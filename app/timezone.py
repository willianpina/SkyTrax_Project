"""Centralized timezone utilities for the SkyTrax operational platform.

All operational timestamps displayed to users use America/Sao_Paulo.
Database persistence remains UTC-aware for portability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")


def now_brasilia() -> datetime:
    """Return the current timezone-aware datetime in Brasília/DF."""
    return datetime.now(BRASILIA_TZ)


def now_utc() -> datetime:
    """Return the current timezone-aware datetime in UTC (for DB persistence)."""
    return datetime.now(timezone.utc)


def to_brasilia(dt: datetime) -> datetime:
    """Convert any timezone-aware datetime to Brasília."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRASILIA_TZ)


def format_operational_time(dt: datetime | None = None) -> str:
    """Format a datetime as HH:MM:SS in Brasília timezone."""
    if dt is None:
        dt = now_brasilia()
    elif dt.tzinfo is None or dt.tzinfo != BRASILIA_TZ:
        dt = to_brasilia(dt)
    return dt.strftime("%H:%M:%S")


def operational_timestamp(dt: datetime | None = None) -> str:
    """Return an ISO-8601 timestamp with Brasília offset (e.g. 2026-05-26T22:23:50-03:00)."""
    if dt is None:
        dt = now_brasilia()
    elif dt.tzinfo is None or dt.tzinfo != BRASILIA_TZ:
        dt = to_brasilia(dt)
    return dt.isoformat()


def operational_display(dt: datetime | None = None) -> dict[str, str]:
    """Return both ISO timestamp and display_time for Redis event payloads."""
    if dt is None:
        dt = now_brasilia()
    elif dt.tzinfo is None or dt.tzinfo != BRASILIA_TZ:
        dt = to_brasilia(dt)
    return {
        "timestamp": dt.isoformat(),
        "display_time": dt.strftime("%H:%M:%S"),
    }
