"""Spider for airline metadata from skytraxratings.com.

Supports full pagination, incremental crawl, deduplication, and retry.
"""
from __future__ import annotations

import scrapy
from scraper.items_aviation import AirlineMetadataItem


class AirlineMetadataSpider(scrapy.Spider):
    name = "airline_metadata"
    allowed_domains = ["skytraxratings.com"]
    start_urls = ["https://skytraxratings.com/airlines"]
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
        airline_links = response.css("a[href*='/airlines/']::attr(href)").getall()
        for href in airline_links:
            url = response.urljoin(href)
            if url not in self._seen_urls and "/airlines/" in url and url != response.url:
                self._seen_urls.add(url)
                yield scrapy.Request(url, callback=self.parse_airline, errback=self._errback)

        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href), .pagination a::attr(href)").getall()
        for href in next_page:
            url = response.urljoin(href)
            if url not in self._seen_urls:
                self._seen_urls.add(url)
                yield scrapy.Request(url, callback=self.parse, errback=self._errback)

    def parse_airline(self, response):
        name = response.css("h1::text").get("").strip()
        if not name:
            return

        self._items_yielded += 1
        slug = response.url.rstrip("/").split("/")[-1]
        country = response.css(".airline-country::text, .country::text").get("").strip()

        stars_els = response.css(".star-rating img, .stars img")
        star_rating = len(stars_els) if stars_els else None

        labels = response.css(".airline-label::text, .tag::text, .badge::text").getall()
        labels = [lbl.strip() for lbl in labels if lbl.strip()]

        alliance = None
        for label in labels:
            low = label.lower()
            if "oneworld" in low:
                alliance = "Oneworld"
            elif "star alliance" in low:
                alliance = "Star Alliance"
            elif "skyteam" in low:
                alliance = "SkyTeam"

        is_low_cost = any("low" in lbl.lower() and "cost" in lbl.lower() for lbl in labels)
        is_premium = star_rating is not None and star_rating >= 4

        hubs_text = response.css(".hub-airports::text, .hubs::text").getall()
        hub_airports = [h.strip() for h in hubs_text if h.strip()]

        certs = response.css(".certification::text, .cert::text").getall()
        certs = [c.strip() for c in certs if c.strip()]

        airline_type = "low_cost" if is_low_cost else "full_service"

        yield AirlineMetadataItem(
            airline_name=name,
            slug=slug,
            country=country or None,
            alliance=alliance,
            airline_type=airline_type,
            star_rating=star_rating,
            is_low_cost=is_low_cost,
            is_premium=is_premium,
            hub_airports=hub_airports,
            certifications=certs,
            operational_labels=labels,
            skytrax_url=response.url,
            raw_metadata={
                "page_title": response.css("title::text").get(""),
                "meta_description": response.css('meta[name="description"]::attr(content)').get(""),
            },
        )

    def _errback(self, failure):
        self.logger.warning("request_failed: %s", failure.request.url)

    def closed(self, reason):
        self.logger.info(
            "airline_metadata_spider_closed: pages=%d items=%d urls_seen=%d reason=%s",
            self._pages_crawled, self._items_yielded, len(self._seen_urls), reason,
        )
