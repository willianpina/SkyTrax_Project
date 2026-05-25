from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import scrapy
import trafilatura
from bs4 import BeautifulSoup, Tag

from scraper.items import AirlineItem, ReviewItem


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
    """Scrapy spider for AirlineQuality/Skytrax airline review pages."""

    name = "airlinequality_reviews"
    allowed_domains = ["airlinequality.com", "www.airlinequality.com"]
    custom_settings = {"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30_000}

    def __init__(self, airline: str | None = None, max_pages: str = "3",
                 use_playwright: str = "false", mode: str = "seed", **kwargs):
        super().__init__(**kwargs)
        self.airline_filter = airline
        self.max_pages = int(max_pages)
        self.use_playwright = use_playwright.lower() == "true"
        self.mode = mode
        self._airlines_queued = 0
        self._reviews_parsed = 0

    def _build_airline_list(self) -> list[dict]:
        if self.airline_filter:
            return [self._make_entry(self.airline_filter)]

        if self.mode == "all":
            return self._airlines_from_db()

        return sorted(SEED_AIRLINES, key=lambda row: row.get("priority", 99))

    def _airlines_from_db(self) -> list[dict]:
        """Load all active airlines from the database."""
        try:
            from database.session import SessionLocal
            from database.models.core import Airline
            session = SessionLocal()
            try:
                rows = session.query(Airline).filter(Airline.is_active.is_(True)).all()
                result = []
                for row in rows:
                    url = row.review_url or f"https://www.airlinequality.com/airline-reviews/{row.slug}/"
                    result.append({
                        "name": row.name,
                        "slug": row.slug,
                        "country": row.country,
                        "review_url": url,
                        "priority": 5,
                    })
                self.logger.info("[SCRAPER] Loaded %d airlines from DB (mode=all)", len(result))
                return result
            finally:
                session.close()
        except Exception as exc:
            self.logger.warning("[SCRAPER] DB load failed, falling back to seeds: %s", exc)
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
        self.logger.info("[SCRAPER] Starting review crawl: %d airlines, max_pages=%d, mode=%s",
                         len(airlines), self.max_pages, self.mode)
        for airline in airlines:
            yield scrapy.Request(
                airline["review_url"],
                callback=self.parse_listing,
                cb_kwargs={"airline": airline, "page": 1},
                meta={"playwright": self.use_playwright, "airline_slug": airline["slug"]},
            )

    def parse_listing(self, response, airline: dict, page: int):
        yield AirlineItem(source="airlinequality", **airline)

        cards = response.css(
            "article[itemprop='review'], article.review, article[class*='review'], "
            ".comp_media-review-rated"
        )
        if not cards:
            extracted = trafilatura.extract(response.text) or ""
            if extracted.strip():
                self.logger.warning(
                    "review_cards_not_found",
                    extra={"spider": self.name, "airline": airline["slug"], "url": response.url},
                )
        for card in cards:
            html = card.get()
            item = self._parse_card(html, airline, response.url)
            if item:
                yield item

        if page < self.max_pages:
            next_url = self._next_page_url(response.url, page + 1)
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                cb_kwargs={"airline": airline, "page": page + 1},
                meta={"playwright": self.use_playwright, "airline_slug": airline["slug"]},
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
            self.logger.debug(
                "review_card_dropped",
                extra={
                    "spider": self.name,
                    "airline": airline["slug"],
                    "has_title": bool(title),
                    "text_length": len(text),
                    "has_rating": rating is not None,
                    "has_review_date": review_date is not None,
                },
            )
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

    def closed(self, reason):
        self.logger.info(
            "[SCRAPER] airlinequality_reviews closed: airlines_queued=%d reviews_parsed=%d "
            "mode=%s max_pages=%d reason=%s",
            self._airlines_queued, self._reviews_parsed, self.mode, self.max_pages, reason,
        )
