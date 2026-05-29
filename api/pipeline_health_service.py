"""Fast, JSON-safe builder for pipeline health (no full schema audit per request)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.payload_serialization import safe_json_payload, safe_json_value
from app.runtime_state import get_degraded_history, get_state
from app.startup_governance import StartupReport, get_last_startup_report

logger = logging.getLogger(__name__)

_EMPTY_GOVERNANCE: dict[str, Any] = {
    "authoritative_kpis": {},
    "canonical_kpis": {},
    "accumulated_kpis": {},
    "delta_kpis": {},
    "kpi_governance": {},
    "kpi_lineage": {},
    "metric_lineage": {},
    "metric_semantics": {},
    "integrity_reconciled": False,
    "integrity_consistent": True,
    "runtime_authoritative": False,
    "governance_source": "none",
}


def _startup_dict(startup: StartupReport | None, runtime: dict[str, Any]) -> dict[str, Any] | None:
    if startup is not None:
        try:
            return startup.to_dict()
        except Exception:
            pass
    raw = runtime.get("startup_report")
    if isinstance(raw, dict):
        return raw
    return None


def _schema_summary_from_startup(
    startup: StartupReport | None,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Reuse startup-time schema audit — avoid validate_schema() on every health poll."""
    schema_blob: dict[str, Any] = {}
    if startup is not None:
        schema_blob = dict(startup.schema or {})
    else:
        sr = runtime.get("startup_report")
        if isinstance(sr, dict):
            schema_blob = dict(sr.get("schema") or {})

    av_id = schema_blob.get("aviation_identity_health") or {}
    if not isinstance(av_id, dict):
        av_id = {}

    healthy = bool(schema_blob.get("healthy", not runtime.get("schema_drift", False)))

    return {
        "healthy": healthy,
        "migration_drift": schema_blob.get("migration_drift", runtime.get("schema_drift")),
        "missing_tables": list(schema_blob.get("missing_tables") or []),
        "pending_migrations": list(schema_blob.get("pending_migrations") or []),
        "current_revision": schema_blob.get("current_revision"),
        "head_revision": schema_blob.get("head_revision"),
        "canonical_aviation_valid": schema_blob.get("canonical_aviation_valid"),
        "aviation_missing_columns": list(schema_blob.get("aviation_missing_columns") or []),
        "aviation_aliases_detected": dict(schema_blob.get("aviation_aliases_detected") or {}),
        "aviation_backfill_status": schema_blob.get("aviation_backfill_status"),
        "aviation_semantic_drift": schema_blob.get("aviation_semantic_drift"),
        "runtime_schema_consistent": schema_blob.get(
            "runtime_schema_consistent",
            not runtime.get("schema_drift", False),
        ),
        "stale_reflection_detected": bool(schema_blob.get("stale_reflection_detected", False)),
        "engine_generation": int(schema_blob.get("engine_generation") or 0),
        "runtime_refresh_count": int(schema_blob.get("runtime_refresh_count") or 0),
        "aviation_identity_health": av_id,
        "canonical_identity_consistent": av_id.get("canonical_identity_consistent"),
        "semantic_duplicates_detected": av_id.get("semantic_duplicates_detected"),
        "slug_collision_rate": av_id.get("slug_collision_rate"),
        "identity_merge_count": av_id.get("identity_merge_count"),
        "summary_source": "startup_cache" if schema_blob else "runtime_flags",
    }


def _orchestration_snapshot(pipeline: dict[str, Any]) -> dict[str, Any]:
    """Queue depth, lifecycle, and worker heartbeat for async refresh observability."""
    out: dict[str, Any] = {
        "queue_depth": -1,
        "worker_alive": False,
        "lifecycle_state": pipeline.get("pipeline_status") or pipeline.get("stage"),
        "active_operation_id": pipeline.get("operation_id"),
        "last_heartbeat_at": pipeline.get("last_heartbeat_at")
        or (pipeline.get("heartbeat") or {}).get("last_heartbeat_at"),
    }
    try:
        from api.operations_dispatch import get_redis_and_queue
        from rq import Worker

        conn, queue = get_redis_and_queue()
        out["queue_depth"] = int(queue.count)
        workers = Worker.all(connection=conn)
        out["worker_alive"] = len(workers) > 0
        out["workers"] = [{"name": w.name, "state": w.get_state()} for w in workers]
    except Exception as exc:
        out["orchestration_error"] = str(exc)[:200]
    try:
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        active = OperationLifecycleManager().get_active_operation()
        if active:
            out["lifecycle_state"] = active.get("lifecycle_state")
            out["active_operation_id"] = active.get("operation_id")
    except Exception:
        pass
    return out


