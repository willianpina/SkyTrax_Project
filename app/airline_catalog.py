"""Shared airline seed catalog — importable by analytics, scraper, and any other layer."""
from __future__ import annotations

from typing import Literal

AirlineTier = Literal["premium", "low_cost", "regional", "strategic"]
CrawlProfileName = Literal["aggressive", "balanced", "lightweight"]


def aq_url(slug: str) -> str:
    return f"https://www.airlinequality.com/airline-reviews/{slug}/"


CRAWL_PROFILES: dict[CrawlProfileName, dict] = {
    "aggressive": {"max_pages": 8, "download_delay": 0.8, "concurrent_per_domain": 6},
    "balanced": {"max_pages": 4, "download_delay": 1.5, "concurrent_per_domain": 4},
    "lightweight": {"max_pages": 2, "download_delay": 2.5, "concurrent_per_domain": 2},
}

SEED_AIRLINES: list[dict] = [
    {"name": "British Airways", "slug": "british-airways", "country": "United Kingdom", "tier": "premium", "profile": "balanced", "priority": 1},
    {"name": "Emirates", "slug": "emirates", "country": "United Arab Emirates", "tier": "premium", "profile": "aggressive", "priority": 2},
    {"name": "Qatar Airways", "slug": "qatar-airways", "country": "Qatar", "tier": "premium", "profile": "aggressive", "priority": 3},
    {"name": "Lufthansa", "slug": "lufthansa", "country": "Germany", "tier": "premium", "profile": "balanced", "priority": 4},
    {"name": "LATAM Airlines", "slug": "latam-airlines", "country": "Brazil/Chile", "tier": "regional", "profile": "balanced", "priority": 5},
    {"name": "American Airlines", "slug": "american-airlines", "country": "United States", "tier": "strategic", "profile": "balanced", "priority": 6},
    {"name": "Delta Air Lines", "slug": "delta-air-lines", "country": "United States", "tier": "strategic", "profile": "balanced", "priority": 7},
    {"name": "United Airlines", "slug": "united-airlines", "country": "United States", "tier": "strategic", "profile": "balanced", "priority": 8},
    {"name": "Air France", "slug": "air-france", "country": "France", "tier": "premium", "profile": "balanced", "priority": 9},
    {"name": "KLM", "slug": "klm", "country": "Netherlands", "tier": "premium", "profile": "balanced", "priority": 10},
    {"name": "Turkish Airlines", "slug": "turkish-airlines", "country": "Turkey", "tier": "strategic", "profile": "balanced", "priority": 11},
    {"name": "Singapore Airlines", "slug": "singapore-airlines", "country": "Singapore", "tier": "premium", "profile": "aggressive", "priority": 12},
    {"name": "Ryanair", "slug": "ryanair", "country": "Ireland", "tier": "low_cost", "profile": "lightweight", "priority": 13},
    {"name": "easyJet", "slug": "easyjet", "country": "United Kingdom", "tier": "low_cost", "profile": "lightweight", "priority": 14},
    {"name": "ANA", "slug": "ana-all-nippon-airways", "country": "Japan", "tier": "premium", "profile": "balanced", "priority": 15},
    {"name": "Cathay Pacific", "slug": "cathay-pacific", "country": "Hong Kong", "tier": "premium", "profile": "balanced", "priority": 16},
    {"name": "Etihad Airways", "slug": "etihad-airways", "country": "United Arab Emirates", "tier": "premium", "profile": "balanced", "priority": 17},
    {"name": "Iberia", "slug": "iberia", "country": "Spain", "tier": "regional", "profile": "lightweight", "priority": 18},
    {"name": "Air Canada", "slug": "air-canada", "country": "Canada", "tier": "strategic", "profile": "balanced", "priority": 19},
    {"name": "TAP Air Portugal", "slug": "tap-portugal", "country": "Portugal", "tier": "regional", "profile": "lightweight", "priority": 20},
]

for row in SEED_AIRLINES:
    row["review_url"] = aq_url(row["slug"])


def airlines_for_profile(profile: CrawlProfileName | None = None) -> list[dict]:
    rows = sorted(SEED_AIRLINES, key=lambda r: r.get("priority", 99))
    if profile:
        return [r for r in rows if r.get("profile") == profile]
    return rows


def airline_by_slug(slug: str) -> dict | None:
    return next((r for r in SEED_AIRLINES if r["slug"] == slug), None)
