"""Semantic schema mapping — ORM columns vs PostgreSQL, legacy aliases, drift detection."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Legacy / alternate column names seen in the wild (table -> canonical -> aliases).
COLUMN_ALIASES: dict[str, dict[str, list[str]]] = {
    "airline_metadata": {
        "iata_code": ["iata", "iata_airline", "airline_iata", "code_iata"],
        "icao_code": ["icao", "icao_airline", "airline_icao"],
        "callsign": ["call_sign"],
        "primary_hub": ["hub", "main_hub"],
        "alliance_code": ["alliance", "alliance_iata"],
        "canonical_country": ["country_canonical"],
        "normalized_name": ["normalized_airline_name", "canonical_name"],
    },
    "airport_metadata": {
        "iata": ["iata_code", "code_iata"],
        "icao": ["icao_code"],
    },
}

# Canonical ORM columns required for full aviation pipeline operation.
REQUIRED_ORM_COLUMNS: dict[str, list[str]] = {
    "airline_metadata": [
        "iata_code",
        "icao_code",
        "callsign",
        "region",
        "primary_hub",
        "canonical_country",
        "normalized_name",
        "alliance_code",
    ],
    "airport_metadata": ["iata", "icao"],
    "review_intelligence": [
        "review_id",
        "disruptions",
        "quality_scores",
        "operational_severity",
        "intelligence_data",
    ],
}


def orm_column_names(model_class: type) -> list[str]:
    """SQLAlchemy mapped column names for a model."""
    return [c.key for c in model_class.__table__.columns]  # type: ignore[attr-defined]


def resolve_physical_column(table: str, canonical: str, db_columns: set[str]) -> str | None:
    """Return the physical column name in DB for a canonical ORM field."""
    if canonical in db_columns:
        return canonical
    for alias in COLUMN_ALIASES.get(table, {}).get(canonical, []):
        if alias in db_columns:
            return alias
    return None


def check_table_semantic_drift(
    engine: Engine,
    table: str,
    *,
    required: list[str] | None = None,
    model_class: type | None = None,
) -> dict[str, Any]:
    """Compare required canonical columns against physical schema."""
    from database.runtime_schema import physical_table_columns, reflected_table_columns

    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return {
            "table": table,
            "exists": False,
            "drift": True,
            "missing_columns": required or [],
            "legacy_mappings": {},
            "unmapped_db_columns": [],
        }

    db_cols = physical_table_columns(engine, table)
    reflected_cols = reflected_table_columns(engine, table)
    stale_reflection = bool(db_cols and db_cols != reflected_cols)
    if stale_reflection:
        logger.warning(
            "[REFLECTION] Semantic drift uses physical columns table=%s stale_reflection=true",
            table,
        )
    required_cols = required or REQUIRED_ORM_COLUMNS.get(table, [])
    if model_class is not None:
        orm_cols = set(orm_column_names(model_class))
        required_cols = list(set(required_cols) | orm_cols)

    missing: list[str] = []
    legacy_mappings: dict[str, str] = {}

    for canonical in required_cols:
        if canonical in db_cols:
            continue
        alias = resolve_physical_column(table, canonical, db_cols)
        if alias:
            legacy_mappings[canonical] = alias
        else:
            missing.append(canonical)

    aliases = COLUMN_ALIASES.get(table, {})
    unmapped = sorted(
        c
        for c in db_cols
        if c not in required_cols and c not in {a for aliases in aliases.values() for a in aliases}
    )

    return {
        "table": table,
        "exists": True,
        "drift": len(missing) > 0,
        "missing_columns": missing,
        "legacy_mappings": legacy_mappings,
        "physical_columns": sorted(db_cols),
        "reflected_columns": sorted(reflected_cols),
        "stale_reflection_detected": stale_reflection,
        "unmapped_db_columns": unmapped[:20],
    }


def audit_semantic_schema(engine: Engine) -> dict[str, Any]:
    """Audit aviation tables for ORM/DB semantic drift."""
    from database.models.aviation import AirlineMetadata, AirportMetadata
    from database.models.graph import ReviewIntelligence

    reports = [
        check_table_semantic_drift(
            engine,
            "airline_metadata",
            model_class=AirlineMetadata,
        ),
        check_table_semantic_drift(
            engine,
            "airport_metadata",
            model_class=AirportMetadata,
        ),
        check_table_semantic_drift(
            engine,
            "review_intelligence",
            model_class=ReviewIntelligence,
        ),
    ]
    drifted = [r for r in reports if r.get("drift")]
    return {
        "healthy": len(drifted) == 0,
        "tables": reports,
        "drifted_tables": [r["table"] for r in drifted],
        "column_aliases": COLUMN_ALIASES,
    }


def stages_blocked_by_semantic_drift(report: dict[str, Any]) -> list[str]:
    """Pipeline stages that must not run when critical tables are semantically incomplete."""
    blocked: list[str] = []
    for entry in report.get("tables", []):
        table = entry.get("table")
        if not entry.get("drift"):
            continue
        missing = set(entry.get("missing_columns") or [])
        if table == "review_intelligence" and missing:
            blocked.append("metadata")
            continue
        if table != "airline_metadata":
            continue
        if "iata_code" in missing or "icao_code" in missing:
            blocked.extend(
                [
                    "aviation_master",
                    "knowledge_graph",
                    "fusion",
                    "aviation_metadata",
                    "hub_intelligence",
                ]
            )
    return sorted(set(blocked))
