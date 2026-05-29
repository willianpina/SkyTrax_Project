"""Live crawl telemetry — broadcasts spider progress to Redis for real-time UI.

Also implements saturation detection: when no new reviews are inserted for
SATURATION_PAGES consecutive pages, the spider is flagged as saturated and
will stop yielding new requests, advancing the pipeline to the next stage.

Includes telemetry hashing for the SubprocessGovernor to detect frozen state.
"""

from __future__ import annotations

import hashlib
import json
import time
import logging

from app.timezone import format_operational_time, operational_timestamp

from scrapy import signals

logger = logging.getLogger(__name__)

REDIS_STATUS_KEY = "skytrax:ops:refresh:status"
PUBLISH_INTERVAL_S = 3
STALL_THRESHOLD_S = 90
SATURATION_PAGES = 50
SATURATION_TIME_S = 300
MAX_EVENTS = 25


class LiveTelemetryExtension:
    """Scrapy extension that publishes real-time crawl metrics to Redis.

    Features:
    - Live telemetry: current airline, pages, reviews, rate, dupes
    - Stall detection: no items scraped in 90s
    - Saturation detection: no NEW reviews inserted for 50 pages or 5 minutes
    - Telemetry hashing: content_hash for governor frozen-state detection
    - Duplicate streak tracking: consecutive pages with zero new inserts
    """

    def __init__(self):
        self.redis = None
        self.operation_id = ""
        self.started_at = 0.0
        self.last_publish = 0.0
        self.last_item_at = 0.0
        self.baseline_reviews = 0
        self._prev_inserted = 0
        self._inserts_at_check = 0
        self._pages_at_last_insert = 0
        self._time_at_last_insert = 0.0
        self._saturation_announced = False
        self._duplicate_streak = 0
        self._prev_page_count = 0
        self._prev_dupes = 0

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.spider_error, signal=signals.spider_error)
        return ext

    def spider_opened(self, spider):
        self.operation_id = getattr(spider, "operation_id", "") or ""
        if not self.operation_id:
            return

        try:
            from redis import Redis
            from app.config import get_settings

            self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
            self.redis.ping()
        except Exception as exc:
            logger.warning("[OPS][TELEMETRY] Redis unavailable: %s", exc)
            self.redis = None
            return

        self.started_at = time.time()
        self.last_item_at = time.time()
        self._time_at_last_insert = time.time()
        self.last_publish = 0.0

        try:
            from database.session import SessionLocal
            from database.models.core import Review

            session = SessionLocal()
            try:
                self.baseline_reviews = session.query(Review).count()
            finally:
                session.close()
        except Exception:
            self.baseline_reviews = 0

        logger.info(
            "[OPS][TELEMETRY] Active op=%s baseline_reviews=%d",
            self.operation_id,
            self.baseline_reviews,
        )

    def item_scraped(self, item, response, spider):
        self.last_item_at = time.time()
        now = time.time()
        if self.redis and self.operation_id and (now - self.last_publish) >= PUBLISH_INTERVAL_S:
            self._publish(spider)
            self.last_publish = now

    def spider_error(self, failure, response, spider):
        pass

    def spider_closed(self, spider, reason):
        if self.redis and self.operation_id:
            self._publish(spider, final=True)
            logger.info("[OPS][TELEMETRY] Final publish op=%s reason=%s", self.operation_id, reason)

    @staticmethod
    def _telemetry_hash(pages: int, inserted: int, skipped: int, airline: str) -> str:
        raw = f"{pages}|{inserted}|{skipped}|{airline}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _publish(self, spider, final=False):
        if not self.redis:
            return
        try:
            stats = spider.crawler.stats
            inserted = stats.get_value("pipeline/reviews_inserted", 0)
            skipped = stats.get_value("pipeline/reviews_skipped", 0)
            pages = getattr(spider, "_pages_crawled", 0)
            airlines_queued = getattr(spider, "_airlines_queued", 0)
            current_airline = getattr(spider, "_current_airline", "")

            elapsed = max(time.time() - self.started_at, 1)
            rps = inserted / elapsed

            time_since_last = time.time() - self.last_item_at
            stalled = time_since_last > STALL_THRESHOLD_S and elapsed > 30

            if inserted > self._inserts_at_check:
                self._inserts_at_check = inserted
                self._pages_at_last_insert = pages
                self._time_at_last_insert = time.time()
                self._duplicate_streak = 0

            # Track duplicate streak: pages advancing but inserts frozen
            if pages > self._prev_page_count and inserted == self._prev_inserted:
                self._duplicate_streak += pages - self._prev_page_count
            elif inserted > self._prev_inserted:
                self._duplicate_streak = 0
            self._prev_page_count = pages

            pages_dry = pages - self._pages_at_last_insert
            time_dry = time.time() - self._time_at_last_insert
            saturated = (
                (pages_dry >= SATURATION_PAGES or time_dry >= SATURATION_TIME_S)
                and pages > 10
                and inserted == self._inserts_at_check
            )

            if saturated and not self._saturation_announced:
                self._saturation_announced = True
                spider._saturated = True
                logger.warning(
                    "[SATURATION] Corpus saturated. pages_dry=%d time_dry=%.0fs "
                    "inserted=%d pages=%d airline=%s dupe_streak=%d",
                    pages_dry,
                    time_dry,
                    inserted,
                    pages,
                    current_airline,
                    self._duplicate_streak,
                )

            no_insert_seconds = int(time.time() - self._time_at_last_insert)
            total_reviews = self.baseline_reviews + inserted

            telemetry = {
                "current_airline": current_airline,
                "pages_processed": pages,
                "reviews_added": inserted,
                "reviews_total": total_reviews,
                "duplicates_skipped": skipped,
                "reviews_per_second": round(rps, 1),
                "airlines_queued": airlines_queued,
                "crawl_errors": stats.get_value("spider_exceptions", 0) or 0,
                "stalled": stalled,
                "saturated": saturated,
                "pages_since_last_insert": pages_dry,
                "elapsed_seconds": int(elapsed),
                "content_hash": self._telemetry_hash(pages, inserted, skipped, current_airline),
                "duplicate_streak": self._duplicate_streak,
                "no_insert_seconds": no_insert_seconds,
            }

            raw = self.redis.get(REDIS_STATUS_KEY)
            status = json.loads(raw) if raw else {}
            status["crawl_telemetry"] = telemetry
            status["updated_at"] = operational_timestamp()

            delta = inserted - self._prev_inserted
            events = status.get("events", [])
            if current_airline and delta > 0:
                events.append(
                    {
                        "time": format_operational_time(),
                        "message": f"{current_airline} — +{delta} reviews (page {pages})",
                    }
                )
            if saturated and not final:
                events.append(
                    {
                        "time": format_operational_time(),
                        "message": f"[SATURATION] Corpus saturated — {pages_dry} pages, {no_insert_seconds}s without inserts",
                    }
                )
            if self._duplicate_streak > 20 and not saturated and not final:
                events.append(
                    {
                        "time": format_operational_time(),
                        "message": f"[NO_PROGRESS] Duplicate streak: {self._duplicate_streak} pages",
                    }
                )
            if final:
                events.append(
                    {
                        "time": format_operational_time(),
                        "message": f"[CRAWL_EXIT] Crawl done: {inserted} new, {skipped} dupes, {pages} pages"
                        + (f" [SATURATED dupe_streak={self._duplicate_streak}]" if saturated else ""),
                    }
                )
            status["events"] = events[-MAX_EVENTS:]
            self._prev_inserted = inserted

            self.redis.set(REDIS_STATUS_KEY, json.dumps(status), ex=14400)

            if stalled:
                logger.warning(
                    "[TELEMETRY_STATIC] No items in %.0fs. airline=%s reviews=%d pages=%d",
                    time_since_last,
                    current_airline,
                    inserted,
                    pages,
                )
        except Exception as exc:
            logger.warning("[OPS][TELEMETRY] Publish error: %s", exc)
