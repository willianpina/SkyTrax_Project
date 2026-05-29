"""Database schema validation, migration drift detection, and dev bootstrap."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Tables required for full pipeline operation (grouped by stage).
REQUIRED_TABLES: dict[str, list[str]] = {
    "core": ["airlines", "reviews", "nlp_results"],
    "metadata": ["review_intelligence"],
    "knowledge_graph": ["graph_nodes", "graph_edges", "fusion_signals"],
    "forecasting": ["forecast_snapshots"],
    "anomalies": ["anomaly_events"],
    "semantic": ["semantic_clusters", "executive_insights"],
    "operations": ["operational_refresh_runs"],
    "aviation": ["airline_metadata", "airport_metadata", "alliances"],
}

# Expected indexes (table -> index names). Missing indexes are warnings, not hard failures.
EXPECTED_INDEXES: dict[str, list[str]] = {
    "graph_nodes": ["ix_graph_nodes_type"],
    "graph_edges": ["ix_graph_edges_type", "ix_graph_edges_source", "ix_graph_edges_target"],
    "review_intelligence": ["ix_review_intel_review", "ix_review_intel_severity"],
    "forecast_snapshots": ["ix_forecast_snapshots_lookup"],
    "anomaly_events": ["ix_anomaly_events_airline", "ix_anomaly_events_type"],
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def all_required_tables() -> list[str]:
    seen: list[str] = []
    for tables in REQUIRED_TABLES.values():
        for t in tables:
            if t not in seen:
                seen.append(t)
    return seen


def check_tables(engine: Engine) -> dict[str, Any]:
    """Return missing and present required tables."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing: list[str] = []
    present: list[str] = []
    by_group: dict[str, dict[str, bool]] = {}

    for group, tables in REQUIRED_TABLES.items():
        by_group[group] = {}
        for table in tables:
            ok = table in existing
            by_group[group][table] = ok
            if ok:
                present.append(table)
            else:
                missing.append(table)

    return {
        "missing_tables": sorted(missing),
        "present_tables": sorted(present),
        "by_group": by_group,
        "complete": len(missing) == 0,
    }


def check_indexes(engine: Engine) -> dict[str, Any]:
    """Detect missing expected indexes."""
    inspector = inspect(engine)
    missing_indexes: list[dict[str, str]] = []
    invalid_indexes: list[dict[str, str]] = []

    for table, expected in EXPECTED_INDEXES.items():
        if table not in inspector.get_table_names():
            continue
        actual = {idx["name"] for idx in inspector.get_indexes(table)}
        for idx_name in expected:
            if idx_name not in actual:
                missing_indexes.append({"table": table, "index": idx_name})

    return {
        "missing_indexes": missing_indexes,
        "invalid_indexes": invalid_indexes,
        "ok": len(missing_indexes) == 0,
    }


def check_constraints(engine: Engine) -> dict[str, Any]:
    """Surface broken or missing FK targets (orphan table references)."""
    inspector = inspect(engine)
    broken: list[dict[str, str]] = []

    for table in ("graph_edges", "forecast_snapshots", "anomaly_events", "review_intelligence"):
        if table not in inspector.get_table_names():
            continue
        for fk in inspector.get_foreign_keys(table):
            referred = fk.get("referred_table")
            if referred and referred not in inspector.get_table_names():
                broken.append(
                    {
                        "table": table,
                        "constraint": fk.get("name") or "unnamed",
                        "referred_table": referred,
                    }
                )

    return {"broken_constraints": broken, "ok": len(broken) == 0}


def check_migrations(engine: Engine) -> dict[str, Any]:
    """Compare alembic_version with migration head."""
    head = _alembic_head_revision()
    current: str | None = None
    pending: list[str] = []

    try:
        with engine.connect() as conn:
            if "alembic_version" not in inspect(engine).get_table_names():
                return {
                    "current_revision": None,
                    "head_revision": head,
                    "pending_migrations": [head] if head else [],
                    "drift": True,
                    "alembic_table_missing": True,
                }
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            current = row[0] if row else None
    except Exception as exc:
        logger.warning("[MIGRATION] version check failed: %s", exc)
        return {
            "current_revision": current,
            "head_revision": head,
            "pending_migrations": [],
            "drift": True,
            "error": str(exc),
        }

    drift = current != head
    if drift and head:
        pending = [head] if current != head else []

    return {
        "current_revision": current,
        "head_revision": head,
        "pending_migrations": pending,
        "drift": drift,
        "alembic_table_missing": False,
    }


