"""Spider for airport metadata from skytraxratings.com.

Supports full pagination, incremental crawl, deduplication, and retry.
"""
from __future__ import annotations

import scrapy
from scraper.items_aviation import AirportMetadataItem


class AirportMetadataSpider(scrapy.Spider):
    name = "airport_metadata"
    allowed_domains = ["skytraxratings.com"]
    start_urls = ["https://skytraxratings.com/airports"]
    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "DOWNLOAD_TIMEOUT": 30,
        "ITEM_PIPELINES": {
            "scraper.pipelines.aviation_pipeline.AviationMetadataPipeline": 300,
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_urls = set()
        self._pages_crawled = 0
        self._items_yielded = 0

    def parse(self, response):
        self._pages_crawled += 1
        airport_links = response.css("a[href*='/airports/']::attr(href)").getall()
        for href in airport_links:
            url = response.urljoin(href)
            if url not in self._seen_urls and "/airports/" in url and url != response.url:
                self._seen_urls.add(url)
                yield scrapy.Request(url, callback=self.parse_airport, errback=self._errback)

        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href), .pagination a::attr(href)").getall()
        for href in next_page:
            url = response.urljoin(href)
            if url not in self._seen_urls:
                self._seen_urls.add(url)
                yield scrapy.Request(url, callback=self.parse, errback=self._errback)

    def parse_airport(self, response):
        name = response.css("h1::text").get("").strip()
        if not name:
            return

        self._items_yielded += 1
        iata = response.css(".iata-code::text, .airport-code::text").get("").strip().upper() or None
        country = response.css(".airport-country::text, .country::text").get("").strip()
        city = response.css(".airport-city::text, .city::text").get("").strip()
        region = response.css(".airport-region::text, .region::text").get("").strip()

        stars = response.css(".star-rating img, .stars img")
        rating = len(stars) if stars else None

        labels = response.css(".airport-label::text, .tag::text, .badge::text").getall()
        labels = [l.strip() for l in labels if l.strip()]

        hub_level = None
        for lbl in labels:
            low = lbl.lower()
            if "major hub" in low:
                hub_level = "major"
            elif "hub" in low:
                hub_level = "secondary"

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
            operational_labels=labels,
            skytrax_url=response.url,
            raw_metadata={"page_title": response.css("title::text").get("")},
        )

    def _errback(self, failure):
        self.logger.warning("request_failed: %s", failure.request.url)

    def closed(self, reason):
        self.logger.info(
            "airport_metadata_spider_closed: pages=%d items=%d urls_seen=%d reason=%s",
            self._pages_crawled, self._items_yielded, len(self._seen_urls), reason,
        )
