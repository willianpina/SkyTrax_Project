from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from sqlalchemy.exc import IntegrityError

from database.models import Airline, Review
from database.session import SessionLocal
from scraper.pipelines.fingerprinting import review_fingerprint
from scraper.items import AirlineItem, ReviewItem

logger = logging.getLogger(__name__)


class FingerprintPipeline:
    """Attach deterministic fingerprints to review items."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if isinstance(item, ReviewItem) and not adapter.get("fingerprint"):
            adapter["fingerprint"] = review_fingerprint(
                adapter.get("airline_slug"),
                adapter.get("title"),
                adapter.get("text"),
                adapter.get("route"),
                adapter.get("review_date"),
            )
            adapter["scraped_at"] = datetime.now(timezone.utc).isoformat()
        return item


class ValidationPipeline:
    """Drop malformed items before persistence."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if isinstance(item, ReviewItem):
            missing = [
                field
                for field in ("title", "text", "rating", "review_date", "fingerprint")
                if adapter.get(field) in (None, "")
            ]
            if missing:
                raise DropItem(f"Review item missing required fields: {', '.join(missing)}")
        if isinstance(item, AirlineItem) and not adapter.get("slug"):
            raise DropItem("Airline item missing slug")
        return item


class PostgresPersistencePipeline:
    """Persist Scrapy items into PostgreSQL with idempotent deduplication."""

    def open_spider(self, spider):
        self.session = SessionLocal()
        self.inserted_reviews = 0
        self.skipped_reviews = 0
        self.pending_writes = 0
        self.batch_size = int(os.getenv("SCRAPY_DB_BATCH_SIZE", "100"))

    def close_spider(self, spider):
        self._commit(spider)
        self._sync_stats(spider)
        self.session.close()
        logger.info(
            "[OPS][PERSIST] pipeline_closed spider=%s inserted=%d skipped=%d",
            spider.name,
            self.inserted_reviews,
            self.skipped_reviews,
        )

    def process_item(self, item, spider):
        if isinstance(item, AirlineItem):
            self._upsert_airline(ItemAdapter(item), spider)
            return item
        if isinstance(item, ReviewItem):
            self._insert_review(ItemAdapter(item), spider)
            return item
        return item

    def _upsert_airline(self, item: ItemAdapter, spider) -> Airline:
        airline = self.session.query(Airline).filter_by(slug=item["slug"]).first()
        if airline is None:
            airline = Airline(
                name=item["name"],
                slug=item["slug"],
                country=item.get("country"),
                review_url=item.get("review_url"),
                source=item.get("source", "airlinequality"),
            )
            self.session.add(airline)
        else:
            airline.name = item["name"]
            airline.country = item.get("country")
            airline.review_url = item.get("review_url")
            airline.source = item.get("source", airline.source)
        self.session.flush()
        self._mark_write(spider)
        return airline

    def _insert_review(self, item: ItemAdapter, spider) -> None:
        if self.session.query(Review.id).filter_by(fingerprint=item["fingerprint"]).first():
            self.skipped_reviews += 1
            self._sync_stats(spider)
            logger.debug(
                "[OPS][DEDUPE] airline=%s fingerprint=%s",
                item.get("airline_slug"),
                item["fingerprint"][:12],
            )
            return
        airline = self._get_or_create_airline(item)
        review = Review(
            airline_id=airline.id,
            source=item.get("source", "airlinequality"),
            external_id=item.get("external_id"),
            source_url=item.get("source_url"),
            title=item.get("title"),
            text=item["text"],
            rating=item.get("rating"),
            recommended=item.get("recommended"),
            seat_type=item.get("seat_type"),
            route=item.get("route"),
            aircraft=item.get("aircraft"),
            travel_type=item.get("travel_type"),
            review_date=self._parse_date(item.get("review_date")),
            metrics=item.get("metrics") or {},
            fingerprint=item["fingerprint"],
        )
        self.session.add(review)
        try:
            self.session.flush()
            self.inserted_reviews += 1
            airline.last_scraped_at = datetime.now(timezone.utc)
            self._mark_write(spider)
            self._sync_stats(spider)
            logger.debug(
                "[OPS][PERSIST] airline=%s review_date=%s inserted=%d",
                item.get("airline_slug"),
                item.get("review_date"),
                self.inserted_reviews,
            )
        except IntegrityError:
            self.session.rollback()
            self.skipped_reviews += 1
            self._sync_stats(spider)

    def _get_or_create_airline(self, item: ItemAdapter) -> Airline:
        airline = self.session.query(Airline).filter_by(slug=item["airline_slug"]).first()
        if airline is not None:
            return airline
        airline = Airline(
            name=item.get("airline_name") or item["airline_slug"].replace("-", " ").title(),
            slug=item["airline_slug"],
            source=item.get("source", "airlinequality"),
            last_scraped_at=datetime.now(timezone.utc),
        )
        self.session.add(airline)
        self.session.flush()
        return airline

    def _sync_stats(self, spider) -> None:
        """Expose insert/skip counters via Scrapy stats for the telemetry extension."""
        try:
            spider.crawler.stats.set_value("pipeline/reviews_inserted", self.inserted_reviews)
            spider.crawler.stats.set_value("pipeline/reviews_skipped", self.skipped_reviews)
        except Exception:
            pass

    def _mark_write(self, spider) -> None:
        self.pending_writes += 1
        if self.pending_writes >= self.batch_size:
            self._commit(spider)

    def _commit(self, spider) -> None:
        if not getattr(self, "pending_writes", 0):
            return
        try:
            self.session.commit()
            self.pending_writes = 0
        except IntegrityError as exc:
            self.session.rollback()
            if spider is not None:
                spider.logger.warning(
                    "postgres_batch_commit_failed",
                    extra={"spider": spider.name, "error_type": exc.__class__.__name__},
                )

    @staticmethod
    def _parse_date(value: str | date | None) -> date | None:
        if value is None or isinstance(value, date):
            return value
        return date.fromisoformat(value)
