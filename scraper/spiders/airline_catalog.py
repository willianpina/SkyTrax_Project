from __future__ import annotations

import scrapy

from scraper.items import AirlineItem
from scraper.spiders.airlinequality import SEED_AIRLINES


class AirlineCatalogSpider(scrapy.Spider):
    """Catalog spider for airline metadata seeding and future source discovery."""

    name = "airline_catalog"

    def start_requests(self):
        for airline in SEED_AIRLINES:
            yield scrapy.Request(
                airline["review_url"],
                callback=self.parse_airline,
                cb_kwargs={"airline": airline},
                dont_filter=True,
            )

    def parse_airline(self, response, airline: dict):
        title = response.css("h1::text").get()
        yield AirlineItem(
            name=title.strip() if title else airline["name"],
            slug=airline["slug"],
            country=airline["country"],
            review_url=response.url,
            source="airlinequality",
        )
