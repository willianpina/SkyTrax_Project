"""Spider for airline metadata from skytraxratings.com."""
from __future__ import annotations

import re

import scrapy
from scraper.items_aviation import AirlineMetadataItem


class AirlineMetadataSpider(scrapy.Spider):
    name = "airline_metadata"
    allowed_domains = ["skytraxratings.com"]
    start_urls = ["https://skytraxratings.com/airlines"]
    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ITEM_PIPELINES": {
            "scraper.pipelines.aviation_pipeline.AviationMetadataPipeline": 300,
        },
    }

    def parse(self, response):
        airline_links = response.css("a[href*='/airlines/']::attr(href)").getall()
        seen = set()
        for href in airline_links:
            url = response.urljoin(href)
            if url not in seen and "/airlines/" in url:
                seen.add(url)
                yield scrapy.Request(url, callback=self.parse_airline)

    def parse_airline(self, response):
        name = response.css("h1::text").get("").strip()
        if not name:
            return

        slug = response.url.rstrip("/").split("/")[-1]
        country = response.css(".airline-country::text, .country::text").get("").strip()

        stars_els = response.css(".star-rating img, .stars img")
        star_rating = len(stars_els) if stars_els else None

        labels = response.css(".airline-label::text, .tag::text, .badge::text").getall()
        labels = [l.strip() for l in labels if l.strip()]

        alliance = None
        for label in labels:
            low = label.lower()
            if "oneworld" in low:
                alliance = "Oneworld"
            elif "star alliance" in low:
                alliance = "Star Alliance"
            elif "skyteam" in low:
                alliance = "SkyTeam"

        is_low_cost = any("low" in l.lower() and "cost" in l.lower() for l in labels)
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