def _alembic_head_revision() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        if not ALEMBIC_INI.is_file():
            return None
        cfg = Config(str(ALEMBIC_INI))
        script = ScriptDirectory.from_config(cfg)
        return script.get_current_head()
    except Exception as exc:
        logger.debug("[MIGRATION] head resolution failed: %s", exc)
        return None


def run_migrations_upgrade(engine: Engine | None = None) -> dict[str, Any]:
    """Run alembic upgrade head (dev bootstrap)."""
    import time

    t0 = time.perf_counter()
    try:
        from alembic import command
        from alembic.config import Config

        if not ALEMBIC_INI.is_file():
            return {"success": False, "error": "alembic.ini not found", "duration_ms": 0}

        if engine is None:
            from database.session import engine as default_engine

            engine = default_engine

        from database.alembic_version_repair import ensure_alembic_version_capacity

        preflight = ensure_alembic_version_capacity(engine)
        if not preflight.get("alembic_safe") and not preflight.get("actions"):
            logger.error(
                "[ALEMBIC] version_num capacity insufficient (%s) — enable ALEMBIC_VERSION_AUTO_REPAIR",
                preflight.get("version_num_length"),
            )
            return {
                "success": False,
                "error": "alembic_version_truncation_risk",
                "alembic_preflight": preflight,
                "duration_ms": 0,
            }

        cfg = Config(str(ALEMBIC_INI))
        logger.warning("[BOOTSTRAP] Running alembic upgrade head")
        command.upgrade(cfg, "head")
        head = _alembic_head_revision()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.warning("[BOOTSTRAP] Migrations applied head=%s duration_ms=%d", head, duration_ms)
        return {
            "success": True,
            "head_revision": head,
            "duration_ms": duration_ms,
            "alembic_preflight": preflight,
        }
    except Exception as exc:
        logger.exception("[BOOTSTRAP] Migration upgrade failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }


def bootstrap_schema(engine: Engine) -> tuple[dict[str, Any], int]:
    """Validate → migrate if needed → revalidate. Returns (report, migration_duration_ms)."""
    import time

    t0 = time.perf_counter()
    migration_ms = 0

    logger.info("[SCHEMA] Bootstrap phase 1 — initial validation")
    report = validate_schema(engine, auto_migrate_dev=False)

    needs_bootstrap = report["missing_tables"] or report.get("migration_drift")
    if needs_bootstrap:
        logger.warning("[MIGRATION] Pending changes detected — running alembic upgrade head")
        br = run_migrations_upgrade(engine)
        migration_ms = int(br.get("duration_ms", 0))
        report["bootstrap_attempted"] = True
        report["bootstrap_result"] = br

        if br.get("success"):
            logger.info("[SCHEMA] Bootstrap phase 2 — revalidation after migration")
            from database.runtime_schema import refresh_sqlalchemy_runtime_after_migrations

            refresh_sqlalchemy_runtime_after_migrations(engine, reason="bootstrap_migration")
            report = validate_schema(engine, auto_migrate_dev=False)
            report["bootstrap_attempted"] = True
            report["bootstrap_result"] = br
        else:
            logger.error("[BOOTSTRAP] Migration failed: %s", br.get("error"))

    total_ms = int((time.perf_counter() - t0) * 1000)
    log_schema_report(report)
    return report, migration_ms or total_ms


def log_schema_report(report: dict[str, Any]) -> None:
    """Emit structured [SCHEMA] / [MIGRATION] / [BOOTSTRAP] logs from a report dict."""
    if report.get("missing_tables"):
        logger.warning(
            "[SCHEMA] Missing tables (%d): %s",
            len(report["missing_tables"]),
            ", ".join(report["missing_tables"][:12]),
        )
    else:
        logger.info("[SCHEMA] All required tables present (%d)", len(report.get("present_tables", [])))

    if report.get("migration_drift"):
        logger.warning(
            "[MIGRATION] Drift current=%s head=%s",
            report.get("current_revision"),
            report.get("head_revision"),
        )
    else:
        logger.info("[MIGRATION] At head revision=%s", report.get("current_revision"))

    if report.get("bootstrap_attempted"):
        br = report.get("bootstrap_result") or {}
        if br.get("success"):
            logger.warning(
                "[BOOTSTRAP] Success head=%s duration_ms=%s",
                br.get("head_revision"),
                br.get("duration_ms"),
            )
        else:
            logger.error("[BOOTSTRAP] Failed: %s", br.get("error"))


def check_semantic_drift(engine: Engine) -> dict[str, Any]:
    """ORM vs PostgreSQL column alignment (e.g. airline_metadata.iata_code)."""
    try:
        from database.schema_semantic import audit_semantic_schema, stages_blocked_by_semantic_drift

        audit = audit_semantic_schema(engine)
        audit["blocked_stages"] = stages_blocked_by_semantic_drift(audit)
        return audit
    except Exception as exc:
        logger.warning("[SCHEMA] semantic audit failed: %s", exc)
        return {"healthy": False, "error": str(exc), "tables": [], "blocked_stages": []}


def check_alembic_version_health(engine: Engine) -> dict[str, Any]:
    """Alembic version table capacity and migration chain validity."""
    from database.alembic_version_repair import (
        check_migration_chain,
        inspect_alembic_version_table,
    )

    info = inspect_alembic_version_table(engine)
    chain = check_migration_chain(engine)
    min_len = info.get("min_required_length") or 128
    col_len = info.get("version_num_length") or 0
    return {
        **info,
        **chain,
        "alembic_version_length": col_len,
        "alembic_safe": not info.get("truncation_risk", True) and col_len >= min_len,
    }


def validate_schema(engine: Engine, *, auto_migrate_dev: bool = False) -> dict[str, Any]:
    """Full schema health report."""
    tables = check_tables(engine)
    indexes = check_indexes(engine)
    constraints = check_constraints(engine)
    migrations = check_migrations(engine)
    semantic = check_semantic_drift(engine)
    alembic_health = check_alembic_version_health(engine)
    from database.aviation_schema import audit_aviation_schema, repair_aviation_schema

    aviation = audit_aviation_schema(engine)
    aviation_repair: dict[str, Any] | None = None

    bootstrap_attempted = False
    bootstrap_result: dict[str, Any] | None = None

    if auto_migrate_dev and (tables["missing_tables"] or migrations.get("drift")):
        bootstrap_attempted = True
        bootstrap_result = run_migrations_upgrade(engine)
        if bootstrap_result.get("success"):
            tables = check_tables(engine)
            indexes = check_indexes(engine)
            constraints = check_constraints(engine)
            migrations = check_migrations(engine)

    try:
        from app.config import get_settings

        settings = get_settings()
        should_auto_repair_aviation = (
            settings.aviation_schema_auto_repair
            and (settings.environment or "").lower() == "development"
            and aviation.get("aviation_semantic_drift")
        )
        if should_auto_repair_aviation:
            logger.warning("[AVIATION_REPAIR] Auto-repair enabled for development")
            aviation_repair = repair_aviation_schema(engine)
            aviation = audit_aviation_schema(engine)
    except Exception as exc:
        logger.warning("[AVIATION_DRIFT] aviation auto-repair skipped: %s", exc)

    alembic_safe = alembic_health.get("alembic_safe", True) and not alembic_health.get(
        "truncation_risk", False
    )
    chain_valid = alembic_health.get("migration_chain_valid", True)

    healthy = (
        tables["complete"]
        and constraints["ok"]
        and not migrations.get("drift", True)
        and semantic.get("healthy", True)
        and aviation.get("canonical_aviation_valid", True)
        and alembic_safe
        and chain_valid
    )

    try:
        from database.runtime_schema import get_runtime_schema_report

        runtime = get_runtime_schema_report(engine)
    except Exception as exc:
        logger.warning("[RUNTIME_SCHEMA] Runtime audit skipped: %s", exc)
        runtime = {
            "runtime_schema_consistent": False,
            "stale_reflection_detected": False,
            "runtime_metrics": {},
            "engine_generation": 0,
            "runtime_refresh_count": 0,
            "error": str(exc),
        }

    aviation_identity_health: dict[str, Any] = {}
    try:
        from sqlalchemy.orm import Session as SasSession

        from aviation.aviation_identity_governance import audit_aviation_identity_health

        with SasSession(bind=engine, autoflush=False, expire_on_commit=False) as gov_sess:
            aviation_identity_health = audit_aviation_identity_health(gov_sess)
            gov_sess.rollback()
    except Exception as exc:
        logger.warning("[AVIATION_IDENTITY] Governance audit skipped: %s", exc)
        aviation_identity_health = {"error": str(exc)}

    return {
        "healthy": healthy,
        "alembic_version_length": alembic_health.get("alembic_version_length"),
        "alembic_safe": alembic_safe,
        "migration_chain_valid": alembic_health.get("migration_chain_valid"),
        "alembic_health": alembic_health,
        "missing_tables": tables["missing_tables"],
        "present_tables": tables["present_tables"],
        "tables_by_group": tables["by_group"],
        "pending_migrations": migrations.get("pending_migrations", []),
        "current_revision": migrations.get("current_revision"),
        "head_revision": migrations.get("head_revision"),
        "migration_drift": migrations.get("drift", True),
        "missing_indexes": indexes["missing_indexes"],
        "broken_constraints": constraints["broken_constraints"],
        "semantic_drift": not semantic.get("healthy", True),
        "semantic_audit": semantic,
        "semantic_blocked_stages": semantic.get("blocked_stages", []),
        "canonical_aviation_valid": aviation.get("canonical_aviation_valid", False),
        "aviation_missing_columns": aviation.get("aviation_missing_columns", []),
        "aviation_aliases_detected": aviation.get("aviation_aliases_detected", {}),
        "aviation_semantic_drift": aviation.get("aviation_semantic_drift", True),
        "aviation_backfill_status": aviation.get("aviation_backfill_status", "unknown"),
        "aviation_schema_audit": aviation,
        "aviation_auto_repair": aviation_repair,
        "bootstrap_attempted": bootstrap_attempted,
        "bootstrap_result": bootstrap_result,
        "runtime_schema_consistent": runtime.get("runtime_schema_consistent", False),
        "stale_reflection_detected": runtime.get("stale_reflection_detected", False),
        "runtime_schema_tables": runtime.get("runtime_schema_tables", {}),
        "runtime_metrics": runtime.get("runtime_metrics", {}),
        "engine_generation": runtime.get("engine_generation", 0),
        "runtime_refresh_count": runtime.get("runtime_refresh_count", 0),
        "reflected_columns": runtime.get("runtime_schema_tables", {})
        .get("airline_metadata", {})
        .get("reflected_columns", []),
        "orm_columns": runtime.get("runtime_schema_tables", {})
        .get("airline_metadata", {})
        .get("orm_columns", []),
        "aviation_identity_health": aviation_identity_health,
        "canonical_identity_consistent": aviation_identity_health.get(
            "canonical_identity_consistent",
            False,
        ),
        "semantic_duplicates_detected": aviation_identity_health.get(
            "semantic_duplicates_detected",
            0,
        ),
    }


def log_schema_startup(engine: Engine, *, auto_migrate_dev: bool = False) -> dict[str, Any]:
    """Startup validator — logs [SCHEMA] / [MIGRATION] / [BOOTSTRAP] and returns report."""
    if auto_migrate_dev:
        report, _ = bootstrap_schema(engine)
    else:
        report = validate_schema(engine, auto_migrate_dev=False)
        log_schema_report(report)
    return report
