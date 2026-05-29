"""Startup / Redis-first health snapshots — no per-request schema reflection."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_schema_snapshot: dict[str, Any] = {}
_native_snapshot: dict[str, Any] = {}
_integrity_snapshot: dict[str, Any] | None = None
_seeded_at: float | None = None


def seed_from_startup_report(report: Any | None = None) -> None:
    """Cache schema + native from startup governance (called once at lifespan)."""
    global _schema_snapshot, _native_snapshot, _seeded_at
    if report is None:
        from app.startup_governance import get_last_startup_report

        report = get_last_startup_report()
    if report is None:
        logger.warning("[HEALTH_SNAPSHOT] no startup report to seed")
        return

    schema = dict(getattr(report, "schema", None) or {})
    native = dict(getattr(report, "native", None) or {})
    _schema_snapshot = schema
    _native_snapshot = native
    _seeded_at = time.time()
    logger.info(
        "[HEALTH_SNAPSHOT] seeded schema_healthy=%s native_keys=%d",
        schema.get("healthy"),
        len(native),
    )


def refresh_integrity_from_redis() -> dict[str, Any] | None:
    """Load integrity snapshot from Redis (no DB audit on hot path)."""
    global _integrity_snapshot
    try:
        from analytics.pipeline_integrity import load_authoritative_integrity_snapshot

        _integrity_snapshot = load_authoritative_integrity_snapshot()
    except Exception as exc:
        logger.warning("[HEALTH_SNAPSHOT] integrity redis load failed: %s", exc)
        _integrity_snapshot = None
    return _integrity_snapshot


def get_schema_health_fast() -> dict[str, Any]:
    """Schema summary from startup cache only."""
    from app.runtime_state import get_state
    from app.config import get_settings

    state = get_state()
    schema = dict(_schema_snapshot)
    if not schema:
        schema = dict((state.get("startup_report") or {}).get("schema") or {})

    healthy = bool(schema.get("healthy", not state.get("schema_drift", False)))
    settings = get_settings()

    return {
        "status": "ok" if healthy else "degraded",
        "readiness": "ready" if healthy else "not_ready",
        "environment": settings.environment,
        "healthy": healthy,
        "migration_drift": schema.get("migration_drift", state.get("schema_drift")),
        "missing_tables": list(schema.get("missing_tables") or []),
        "pending_migrations": list(schema.get("pending_migrations") or []),
        "current_revision": schema.get("current_revision"),
        "head_revision": schema.get("head_revision"),
        "semantic_drift": schema.get("semantic_drift", False),
        "alembic_safe": schema.get("alembic_safe", True),
        "migration_chain_valid": schema.get("migration_chain_valid"),
        "summary_source": "startup_cache" if _schema_snapshot else "runtime_flags",
        "snapshot_age_s": int(time.time() - _seeded_at) if _seeded_at else None,
    }


def get_native_health_fast() -> dict[str, Any]:
    """Native stack from startup cache + runtime flags (no subprocess probes)."""
    from app.runtime_state import get_state, is_forecast_safe_mode

    state = get_state()
    native = dict(_native_snapshot)
    if not native:
        sr = state.get("startup_report")
        if isinstance(sr, dict):
            native = dict(sr.get("native") or {})

    flags = {
        "forecast_safe_mode_active": is_forecast_safe_mode(),
        "native_crash_count": state.get("native_crash_count", 0),
    }
    degraded = bool(native.get("any_segfault_detected")) or flags["forecast_safe_mode_active"]

    return {
        "status": "degraded" if degraded else "ok",
        "readiness": "degraded" if degraded else "ready",
        "native_fallback_active": flags["forecast_safe_mode_active"],
        "summary_source": "startup_cache" if _native_snapshot else "runtime_flags",
        "snapshot_age_s": int(time.time() - _seeded_at) if _seeded_at else None,
        **native,
        **flags,
    }


def get_integrity_health_fast() -> dict[str, Any]:
    """Integrity from Redis snapshot + live KPIs — no full DB build_authoritative_integrity."""
    from analytics.pipeline_integrity import (
        load_authoritative_integrity_snapshot,
        load_live_kpis_from_redis,
        reconcile_integrity_metrics,
    )

    cached = load_authoritative_integrity_snapshot() or _integrity_snapshot
    live_kpis = load_live_kpis_from_redis() or {}

    if not cached:
        return {
            "status": "degraded",
            "readiness": "degraded",
            "healthy": False,
            "integrity_consistent": True,
            "summary_source": "empty_snapshot",
            "table_counts": {},
            "authoritative_kpis": live_kpis,
        }

    if cached.get("table_counts"):
        merged = reconcile_integrity_metrics(
            table_counts=cached.get("table_counts"),
            coverage=cached.get("coverage"),
            live_kpis=live_kpis,
            stage_results=None,
        )
        audit = {**cached, **merged}
    else:
        audit = dict(cached)

    healthy = bool(audit.get("healthy", audit.get("integrity_consistent", True)))
    return {
        "status": "ok" if healthy else "degraded",
        "readiness": "ready" if audit.get("integrity_consistent", True) else "degraded",
        "summary_source": "redis_snapshot",
        "integrity_snapshot_cached_at": cached.get("cached_at"),
        **audit,
    }
