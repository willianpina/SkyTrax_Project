"""Canonical aviation schema audit and repair helpers."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from database.runtime_schema import physical_table_columns

logger = logging.getLogger(__name__)

AVIATION_REQUIRED_COLUMNS = {
    "airline_metadata": [
        "iata_code",
        "icao_code",
        "primary_hub",
        "canonical_country",
        "normalized_name",
        "alliance_code",
    ],
}

AVIATION_ALIASES = {
    "iata_code": ["iata", "iata_airline", "airline_iata", "code_iata"],
    "icao_code": ["icao", "icao_airline", "airline_icao"],
}


def audit_aviation_schema(engine: Engine) -> dict[str, Any]:
    insp = inspect(engine)
    table = "airline_metadata"
    if table not in insp.get_table_names():
        logger.warning("[AVIATION_SCHEMA] table_missing=%s", table)
        return {
            "canonical_aviation_valid": False,
            "aviation_missing_columns": AVIATION_REQUIRED_COLUMNS[table],
            "aviation_aliases_detected": {},
            "aviation_orphan_columns": [],
            "aviation_semantic_drift": True,
            "aviation_backfill_status": "table_missing",
        }
    cols = physical_table_columns(engine, table)
    missing = [c for c in AVIATION_REQUIRED_COLUMNS[table] if c not in cols]
    aliases: dict[str, str] = {}
    for canonical, legacy in AVIATION_ALIASES.items():
        for alias in legacy:
            if alias in cols:
                aliases[canonical] = alias
                break
    report = {
        "canonical_aviation_valid": len(missing) == 0,
        "aviation_missing_columns": missing,
        "aviation_aliases_detected": aliases,
        "aviation_orphan_columns": sorted(
            c
            for c in cols
            if c
            not in set(AVIATION_REQUIRED_COLUMNS[table])
            | {
                "id",
                "airline_id",
                "airline_name",
                "slug",
                "callsign",
                "country",
                "region",
                "alliance_id",
                "airline_type",
                "star_rating",
                "is_low_cost",
                "is_premium",
                "fleet_size",
                "certifications",
                "hub_airports",
                "operational_labels",
                "skytrax_url",
                "enrichment_confidence",
                "normalization_confidence",
                "metadata_quality_score",
                "enrichment_status",
                "coverage_status",
                "source_confidence",
                "raw_metadata",
                "last_enriched_at",
                "last_seen_at",
                "created_at",
                "updated_at",
            }
        )[:30],
        "aviation_semantic_drift": len(missing) > 0,
        "aviation_backfill_status": "pending" if aliases else "not_needed",
    }
    logger.info(
        "[AVIATION_DRIFT] valid=%s missing=%s aliases=%s",
        report["canonical_aviation_valid"],
        report["aviation_missing_columns"],
        report["aviation_aliases_detected"],
    )
    return report


def repair_aviation_schema(engine: Engine) -> dict[str, Any]:
    """Idempotent physical reconciliation + alias backfill."""
    actions: list[str] = []
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS iata_code VARCHAR(16)"))
        conn.execute(text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS icao_code VARCHAR(16)"))
        conn.execute(text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS primary_hub VARCHAR(16)"))
        conn.execute(
            text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS canonical_country VARCHAR(120)")
        )
        conn.execute(
            text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(220)")
        )
        conn.execute(text("ALTER TABLE airline_metadata ADD COLUMN IF NOT EXISTS alliance_code VARCHAR(24)"))
        actions.extend(
            [
                "ensure_iata_code",
                "ensure_icao_code",
                "ensure_primary_hub",
                "ensure_canonical_country",
                "ensure_normalized_name",
                "ensure_alliance_code",
            ]
        )
        for alias in AVIATION_ALIASES["iata_code"]:
            conn.execute(
                text(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='airline_metadata' AND column_name='{alias}') THEN "
                    f"UPDATE airline_metadata SET iata_code=UPPER(TRIM({alias})) WHERE iata_code IS NULL AND {alias} IS NOT NULL AND TRIM({alias})<>''; "
                    "END IF; END $$;"
                )
            )
        for alias in AVIATION_ALIASES["icao_code"]:
            conn.execute(
                text(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='airline_metadata' AND column_name='{alias}') THEN "
                    f"UPDATE airline_metadata SET icao_code=UPPER(TRIM({alias})) WHERE icao_code IS NULL AND {alias} IS NOT NULL AND TRIM({alias})<>''; "
                    "END IF; END $$;"
                )
            )
        conn.execute(
            text(
                "UPDATE airline_metadata SET iata_code = UPPER(TRIM(raw_metadata->>'iata')) "
                "WHERE iata_code IS NULL AND raw_metadata->>'iata' IS NOT NULL AND TRIM(raw_metadata->>'iata')<>''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET iata_code = UPPER(TRIM(raw_metadata->>'iata_code')) "
                "WHERE iata_code IS NULL AND raw_metadata->>'iata_code' IS NOT NULL AND TRIM(raw_metadata->>'iata_code')<>''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET icao_code = UPPER(TRIM(raw_metadata->>'icao')) "
                "WHERE icao_code IS NULL AND raw_metadata->>'icao' IS NOT NULL AND TRIM(raw_metadata->>'icao')<>''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET canonical_country = COALESCE(canonical_country, NULLIF(TRIM(country), '')) "
                "WHERE canonical_country IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET normalized_name = COALESCE(normalized_name, NULLIF(TRIM(slug), '')) "
                "WHERE normalized_name IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET alliance_code = UPPER(TRIM(raw_metadata->>'alliance_code')) "
                "WHERE alliance_code IS NULL AND raw_metadata->>'alliance_code' IS NOT NULL AND TRIM(raw_metadata->>'alliance_code')<>''"
            )
        )
        actions.append("backfill_aliases")
        logger.warning("[AVIATION_BACKFILL] completed aliases iata/icao/raw_metadata")
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_airline_metadata_iata_code ON airline_metadata(iata_code)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_airline_metadata_icao_code ON airline_metadata(icao_code)")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_airline_metadata_normalized_name ON airline_metadata(normalized_name)"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_airline_metadata_slug ON airline_metadata(slug)"))
        actions.append("ensure_indexes")
    logger.warning("[AVIATION_REPAIR] actions=%s", actions)
    report = audit_aviation_schema(engine)
    report["aviation_backfill_status"] = "completed"
    report["actions"] = actions
    return report
