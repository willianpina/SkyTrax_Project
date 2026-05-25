from __future__ import annotations

import logging
import os
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def postgis_requested() -> bool:
    """Whether PostGIS features are requested via ENABLE_POSTGIS."""
    return os.getenv("ENABLE_POSTGIS", "false").lower() in {"true", "1", "yes", "on"}


def try_create_postgis_extension(connection: Connection) -> bool:
    """Attempt CREATE EXTENSION postgis; return True only when available and enabled."""
    if not postgis_requested():
        logger.warning(
            "PostGIS unavailable - geospatial extension skipped (ENABLE_POSTGIS=false)",
            extra={"service": "database", "feature": "postgis"},
        )
        return False
    try:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        logger.info("PostGIS enabled", extra={"service": "database", "feature": "postgis"})
        return True
    except Exception as exc:
        logger.warning(
            "PostGIS unavailable - geospatial features disabled: %s",
            exc,
            extra={"service": "database", "feature": "postgis"},
        )
        return False


def postgis_extension_installed(connection: Connection) -> bool:
    """Check if postgis extension exists in the database."""
    try:
        row = connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'postgis' LIMIT 1")
        ).scalar()
        return bool(row)
    except Exception:
        return False


def airports_location_column_exists(connection: Connection) -> bool:
    """Return True when airports.location geography column is present."""
    try:
        row = connection.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'airports' AND column_name = 'location'
                LIMIT 1
                """
            )
        ).scalar()
        return bool(row)
    except Exception:
        return False


def try_add_airports_location_column(connection: Connection) -> bool:
    """Add geography column and populate from lat/lon when PostGIS is active."""
    if not postgis_extension_installed(connection):
        return False
    try:
        connection.execute(
            text(
                """
                ALTER TABLE airports
                ADD COLUMN IF NOT EXISTS location geography(Point, 4326)
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE airports
                SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL
                  AND location IS NULL
                """
            )
        )
        return True
    except Exception as exc:
        logger.warning(
            "PostGIS geography column skipped: %s",
            exc,
            extra={"service": "database", "feature": "postgis"},
        )
        return False


@lru_cache(maxsize=1)
def runtime_postgis_active() -> bool:
    """Runtime probe: feature flag + extension installed (cached per process)."""
    if not postgis_requested():
        return False
    try:
        from database.session import engine

        with engine.connect() as connection:
            return postgis_extension_installed(connection)
    except Exception:
        return False


def sync_airport_geography(session: Session) -> bool:
    """Populate airports.location when PostGIS is available; no-op otherwise."""
    if not runtime_postgis_active():
        return False
    if not airports_location_column_exists(session.connection()):
        return False
    try:
        session.execute(
            text(
                """
                UPDATE airports
                SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL
                """
            )
        )
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        logger.warning("PostGIS point sync skipped: %s", exc)
        return False
