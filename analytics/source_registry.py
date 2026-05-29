"""Multi-source Architecture — abstract interfaces for future data sources.

The system currently ingests data exclusively from airlinequality.com (SkyTrax).
This module defines the contracts that future sources must implement to plug into
the Aviation Intelligence Fusion Engine.

Planned sources (NOT yet implemented):
- Reddit          (r/aviation, r/flights)
- FlyerTalk       (forums, trip reports)
- Google Reviews  (airline + airport reviews)
- Trustpilot      (airline reviews)
- X/Twitter       (real-time complaints)
- YouTube         (cabin review videos)
- TripAdvisor     (airline + airport reviews)
- FlightRadar24   (operational data, delays)
- AviationStack   (flight schedules, status)
- OpenSky         (live ADS-B data)
- NOTAM feeds     (official notices)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    REVIEW = "review"
    SOCIAL = "social"
    OPERATIONAL = "operational"
    OFFICIAL = "official"


@dataclass
class SourceConfig:
    """Configuration for a data source."""

    name: str
    source_type: SourceType
    base_url: str
    enabled: bool = False
    priority: int = 100
    rate_limit_rps: float = 1.0
    max_items_per_run: int = 10000
    requires_auth: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestedItem:
    """Normalized item produced by any source adapter."""

    source: str
    external_id: str
    content: str
    title: str = ""
    rating: float | None = None
    author: str = ""
    published_at: datetime | None = None
    airline_ref: str = ""
    airport_ref: str = ""
    route_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    """Base class for data source adapters.

    Each source implements this interface to provide normalized items
    to the fusion pipeline. The adapter handles authentication, pagination,
    rate limiting, and normalization.
    """

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def source_type(self) -> SourceType: ...

    @abstractmethod
    def fetch_items(self, since: datetime | None = None, limit: int = 1000) -> list[IngestedItem]: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    def get_config(self) -> SourceConfig:
        return SourceConfig(
            name=self.name(),
            source_type=self.source_type(),
            base_url="",
        )


class SkyTraxAdapter(SourceAdapter):
    """SkyTrax/airlinequality.com adapter — currently the only active source.

    This adapter wraps the existing Scrapy pipeline output. Items are read from
    the PostgreSQL `reviews` table (already ingested by Scrapy spiders).
    """

    def name(self) -> str:
        return "skytrax"

    def source_type(self) -> SourceType:
        return SourceType.REVIEW

    def fetch_items(self, since: datetime | None = None, limit: int = 1000) -> list[IngestedItem]:
        from database.session import SessionLocal
        from database.models.core import Review, Airline

        session = SessionLocal()
        try:
            q = session.query(Review).join(Airline, Airline.id == Review.airline_id)
            if since:
                q = q.filter(Review.created_at >= since)
            reviews = q.order_by(Review.created_at.desc()).limit(limit).all()
            items = []
            for r in reviews:
                airline = session.query(Airline).get(r.airline_id)
                items.append(
                    IngestedItem(
                        source="skytrax",
                        external_id=r.id,
                        content=r.text,
                        title=r.title or "",
                        rating=r.rating,
                        author=r.author or "",
                        published_at=r.review_date,
                        airline_ref=airline.slug if airline else "",
                        metadata=r.metrics or {},
                    )
                )
            return items
        finally:
            session.close()

    def health_check(self) -> bool:
        try:
            from database.session import SessionLocal
            from database.models.core import Review

            session = SessionLocal()
            try:
                return session.query(Review).count() > 0
            finally:
                session.close()
        except Exception:
            return False


_REGISTRY: dict[str, SourceAdapter] = {}


def register_source(adapter: SourceAdapter) -> None:
    _REGISTRY[adapter.name()] = adapter


def get_source(name: str) -> SourceAdapter | None:
    return _REGISTRY.get(name)


def list_sources() -> list[SourceConfig]:
    return [a.get_config() for a in _REGISTRY.values()]


def get_active_sources() -> list[SourceAdapter]:
    return [a for a in _REGISTRY.values() if a.get_config().enabled]


register_source(SkyTraxAdapter())
