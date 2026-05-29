"""Discovery spider -- finds ALL airline review URLs from airlinequality.com.

Scrapes the airline listing pages to discover every airline with reviews,
then persists them to the `airlines` table for subsequent deep scraping.
"""

from __future__ import annotations

import re
import logging
from urllib.parse import urljoin

import scrapy
from scraper.items import AirlineItem

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.airlinequality.com/review-pages/a-z-airline-reviews/"


class AirlineDiscoverySpider(scrapy.Spider):
    """Discover all airlines with review pages on airlinequality.com."""

    name = "airline_discovery"
    allowed_domains = ["airlinequality.com", "www.airlinequality.com"]
    start_urls = [LISTING_URL]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "DOWNLOAD_TIMEOUT": 30,
        "CLOSESPIDER_PAGECOUNT": 200,
        "ITEM_PIPELINES": {
            "scraper.pipelines.scrapy_pipeline.PostgresPersistencePipeline": 300,
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._discovered = 0
        self._seen_slugs: set[str] = set()

    def parse(self, response):
        links = response.css("a[href*='/airline-reviews/']::attr(href)").getall()
        for href in links:
            url = urljoin(response.url, href).rstrip("/") + "/"
            slug = self._extract_slug(url)
            if not slug or slug in self._seen_slugs:
                continue
            self._seen_slugs.add(slug)
            self._discovered += 1
            name = slug.replace("-", " ").title()
            yield AirlineItem(
                name=name,
                slug=slug,
                country=None,
                review_url=url,
                source="airlinequality",
            )

        next_pages = response.css(
            "a.next::attr(href), a[rel='next']::attr(href), "
            ".pagination a::attr(href), .page-numbers a::attr(href)"
        ).getall()
        for href in next_pages:
            url = urljoin(response.url, href)
            if url != response.url:
                yield scrapy.Request(url, callback=self.parse)

    @staticmethod
    def _extract_slug(url: str) -> str | None:
        match = re.search(r"/airline-reviews/([a-z0-9-]+)/?", url)
        return match.group(1) if match else None

    def closed(self, reason):
        self.logger.info(
            "[DISCOVERY] airline_discovery_closed: discovered=%d reason=%s",
            self._discovered,
            reason,
        )
