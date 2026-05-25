from __future__ import annotations

import random
from datetime import datetime, timezone

from scrapy import signals
from scrapy.downloadermiddlewares.retry import get_retry_request

from database.models import SpiderRun
from database.session import SessionLocal


class RotatingUserAgentMiddleware:
    """Rotate user agents to reduce simple bot fingerprinting."""

    def __init__(self, user_agents: list[str]) -> None:
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getlist("USER_AGENTS"))

    def process_request(self, request, spider):
        if self.user_agents:
            request.headers["User-Agent"] = random.choice(self.user_agents)


class AntiBanHeadersMiddleware:
    """Apply conservative browser-like headers for public review pages."""

    def process_request(self, request, spider):
        request.headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        request.headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        request.headers.setdefault("DNT", "1")
        request.headers.setdefault("Upgrade-Insecure-Requests", "1")
        request.headers.setdefault("Sec-Fetch-Site", "none")
        request.headers.setdefault("Sec-Fetch-Mode", "navigate")
        request.headers.setdefault("Sec-Fetch-Dest", "document")


class SmartRetryMiddleware:
    """Retry throttled responses with incremental delay and explicit stats."""

    retry_statuses = {408, 429, 500, 502, 503, 504, 522, 524}

    def process_response(self, request, response, spider):
        if response.status not in self.retry_statuses:
            return response
        retry_times = request.meta.get("retry_times", 0)
        spider.crawler.stats.inc_value("smart_retry/count")
        spider.crawler.stats.inc_value(f"smart_retry/status/{response.status}")
        retry_request = get_retry_request(
            request,
            spider=spider,
            reason=f"status_{response.status}",
        )
        return retry_request or response


class SpiderStatsExtension:
    """Persist operational stats for spider runs."""

    @classmethod
    def from_crawler(cls, crawler):
        extension = cls()
        crawler.signals.connect(extension.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        return extension

    def spider_opened(self, spider):
        self.started_at = datetime.now(timezone.utc)
        self.run_id = None
        session = SessionLocal()
        try:
            run = SpiderRun(
                spider_name=spider.name,
                source="airlinequality",
                status="running",
                started_at=self.started_at,
                items_scraped=0,
                pages_crawled=0,
                errors=[],
            )
            session.add(run)
            session.commit()
            self.run_id = run.id
        finally:
            session.close()

    def spider_closed(self, spider, reason):
        finished_at = datetime.now(timezone.utc)
        stats = dict(spider.crawler.stats.get_stats())
        errors = self._errors(stats)
        status = "success" if reason == "finished" and not errors else reason
        session = SessionLocal()
        try:
            run = session.get(SpiderRun, self.run_id) if self.run_id else None
            if run is None:
                run = SpiderRun(
                    spider_name=spider.name,
                    source="airlinequality",
                    status=status,
                    started_at=getattr(self, "started_at", finished_at),
                    errors=[],
                )
                session.add(run)
            run.status = status
            run.finished_at = finished_at
            run.items_scraped = int(stats.get("item_scraped_count", 0) or 0)
            run.pages_crawled = int(stats.get("response_received_count", 0) or 0)
            run.errors = errors
            session.commit()
        finally:
            session.close()
        duration_ms = int((finished_at - getattr(self, "started_at", finished_at)).total_seconds() * 1000)
        spider.logger.info(
            "spider_closed",
            extra={
                "service": "scrapy",
                "spider": spider.name,
                "reason": reason,
                "status": status,
                "duration_ms": duration_ms,
                "items_scraped": stats.get("item_scraped_count", 0),
                "pages_crawled": stats.get("response_received_count", 0),
                "retries": stats.get("retry/count", 0),
                "errors": errors,
            },
        )

    @staticmethod
    def _errors(stats: dict) -> list[dict[str, object]]:
        errors: list[dict[str, object]] = []
        for key, value in stats.items():
            if key.startswith("spider_exceptions/") or key.startswith("downloader/exception_type_count/"):
                errors.append({"type": key.rsplit("/", 1)[-1], "count": int(value)})
        log_errors = int(stats.get("log_count/ERROR", 0) or 0)
        if log_errors:
            errors.append({"type": "log_error", "count": log_errors})
        return errors
