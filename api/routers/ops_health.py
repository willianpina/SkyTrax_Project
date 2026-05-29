"""Operational health endpoints — Redis-first, startup-cached (no per-request schema audit)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.health_snapshot import (
    get_integrity_health_fast,
    get_native_health_fast,
    get_schema_health_fast,
    refresh_integrity_from_redis,
)
from app.payload_serialization import safe_json_payload
from app.response_contract import fallback_operational_response, safe_json_response
from app.runtime_state import get_degraded_history, get_state, is_forecast_safe_mode

logger = logging.getLogger(__name__)

router = APIRouter(tags=["operations-health"])

_STATUS_BUDGET_S = 0.28


def _runtime_flags() -> dict[str, Any]:
    from app.runtime_state import is_subprocess_cooldown_active

    state = get_state()
    return {
        "forecast_safe_mode_active": is_forecast_safe_mode(),
        "forecast_safe_mode_env": os.getenv("FORECAST_SAFE_MODE", "0"),
        "forecast_isolated_env": os.getenv("FORECAST_ISOLATED", "1"),
        "schema_drift": bool(state.get("schema_drift")),
        "blocked_stages": state.get("blocked_stages", []),
        "native_crash_count": state.get("native_crash_count", 0),
        "subprocess_cooldown_active": is_subprocess_cooldown_active(),
        "degraded_history_count": len(get_degraded_history(50)),
    }


@router.get("/health/schema")
async def schema_health(response: Response):
    """Schema readiness from startup cache — no validate_schema() per request."""
    settings = get_settings()
    try:
        report = await asyncio.wait_for(asyncio.to_thread(get_schema_health_fast), timeout=_STATUS_BUDGET_S)
    except asyncio.TimeoutError:
        logger.warning("[ENDPOINT_TIMEOUT] /health/schema")
        report = get_schema_health_fast()
    except Exception as exc:
        logger.warning("[SAFE_RESPONSE] schema health failed: %s", exc)
        return fallback_operational_response(path="/health/schema", reason=str(exc)[:120])

    healthy = report.get("healthy", False)
    status = "ok" if healthy else "degraded"
    if settings.schema_block_on_drift and settings.environment == "production" and not healthy:
        status = "blocked"
        response.status_code = 503
    report["status"] = status
    report["auto_migrate_policy"] = _migrate_policy_label(settings)
    return report


@router.get("/health/native")
async def native_health(response: Response):
    """Native stack from startup cache — no subprocess probes per request."""
    try:
        report = await asyncio.wait_for(asyncio.to_thread(get_native_health_fast), timeout=_STATUS_BUDGET_S)
    except asyncio.TimeoutError:
        logger.warning("[ENDPOINT_TIMEOUT] /health/native")
        report = get_native_health_fast()
    except Exception as exc:
        logger.warning("[SAFE_RESPONSE] native health failed: %s", exc)
        return fallback_operational_response(path="/health/native", reason=str(exc)[:120])

    if report.get("any_segfault_detected"):
        response.status_code = 503
    return report


@router.get("/health/pipeline")
async def pipeline_health():
    """Aggregated operational readiness: pipeline + schema + native + startup (JSON-safe)."""
    from api.pipeline_health_service import build_pipeline_health_payload

    settings = get_settings()
    flags = _runtime_flags()
    migrate_policy = _migrate_policy_label(settings)

    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(
                build_pipeline_health_payload,
                settings=settings,
                runtime_flags=flags,
                migrate_policy=migrate_policy,
            ),
            timeout=2.5,
        )
        logger.info("[PIPELINE_HEALTH] payload ready readiness=%s", payload.get("readiness"))
        return payload
    except Exception as exc:
        logger.exception("[PIPELINE_HEALTH] build failed: %s", exc)
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_pipeline_health_failures", 1.0)
            record_worker_metric("skytrax_payload_serialization_errors", 1.0)
        except Exception:
            pass
        fallback = safe_json_payload(
            {
                "status": "degraded",
                "readiness": "degraded",
                "environment": settings.environment,
                "degraded": True,
                "pipeline": {"running": False, "stage": "unknown"},
                "schema": {"healthy": False, "summary_source": "fallback"},
                "native": {"safe_mode_active": flags.get("forecast_safe_mode_active", False)},
                "runtime": flags,
                "runtime_health": {},
                "startup": None,
                "blocked_stages": [],
                "degraded_history": [],
                "auto_migrate_policy": migrate_policy,
                **_empty_governance_fields(),
                "payload_safe": False,
                "error": str(exc)[:500],
            },
            context="pipeline_health_fallback",
        )
        return JSONResponse(status_code=200, content=fallback)


def _empty_governance_fields() -> dict[str, Any]:
    return {
        "integrity_reconciled": False,
        "authoritative_kpis": {},
        "canonical_kpis": {},
        "accumulated_kpis": {},
        "delta_kpis": {},
        "kpi_governance": {},
        "kpi_lineage": {},
        "metric_lineage": {},
        "metric_semantics": {},
        "integrity_consistent": True,
        "runtime_authoritative": False,
        "stale_kpis_removed": 0,
        "governance_source": "fallback",
    }


@router.get("/health/integrity")
async def pipeline_integrity(full: bool = Query(False, description="Run deep DB audit (slow)")):
    """Integrity from Redis snapshot by default; optional full DB audit via ?full=1."""
    if full:
        return await _pipeline_integrity_full()

    try:
        body = await asyncio.wait_for(asyncio.to_thread(get_integrity_health_fast), timeout=_STATUS_BUDGET_S)
    except asyncio.TimeoutError:
        logger.warning("[ENDPOINT_TIMEOUT] /health/integrity")
        body = get_integrity_health_fast()
    except Exception as exc:
        logger.warning("[SAFE_RESPONSE] integrity fast path failed: %s", exc)
        return fallback_operational_response(path="/health/integrity", reason=str(exc)[:120])

    return safe_json_payload(body, context="pipeline_integrity_fast")


async def _pipeline_integrity_full():
    """Deep integrity audit — background-only style, bounded thread timeout."""
    from analytics.pipeline_integrity import (
        build_authoritative_integrity,
        integrity_snapshot_cleanup,
        load_authoritative_integrity_snapshot,
        load_live_kpis_from_redis,
        signal_dependency_report,
        validate_graph_consistency,
        validate_snapshot_integrity,
    )
    from database.session import SessionLocal

    def _run():
        integrity_snapshot_cleanup()
        live_kpis = load_live_kpis_from_redis()
        cached = load_authoritative_integrity_snapshot()
        session = SessionLocal()
        try:
            audit = build_authoritative_integrity(
                session,
                live_kpis=live_kpis or (cached or {}).get("authoritative_kpis"),
            )
            audit["graph_validation"] = validate_graph_consistency(session)
            audit["snapshot_validation"] = validate_snapshot_integrity(session)
            audit["signal_dependencies"] = signal_dependency_report(session)
            if cached and cached.get("cached_at"):
                audit["integrity_snapshot_cached_at"] = cached.get("cached_at")
            return {
                "status": "ok" if audit.get("healthy") else "degraded",
                "readiness": "ready" if audit.get("integrity_consistent", True) else "degraded",
                "summary_source": "full_db_audit",
                **audit,
            }
        finally:
            session.close()

    try:
        body = await asyncio.wait_for(asyncio.to_thread(_run), timeout=12.0)
        return safe_json_payload(body, context="pipeline_integrity_full")
    except asyncio.TimeoutError:
        logger.warning("[ENDPOINT_TIMEOUT] /health/integrity?full=1")
        refresh_integrity_from_redis()
        return safe_json_response(
            {**get_integrity_health_fast(), "full_audit": "timeout", "summary_source": "redis_fallback"},
            status_code=200,
            path="/health/integrity",
        )


def _migrate_policy_label(settings) -> str:
    env = (settings.environment or "").lower()
    if env == "production":
        return "never_auto_migrate"
    if env == "development":
        return "auto_migrate_if_enabled" if settings.schema_auto_migrate_dev else "validate_only"
    if env == "staging":
        return "auto_migrate_if_staging_flag" if settings.schema_auto_migrate_staging else "validate_only"
    return "validate_only"
