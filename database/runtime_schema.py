"""Runtime schema consistency — physical DB vs reflection vs ORM.

Uses ``information_schema`` as the source of truth for physical columns so
stale SQLAlchemy Inspector caches cannot false-positive aviation drift.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from database.schema_semantic import (
    REQUIRED_ORM_COLUMNS,
    orm_column_names,
    resolve_physical_column,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_RUNTIME_METRICS: dict[str, int] = {
    "runtime_schema_mismatch": 0,
    "metadata_refresh_count": 0,
    "engine_dispose_count": 0,
    "stale_reflection_detected": 0,
    "prepared_statement_conflicts": 0,
    "runtime_refresh_count": 0,
}

_STALE_ERROR_MARKERS = (
    "undefinedcolumn",
    "does not exist",
    "unknown column",
    "no such column",
)

_PREPARED_STMT_MARKERS = (
    "duplicatepreparedstatement",
    "prepared statement",
)


def runtime_metrics() -> dict[str, int]:
    """Copy of process-local runtime schema counters."""
    return dict(_RUNTIME_METRICS)


def get_engine_generation() -> int:
    from database.session import engine_generation

    return engine_generation()


def physical_table_columns(
    engine: Engine,
    table: str,
    *,
    schema: str = "public",
) -> set[str]:
    """Authoritative column names from PostgreSQL information_schema."""
    if engine.dialect.name == "sqlite":
        insp = sa_inspect(engine)
        if table not in insp.get_table_names():
            return set()
        return {c["name"] for c in insp.get_columns(table)}

    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"schema": schema, "table": table}).fetchall()
    return {row[0] for row in rows}


def reflected_table_columns(engine: Engine, table: str) -> set[str]:
    """SQLAlchemy Inspector columns (may be stale after DDL)."""
    insp = sa_inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def clear_inspector_cache(engine: Engine) -> None:
    """Drop cached reflection on the bound inspector, if supported."""
    try:
        insp = sa_inspect(engine)
        if hasattr(insp, "clear"):
            insp.clear()
            logger.info("[REFLECTION] Inspector cache cleared")
    except Exception as exc:
        logger.debug("[REFLECTION] Inspector clear skipped: %s", exc)


def invalidate_sqlalchemy_runtime(
    engine: Engine | None = None,
    *,
    reason: str = "unspecified",
) -> dict[str, Any]:
    """Dispose connection pool, clear inspector cache, bump engine generation."""
    from database.session import dispose_sqlalchemy_runtime

    _RUNTIME_METRICS["metadata_refresh_count"] += 1
    _RUNTIME_METRICS["runtime_refresh_count"] += 1
    logger.warning("[METADATA_REFRESH] reason=%s", reason)

    result = dispose_sqlalchemy_runtime(reason=reason)
    _RUNTIME_METRICS["engine_dispose_count"] += 1

    bound = engine or result.get("engine")
    if bound is not None:
        clear_inspector_cache(bound)

    logger.warning(
        "[ENGINE_DISPOSE] reason=%s generation=%s",
        reason,
        result.get("engine_generation"),
    )
    return result


def refresh_sqlalchemy_runtime_after_migrations(
    engine: Engine | None = None,
    *,
    reason: str = "post_migration",
) -> dict[str, Any]:
    """Mandatory post-migration hook: pools + reflection must match physical DB."""
    return invalidate_sqlalchemy_runtime(engine, reason=reason)


def validate_runtime_schema_consistency(
    engine: Engine,
    table: str,
    *,
    required: list[str] | None = None,
    model_class: type | None = None,
    schema: str = "public",
) -> dict[str, Any]:
    """Compare physical, reflected, and ORM column sets."""
    required_cols = list(required or REQUIRED_ORM_COLUMNS.get(table, []))
    if model_class is not None:
        orm_cols = set(orm_column_names(model_class))
        required_cols = sorted(set(required_cols) | orm_cols)
    else:
        orm_cols = set()

    physical = physical_table_columns(engine, table, schema=schema)
    reflected = reflected_table_columns(engine, table)

    missing_physical: list[str] = []
    legacy_mappings: dict[str, str] = {}
    for canonical in required_cols:
        if canonical in physical:
            continue
        alias = resolve_physical_column(table, canonical, physical)
        if alias:
            legacy_mappings[canonical] = alias
        else:
            missing_physical.append(canonical)

    stale_pairs: list[dict[str, str]] = []
    for canonical in required_cols:
        in_physical = canonical in physical or canonical in legacy_mappings
        in_reflected = canonical in reflected or (
            legacy_mappings.get(canonical) in reflected if canonical in legacy_mappings else False
        )
        if in_physical and not in_reflected:
            stale_pairs.append({"column": canonical, "physical": "present", "reflected": "missing"})

    stale_reflection = len(stale_pairs) > 0
    if stale_reflection:
        _RUNTIME_METRICS["stale_reflection_detected"] += 1
        logger.warning(
            "[RUNTIME_SCHEMA] Stale reflection table=%s pairs=%s",
            table,
            stale_pairs[:5],
        )

    runtime_schema_consistent = len(missing_physical) == 0 and not stale_reflection
    if not runtime_schema_consistent:
        _RUNTIME_METRICS["runtime_schema_mismatch"] += 1

    return {
        "table": table,
        "runtime_schema_consistent": runtime_schema_consistent,
        "stale_reflection_detected": stale_reflection,
        "stale_reflection_pairs": stale_pairs,
        "physical_columns": sorted(physical),
        "reflected_columns": sorted(reflected),
        "orm_columns": sorted(orm_cols) if orm_cols else sorted(required_cols),
        "missing_physical_columns": missing_physical,
        "legacy_mappings": legacy_mappings,
        "engine_generation": get_engine_generation(),
    }


def get_runtime_schema_report(engine: Engine) -> dict[str, Any]:
    """Audit aviation-critical tables for health endpoints."""
    from database.models.aviation import AirlineMetadata, AirportMetadata

    airline = validate_runtime_schema_consistency(
        engine,
        "airline_metadata",
        model_class=AirlineMetadata,
    )
    airport = validate_runtime_schema_consistency(
        engine,
        "airport_metadata",
        model_class=AirportMetadata,
    )
    metrics = runtime_metrics()
    consistent = airline["runtime_schema_consistent"] and airport["runtime_schema_consistent"]
    return {
        "runtime_schema_consistent": consistent,
        "runtime_schema_tables": {
            "airline_metadata": airline,
            "airport_metadata": airport,
        },
        "stale_reflection_detected": (
            airline["stale_reflection_detected"] or airport["stale_reflection_detected"]
        ),
        "runtime_metrics": metrics,
        "engine_generation": get_engine_generation(),
        "runtime_refresh_count": metrics["runtime_refresh_count"],
    }


def aviation_iata_ready(engine: Engine) -> bool:
    """True when iata_code (or legacy alias) exists in physical PostgreSQL."""
    physical = physical_table_columns(engine, "airline_metadata")
    if "iata_code" in physical:
        return True
    return resolve_physical_column("airline_metadata", "iata_code", physical) is not None


def ensure_aviation_runtime_ready(
    engine: Engine,
    *,
    allow_retry: bool = True,
) -> dict[str, Any]:
    """Verify aviation schema at runtime; self-heal stale reflection once."""
    from database.models.aviation import AirlineMetadata

    report = validate_runtime_schema_consistency(
        engine,
        "airline_metadata",
        model_class=AirlineMetadata,
        required=["iata_code"],
    )
    report["iata_code_ready"] = aviation_iata_ready(engine)

    if report["iata_code_ready"] and not report["stale_reflection_detected"]:
        logger.info("[AVIATION_RUNTIME] Ready generation=%s", report["engine_generation"])
        return report

    if report["stale_reflection_detected"] and allow_retry:
        logger.warning("[AVIATION_RUNTIME] Stale reflection — refreshing runtime once")
        invalidate_sqlalchemy_runtime(engine, reason="aviation_stale_reflection")
        from database.session import engine as live_engine

        report = validate_runtime_schema_consistency(
            live_engine,
            "airline_metadata",
            model_class=AirlineMetadata,
            required=["iata_code"],
        )
        report["iata_code_ready"] = aviation_iata_ready(live_engine)
        report["runtime_repaired"] = True
        return report

    if not report["iata_code_ready"]:
        logger.error(
            "[AVIATION_RUNTIME] iata_code unavailable physical=%s",
            report.get("physical_columns", [])[:12],
        )
    return report


def _normalize_error(exc: BaseException) -> str:
    return str(exc).lower()


def is_stale_schema_error(exc: BaseException) -> bool:
    msg = _normalize_error(exc)
    if isinstance(exc, ProgrammingError):
        return True
    return any(marker in msg for marker in _STALE_ERROR_MARKERS)


def is_prepared_statement_conflict(exc: BaseException) -> bool:
    msg = _normalize_error(exc)
    if any(marker in msg for marker in _PREPARED_STMT_MARKERS):
        _RUNTIME_METRICS["prepared_statement_conflicts"] += 1
        logger.warning("[PREPARED_STATEMENT] Conflict detected: %s", exc)
        return True
    return False


def runtime_schema_retry_once(func: F) -> F:
    """Execute callable once more after runtime invalidation on schema errors."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if not (is_stale_schema_error(exc) or is_prepared_statement_conflict(exc)):
                raise
            logger.warning("[SQLALCHEMY_CACHE] Retrying after schema error: %s", exc)
            invalidate_sqlalchemy_runtime(reason=f"retry:{func.__name__}")
            return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def reconcile_runtime_with_physical(engine: Engine) -> dict[str, Any]:
    """Refresh pools when reflection lags physical schema; return aviation report."""
    airline_physical = physical_table_columns(engine, "airline_metadata")
    airline_reflected = reflected_table_columns(engine, "airline_metadata")
    if airline_physical and airline_physical != airline_reflected:
        logger.warning("[RUNTIME_SCHEMA] Physical/reflected mismatch — refreshing runtime")
        invalidate_sqlalchemy_runtime(engine, reason="physical_reflected_mismatch")
        from database.session import engine as live_engine

        engine = live_engine
    return ensure_aviation_runtime_ready(engine, allow_retry=False)
