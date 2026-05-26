"""Spider for airport metadata from skytraxratings.com.

Crawls both the paginated /airports listing and the /a-z-of-airport-ratings
table for maximum coverage. Supports incremental crawl, deduplication, and retry.
"""
from __future__ import annotations

import re
import scrapy
from scraper.items_aviation import AirportMetadataItem


class AirportMetadataSpider(scrapy.Spider):
    name = "airport_metadata"
    allowed_domains = ["skytraxratings.com"]
    start_urls = [
        "https://skytraxratings.com/airports",
        "https://skytraxratings.com/a-z-of-airport-ratings",
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "DOWNLOAD_TIMEOUT": 30,
        "CLOSESPIDER_PAGECOUNT": 2000,
        "ITEM_PIPELINES": {
            "scraper.pipelines.aviation_pipeline.AviationMetadataPipeline": 300,
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_urls = set()
        self._seen_airports = set()
        self._pages_crawled = 0
        self._items_yielded = 0
        self._items_dropped = 0

    def parse(self, response):
        self._pages_crawled += 1
        url = response.url

        if "a-z-of-airport-ratings" in url:
            yield from self._parse_az_table(response)
            return

        airport_links = response.css("a[href*='/airports/']::attr(href)").getall()
        for href in airport_links:
            full_url = response.urljoin(href)
            if self._should_follow_detail(full_url):
                self._seen_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse_airport, errback=self._errback)

        next_links = response.css(
            "a.next::attr(href), "
            "a[rel='next']::attr(href), "
            ".pagination a::attr(href), "
            "a.page-numbers::attr(href), "
            ".nav-links a::attr(href)"
        ).getall()
        for href in next_links:
            full_url = response.urljoin(href)
            if full_url not in self._seen_urls and "page" in full_url:
                self._seen_urls.add(full_url)
                yield scrapy.Request(full_url, callback=self.parse, errback=self._errback)

    def _should_follow_detail(self, url):
        if url in self._seen_urls:
            return False
        if "/airports/" not in url:
            return False
        skip = {"page/", "/airports?", "a-z-of"}
        return not any(s in url for s in skip)

    def _parse_az_table(self, response):
        """Parse the A-Z table page which lists all airports with star ratings."""
        rows = response.css("table tr, .rating-table tr, table.tablesorter tbody tr")
        for row in rows:
            cells = row.css("td")
            if len(cells) < 2:
                continue

            link = row.css("a[href*='/airports/']::attr(href)").get()
            name = row.css("a::text").get("").strip()
            if not name:
                name = cells[0].css("::text").get("").strip()

            stars_text = cells[-1].css("::text").get("").strip() if cells else ""
            star_match = re.search(r"(\d)", stars_text)
            rating = int(star_match.group(1)) if star_match else None

            if link:
                full_url = response.urljoin(link)
                if self._should_follow_detail(full_url):
                    self._seen_urls.add(full_url)
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_airport,
                        cb_kwargs={"az_rating": rating},
                        errback=self._errback,
                    )

    def parse_airport(self, response, az_rating=None):
        name = (
            response.css("h1::text").get("")
            or response.css("h1.entry-title::text").get("")
            or response.css(".airport-name::text").get("")
            or response.css("article h1::text").get("")
        ).strip()

        if not name:
            self._items_dropped += 1
            return

        name_key = name.lower()
        if name_key in self._seen_airports:
            return
        self._seen_airports.add(name_key)

        iata = self._extract_iata(response, name)
        country = self._extract_field(response, [
            ".airport-country::text", ".country::text",
            "meta[name='country']::attr(content)",
        ])
        city = self._extract_field(response, [
            ".airport-city::text", ".city::text",
            "meta[name='city']::attr(content)",
        ])
        region = self._extract_field(response, [
            ".airport-region::text", ".region::text",
        ])

        rating = az_rating or self._extract_rating(response)
        hub_level = self._extract_hub_level(response)

        self._items_yielded += 1
        self.logger.info(
            "[AIRPORT] #%d %s (%s) — %s, %s — %s★ — hub=%s",
            self._items_yielded, name, iata or "???",
            city or "?", country or "?", rating or "?", hub_level or "none",
        )

        yield AirportMetadataItem(
            airport_name=name,
            iata=iata,
            icao=None,
            city=city or None,
            country=country or None,
            region=region or None,
            airport_rating=rating,
            hub_level=hub_level,
            passenger_volume=None,
            latitude=None,
            longitude=None,
            operational_labels=self._extract_labels(response),
            skytrax_url=response.url,
            raw_metadata={"page_title": response.css("title::text").get("")},
        )

    def _extract_iata(self, response, name):
        for sel in [".iata-code::text", ".airport-code::text", ".code::text"]:
            val = response.css(sel).get("").strip().upper()
            if val and len(val) == 3 and val.isalpha():
                return val
        match = re.search(r"\(([A-Z]{3})\)", name)
        if match:
            return match.group(1)
        body = response.css("article, .entry-content, .airport-content").get("") or ""
        match = re.search(r"IATA\s*(?:code)?[:\s]+([A-Z]{3})", body)
        if match:
            return match.group(1)
        return None

    def _extract_field(self, response, selectors):
        for sel in selectors:
            val = response.css(sel).get("").strip()
            if val:
                return val
        return ""

    def _extract_rating(self, response):
        stars = response.css(".star-rating img, .stars img, .rating img")
        if stars:
            return len(stars)
        for sel in [".star-rating::text", ".rating::text", ".airport-rating::text"]:
            val = response.css(sel).get("").strip()
            m = re.search(r"(\d)", val)
            if m:
                return int(m.group(1))
        filled = response.css(".star.filled, .star-fill, .fa-star")
        if filled:
            return len(filled)
        return None

    def _extract_hub_level(self, response):
        labels = self._extract_labels(response)
        for lbl in labels:
            low = lbl.lower()
            if "major hub" in low or "international hub" in low:
                return "major"
            if "hub" in low:
                return "secondary"
            if "regional" in low:
                return "regional"

        body_text = (response.css("article").get("") or "").lower()
        if "major hub" in body_text or "international hub" in body_text:
            return "major"
        if "hub airport" in body_text:
            return "secondary"
        return None

    def _extract_labels(self, response):
        labels = response.css(
            ".airport-label::text, .tag::text, .badge::text, "
            ".airport-type::text, .entry-meta span::text"
        ).getall()
        return [lbl.strip() for lbl in labels if lbl.strip()]

    def _errback(self, failure):
        self.logger.warning("[AIRPORT] request_failed: %s", failure.request.url)

    def closed(self, reason):
        self.logger.info(
            "[AIRPORT] spider_closed: pages=%d items=%d dropped=%d urls_seen=%d reason=%s",
            self._pages_crawled, self._items_yielded, self._items_dropped,
            len(self._seen_urls), reason,
        )
