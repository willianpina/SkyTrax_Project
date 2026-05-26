from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import scrapy
import trafilatura
from bs4 import BeautifulSoup, Tag

from scraper.items import AirlineItem, ReviewItem

MAX_PAGES_ABSOLUTE = 500

SEED_AIRLINES = [
    {
        "name": "British Airways",
        "slug": "british-airways",
        "country": "United Kingdom",
        "review_url": "https://www.airlinequality.com/airline-reviews/british-airways/",
        "priority": 1,
    },
    {
        "name": "Emirates",
        "slug": "emirates",
        "country": "United Arab Emirates",
        "review_url": "https://www.airlinequality.com/airline-reviews/emirates/",
        "priority": 2,
    },
    {
        "name": "Qatar Airways",
        "slug": "qatar-airways",
        "country": "Qatar",
        "review_url": "https://www.airlinequality.com/airline-reviews/qatar-airways/",
        "priority": 3,
    },
    {
        "name": "Lufthansa",
        "slug": "lufthansa",
        "country": "Germany",
        "review_url": "https://www.airlinequality.com/airline-reviews/lufthansa/",
        "priority": 4,
    },
    {
        "name": "LATAM Airlines",
        "slug": "latam-airlines",
        "country": "Brazil/Chile",
        "review_url": "https://www.airlinequality.com/airline-reviews/latam-airlines/",
        "priority": 5,
    },
]


