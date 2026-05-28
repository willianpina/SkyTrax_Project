"""Re-exports from the shared catalog for backward compatibility."""

from __future__ import annotations

from app.airline_catalog import (  # noqa: F401
    CRAWL_PROFILES,
    SEED_AIRLINES,
    AirlineTier,
    CrawlProfileName,
    airline_by_slug,
    airlines_for_profile,
    aq_url,
)
