"""Scrapy items for aviation metadata crawling."""

from __future__ import annotations

import scrapy


class AirlineMetadataItem(scrapy.Item):
    airline_name = scrapy.Field()
    slug = scrapy.Field()
    country = scrapy.Field()
    alliance = scrapy.Field()
    airline_type = scrapy.Field()
    star_rating = scrapy.Field()
    is_low_cost = scrapy.Field()
    is_premium = scrapy.Field()
    hub_airports = scrapy.Field()
    certifications = scrapy.Field()
    operational_labels = scrapy.Field()
    skytrax_url = scrapy.Field()
    raw_metadata = scrapy.Field()


class AirportMetadataItem(scrapy.Item):
    airport_name = scrapy.Field()
    iata = scrapy.Field()
    icao = scrapy.Field()
    city = scrapy.Field()
    country = scrapy.Field()
    region = scrapy.Field()
    airport_rating = scrapy.Field()
    hub_level = scrapy.Field()
    passenger_volume = scrapy.Field()
    latitude = scrapy.Field()
    longitude = scrapy.Field()
    operational_labels = scrapy.Field()
    skytrax_url = scrapy.Field()
    raw_metadata = scrapy.Field()
