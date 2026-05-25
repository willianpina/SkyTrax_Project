"""Spider for airport metadata from skytraxratings.com."""
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
        "ITEM_PIPELINES": {
            "scraper.pipelines.aviation_pipeline.AviationMetadataPipeline": 300,
        },
    }

    def parse(self, response):
        airport_links = response.css("a[href*='/airports/']::attr(href)").getall()
        seen = set()
        for href in airport_links:
            url = response.urljoin(href)
            if url not in seen and "/airports/" in url:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_airport)

    def parse_airport(self, response):
        name = response.css("h1::text").get("").strip()
        if not name:
            return

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
            raw_metadata={
                "page_title": response.css("title::text").get(""),
            },
        )
