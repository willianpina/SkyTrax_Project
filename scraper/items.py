from __future__ import annotations

import scrapy


class AirlineItem(scrapy.Item):
    name = scrapy.Field()
    slug = scrapy.Field()
    country = scrapy.Field()
    review_url = scrapy.Field()
    source = scrapy.Field()


class ReviewItem(scrapy.Item):
    airline_slug = scrapy.Field()
    airline_name = scrapy.Field()
    source = scrapy.Field()
    external_id = scrapy.Field()
    source_url = scrapy.Field()
    title = scrapy.Field()
    text = scrapy.Field()
    rating = scrapy.Field()
    recommended = scrapy.Field()
    seat_type = scrapy.Field()
    route = scrapy.Field()
    aircraft = scrapy.Field()
    travel_type = scrapy.Field()
    review_date = scrapy.Field()
    metrics = scrapy.Field()
    fingerprint = scrapy.Field()
    scraped_at = scrapy.Field()