class AirlineQualitySpider(scrapy.Spider):
    """Full historical review ingestion spider for airlinequality.com.

    Supports unlimited pagination (max_pages=0) and incremental crawling
    (skip airlines scraped within --skip_recent_hours).
    """

    name = "airlinequality_reviews"
    allowed_domains = ["airlinequality.com", "www.airlinequality.com"]

    def __init__(self, airline: str | None = None, max_pages: str = "0",
                 mode: str = "seed", skip_recent_hours: str = "0",
                 operation_id: str = "", **kwargs):
        super().__init__(**kwargs)
        self.airline_filter = airline
        self.max_pages = int(max_pages)
        self.mode = mode
        self.skip_recent_hours = int(skip_recent_hours)
        self.operation_id = operation_id

        self._airlines_queued = 0
        self._airlines_skipped = 0
        self._pages_crawled = 0
        self._reviews_parsed = 0
        self._reviews_dropped = 0
        self._current_airline = ""
        self._saturated = False

    def _build_airline_list(self) -> list[dict]:
        if self.airline_filter:
            return [self._make_entry(self.airline_filter)]
        if self.mode == "all":
            return self._airlines_from_db()
        return sorted(SEED_AIRLINES, key=lambda row: row.get("priority", 99))

    def _airlines_from_db(self) -> list[dict]:
        try:
            from database.session import SessionLocal
            from database.models.core import Airline
            session = SessionLocal()
            try:
                rows = session.query(Airline).filter(Airline.is_active.is_(True)).all()
                cutoff = None
                if self.skip_recent_hours > 0:
                    cutoff = datetime.now(timezone.utc) - timedelta(hours=self.skip_recent_hours)

                result = []
                skipped = 0
                for row in rows:
                    if cutoff and row.last_scraped_at and row.last_scraped_at >= cutoff:
                        skipped += 1
                        continue
                    url = row.review_url or f"https://www.airlinequality.com/airline-reviews/{row.slug}/"
                    result.append({
                        "name": row.name,
                        "slug": row.slug,
                        "country": row.country,
                        "review_url": url,
                        "priority": 5,
                    })
                self._airlines_skipped = skipped
                self.logger.info(
                    "[CRAWLER] Loaded %d airlines from DB, skipped %d (recently scraped), mode=all",
                    len(result), skipped,
                )
                return result
            finally:
                session.close()
        except Exception as exc:
            self.logger.warning("[CRAWLER] DB load failed, falling back to seeds: %s", exc)
            return SEED_AIRLINES

    @staticmethod
    def _make_entry(slug: str) -> dict:
        return {
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "country": None,
            "review_url": f"https://www.airlinequality.com/airline-reviews/{slug}/",
            "priority": 1,
        }

    def start_requests(self):
        airlines = self._build_airline_list()
        self._airlines_queued = len(airlines)
        effective_limit = self.max_pages if self.max_pages > 0 else "unlimited"
        self.logger.info(
            "[CRAWLER] Starting: airlines=%d max_pages=%s mode=%s skip_recent=%dh",
            len(airlines), effective_limit, self.mode, self.skip_recent_hours,
        )
        for airline in airlines:
            yield scrapy.Request(
                airline["review_url"],
                callback=self.parse_listing,
                cb_kwargs={"airline": airline, "page": 1},
                meta={"airline_slug": airline["slug"]},
            )

    def parse_listing(self, response, airline: dict, page: int):
        if self._saturated:
            self.logger.info(
                "[OPS][SATURATION] Corpus saturated — skipping %s page %d",
                airline.get("slug"), page,
            )
            return

        self._pages_crawled += 1
        self._current_airline = airline.get("name", airline.get("slug", ""))

        if page == 1:
            yield AirlineItem(
                name=airline["name"],
                slug=airline["slug"],
                country=airline.get("country"),
                review_url=airline.get("review_url"),
                source="airlinequality",
            )

        cards = response.css(
            "article[itemprop='review'], article.review, article[class*='review'], "
            ".comp_media-review-rated"
        )

        page_reviews = 0
        for card in cards:
            html = card.get()
            item = self._parse_card(html, airline, response.url)
            if item:
                page_reviews += 1
                yield item

        self.logger.info(
            "[OPS][CRAWL] airline=%s page=%d cards=%d reviews=%d total_pages=%d",
            airline["slug"], page, len(cards), page_reviews, self._pages_crawled,
        )

        if not cards:
            return

        should_continue = (
            (self.max_pages == 0 or page < self.max_pages)
            and page < MAX_PAGES_ABSOLUTE
        )
        if should_continue:
            next_url = self._next_page_url(response.url, page + 1)
            self.logger.info(
                "[OPS][PAGINATION] airline=%s next_page=%d",
                airline["slug"], page + 1,
            )
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                cb_kwargs={"airline": airline, "page": page + 1},
                meta={"airline_slug": airline["slug"]},
            )

    @staticmethod
    def _next_page_url(current_url: str, next_page: int) -> str:
        base = current_url.split("/page/")[0].rstrip("/") + "/"
        return urljoin(base, f"page/{next_page}/")

    def _parse_card(self, html: str, airline: dict, source_url: str) -> ReviewItem | None:
        soup = BeautifulSoup(html, "html.parser")
        text = self._clean_review_text(
            self._text(soup.select_one("[itemprop='reviewBody'], .text_content, .review-content"))
        )
        title = self._clean_title(self._text(soup.select_one("h2.text_header, h2, .review-title")))
        metrics = self._extract_metrics(soup)
        rating = self._rating(soup, metrics)
        review_date = self._review_date(soup)

        if not title or len(text) < 40 or rating is None or review_date is None:
            self._reviews_dropped += 1
            return None
        self._reviews_parsed += 1
        return ReviewItem(
            airline_slug=airline["slug"],
            airline_name=airline["name"],
            source="airlinequality",
            external_id=None,
            source_url=source_url,
            title=title,
            text=text,
            rating=rating,
            recommended=self._recommended(metrics),
            seat_type=metrics.get("seat_type"),
            route=metrics.get("route"),
            aircraft=metrics.get("aircraft"),
            travel_type=metrics.get("type_of_traveller"),
            review_date=review_date,
            metrics=metrics,
        )

    @staticmethod
    def _extract_metrics(card: Tag) -> dict[str, str]:
        metrics: dict[str, str] = {}
        for row in card.select("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) >= 2:
                metrics[cells[0].lower().replace(" ", "_")] = cells[1]
        return metrics

    @staticmethod
    def _rating(card: Tag, metrics: dict[str, str]) -> float | None:
        candidates = [metrics.get("rating"), AirlineQualitySpider._text(card.select_one(".rating-10, .review-rating"))]
        rating_value = AirlineQualitySpider._text(card.select_one("[itemprop='ratingValue']"))
        if rating_value:
            candidates.insert(0, rating_value)
        for candidate in candidates:
            if not candidate:
                continue
            candidate = candidate.replace("\n", " ").strip()
            match = re.search(r"\d+(?:\.\d+)?", candidate)
            if not match:
                continue
            try:
                rating = float(match.group(0))
                if 0 <= rating <= 10:
                    return rating
            except ValueError:
                continue
        return None

    @staticmethod
    def _recommended(metrics: dict[str, str]) -> bool | None:
        value = metrics.get("recommended")
        if value is None:
            return None
        return value.strip().lower() in {"yes", "true", "recommended"}

    @staticmethod
    def _review_date(card: Tag):
        date_node = card.select_one("time, [itemprop='datePublished'], .date, .published-date")
        value = ""
        if date_node:
            value = date_node.get("datetime") or date_node.get("content") or AirlineQualitySpider._text(date_node)
        if not value:
            return None
        value = re.sub(r"^published\s+", "", value.strip(), flags=re.IGNORECASE)
        value = value.replace("st ", " ").replace("nd ", " ").replace("rd ", " ").replace("th ", " ")
        for fmt in ("%d %B %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def _text(node: Tag | None) -> str:
        return node.get_text(" ", strip=True) if node else ""

    @staticmethod
    def _clean_title(value: str) -> str:
        return value.strip().strip('"').strip()

    @staticmethod
    def _clean_review_text(value: str) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        return re.sub(
            r"^(✅\s*)?(Trip Verified|Not Verified)\s*\|?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if should_continue:
            self.logger.info(
                "[OPS][PAGINATION] airline=%s page=%d url=%s",
                airline["slug"], page + 1, next_url,
            )

    def closed(self, reason):
        self.logger.info(
            "[OPS][CRAWL] spider_closed airlines=%d pages=%d reviews=%d "
            "dropped=%d skipped=%d max_pages=%d mode=%s reason=%s",
            self._airlines_queued, self._pages_crawled, self._reviews_parsed,
            self._reviews_dropped, self._airlines_skipped,
            self.max_pages, self.mode, reason,
        )