def _quick_pipeline_status() -> dict[str, Any]:
    """Redis pipeline status only — no DB integrity attach (keeps health fast)."""
    try:
        from worker.orchestration.refresh_pipeline import REDIS_STATUS_KEY, _redis

        r = _redis()
        raw = r.get(REDIS_STATUS_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                data.setdefault(
                    "running",
                    data.get("stage") not in ("idle", "completed", "completed_degraded", "failed", None),
                )
                return data
    except Exception as exc:
        logger.warning("[PIPELINE_HEALTH] quick status failed: %s", exc)
    return {"running": False, "stage": "idle", "progress": 0}


def _stage_error_text(stage_results: dict[str, Any] | None, stage: str) -> str:
    blob = (stage_results or {}).get(stage) or {}
    return str(blob.get("error") or "")


def _is_aviation_identity_conflict_error(text: str) -> bool:
    t = text.lower()
    if "uniqueviolation" in t or "unique violation" in t:
        return "slug" in t or "airline_metadata_slug" in t
    return "duplicate key" in t and ("slug" in t or "airline_metadata" in t)


def _extract_governance_fields(report: dict[str, Any], *, source: str) -> dict[str, Any]:
    authoritative = (
        report.get("canonical_kpis")
        or report.get("accumulated_kpis")
        or report.get("authoritative_kpis")
        or {}
    )
    accumulated = report.get("accumulated_kpis") or authoritative
    lineage = report.get("metric_lineage") or report.get("kpi_lineage") or {}
    return {
        "authoritative_kpis": dict(authoritative) if isinstance(authoritative, dict) else {},
        "canonical_kpis": dict(authoritative) if isinstance(authoritative, dict) else {},
        "accumulated_kpis": dict(accumulated) if isinstance(accumulated, dict) else {},
        "delta_kpis": dict(report.get("delta_kpis") or {})
        if isinstance(report.get("delta_kpis"), dict)
        else {},
        "kpi_governance": dict(report.get("kpi_governance") or {})
        if isinstance(report.get("kpi_governance"), dict)
        else {},
        "kpi_lineage": dict(lineage) if isinstance(lineage, dict) else {},
        "metric_lineage": dict(lineage) if isinstance(lineage, dict) else {},
        "metric_semantics": dict(report.get("metric_semantics") or {})
        if isinstance(report.get("metric_semantics"), dict)
        else {},
        "integrity_reconciled": bool(report.get("integrity_reconciled")),
        "integrity_consistent": bool(report.get("integrity_consistent", True)),
        "runtime_authoritative": bool(authoritative),
        "governance_source": source,
    }


def resolve_pipeline_governance(
    pipeline: dict[str, Any],
) -> dict[str, Any]:
    """Governance from Redis snapshot + live KPIs — no full DB audit on health path."""
    try:
        from analytics.pipeline_integrity import (
            load_authoritative_integrity_snapshot,
            load_live_kpis_from_redis,
            reconcile_integrity_metrics,
        )

        live_kpis = load_live_kpis_from_redis() or (
            pipeline.get("kpis") if isinstance(pipeline.get("kpis"), dict) else {}
        )
        stage_results = (
            pipeline.get("stage_results") if isinstance(pipeline.get("stage_results"), dict) else {}
        )
        cached = load_authoritative_integrity_snapshot()

        if cached and isinstance(cached, dict):
            if cached.get("table_counts"):
                merged = reconcile_integrity_metrics(
                    table_counts=cached.get("table_counts"),
                    coverage=cached.get("coverage"),
                    live_kpis=live_kpis,
                    stage_results=stage_results,
                )
                report = {**cached, **merged}
            else:
                report = cached
            gov = _extract_governance_fields(report, source="redis_snapshot")
            if gov["authoritative_kpis"] or gov["metric_lineage"]:
                logger.debug("[KPI_SERIALIZATION] governance from redis snapshot")
                return gov

        embedded = pipeline.get("integrity")
        if isinstance(embedded, dict) and (
            embedded.get("canonical_kpis") or embedded.get("accumulated_kpis")
        ):
            gov = _extract_governance_fields(embedded, source="pipeline_integrity_embedded")
            logger.debug("[LINEAGE_SERIALIZATION] governance from pipeline integrity blob")
            return gov
    except Exception as exc:
        logger.warning("[PIPELINE_HEALTH] governance resolve skipped: %s", exc)
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_pipeline_health_failures", 1.0)
        except Exception:
            pass

    return dict(_EMPTY_GOVERNANCE)


def build_pipeline_health_payload(
    *,
    settings: Any,
    runtime_flags: dict[str, Any],
    migrate_policy: str,
) -> dict[str, Any]:
    """Assemble pipeline health response (sync — call via thread pool from async route)."""
    logger.info("[PIPELINE_HEALTH] building payload")
    runtime = get_state()
    startup = get_last_startup_report()
    schema = _schema_summary_from_startup(startup, runtime)
    pipeline = _quick_pipeline_status()
    orchestration = _orchestration_snapshot(pipeline)
    governance = resolve_pipeline_governance(pipeline)

    schema_ok = bool(schema.get("healthy", False))
    pipeline_running = bool(pipeline.get("running", False))
    pipeline_degraded = pipeline.get("pipeline_status") in (
        "running_degraded",
        "stalled",
        "completed_degraded",
    )
    runtime_schema_consistent = bool(schema.get("runtime_schema_consistent", False))
    canonical_aviation_valid = bool(schema.get("canonical_aviation_valid", False))
    stage_results = pipeline.get("stage_results") if isinstance(pipeline.get("stage_results"), dict) else {}

    impossible_aviation_state = (
        canonical_aviation_valid
        and runtime_schema_consistent
        and any(
            "iata_code" in _stage_error_text(stage_results, stage).lower()
            and not _is_aviation_identity_conflict_error(_stage_error_text(stage_results, stage))
            for stage in ("aviation_master", "fusion")
        )
    )

    readiness = "ready"
    if not schema_ok or runtime_flags.get("schema_drift"):
        readiness = "degraded"
    if settings.schema_block_on_drift and settings.environment == "production" and not schema_ok:
        readiness = "blocked"
    if runtime_flags.get("subprocess_cooldown_active"):
        readiness = "degraded"

    startup_payload = _startup_dict(startup, runtime)

    payload = {
        "status": readiness,
        "readiness": readiness,
        "environment": settings.environment,
        "degraded": readiness != "ready",
        "pipeline": {
            "running": pipeline_running,
            "stage": pipeline.get("stage"),
            "progress": pipeline.get("progress"),
            "pipeline_status": pipeline.get("pipeline_status"),
            "operation_id": pipeline.get("operation_id"),
            "degraded": pipeline_degraded,
            "false_degraded_detected": impossible_aviation_state,
            **orchestration,
        },
        "orchestration": orchestration,
        "schema": schema,
        "native": {
            "safe_mode_active": runtime_flags["forecast_safe_mode_active"],
            "native_crash_count": runtime_flags["native_crash_count"],
            "apple_silicon": (startup_payload or {}).get("native", {}).get("apple_silicon")
            if isinstance(startup_payload, dict)
            else None,
        },
        "runtime": runtime_flags,
        "runtime_health": {
            "runtime_schema_consistent": runtime_schema_consistent,
            "canonical_aviation_valid": canonical_aviation_valid,
            "impossible_aviation_state": impossible_aviation_state,
        },
        "startup": startup_payload,
        "blocked_stages": list(runtime.get("blocked_stages") or []),
        "degraded_history": get_degraded_history(10),
        "auto_migrate_policy": migrate_policy,
        "integrity_reconciled": governance["integrity_reconciled"],
        "authoritative_kpis": governance["authoritative_kpis"],
        "canonical_kpis": governance["canonical_kpis"],
        "accumulated_kpis": governance["accumulated_kpis"],
        "delta_kpis": governance["delta_kpis"],
        "kpi_governance": governance["kpi_governance"],
        "kpi_lineage": governance["kpi_lineage"],
        "metric_lineage": governance["metric_lineage"],
        "metric_semantics": governance["metric_semantics"],
        "integrity_consistent": governance["integrity_consistent"],
        "runtime_authoritative": governance["runtime_authoritative"],
        "stale_kpis_removed": 0,
        "governance_source": governance["governance_source"],
        "payload_safe": True,
    }

    safe = safe_json_payload(payload, context="pipeline_health")
    safe["payload_safe"] = True
    return safe


def validate_pipeline_health_contract(payload: dict) -> dict:
    """Optional Pydantic coercion — use in tests/startup only, not per-request hot path."""
    try:
        from api.schemas import PipelineHealthResponse

        model = PipelineHealthResponse.model_validate(payload)
        return model.model_dump(mode="json", by_alias=True)
    except Exception as exc:
        logger.warning("[PYDANTIC_SCHEMA] validate_pipeline_health_contract: %s", exc)
        out = safe_json_payload(payload, context="pipeline_health_contract_repair")
        out["contract_repaired"] = True
        return out


def governance_payload_for_tests() -> dict[str, Any]:
    """Sample governance blob for unit tests."""
    from analytics.kpi_governance import resolve_authoritative_kpis
    from unittest.mock import MagicMock

    session = MagicMock()
    gov = resolve_authoritative_kpis(
        session, live_kpis={"graph_nodes": 10, "graph_edges": 5}, stage_results={}
    )
    return safe_json_value(gov)
