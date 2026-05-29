"""Operational reporting reconciliation — KPI-driven, run-scoped, stale-event cleanup."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.timezone import format_operational_time

logger = logging.getLogger(__name__)

_FALSE_DEGRADED_CLASS = "false_degraded_stale_status"

_IATA_MISSING_RE = re.compile(
    r"iata_code.*(missing|ausente|does not exist|schema drift)|"
    r"coluna airline_metadata\.iata_code",
    re.I,
)
_SIGNALS_UNAVAILABLE_RE = re.compile(
    r"sinais indispon|signals unavailable|upstream.*empty|grafo ou metadados|"
    r"dependency contract|upstream contract",
    re.I,
)
_UPSTREAM_EMPTY_RE = re.compile(
    r"upstream|vazio|empty|incomplete|skipped|indispon",
    re.I,
)


def _metric(kpis: dict[str, Any], results: dict[str, Any], kpi_key: str, *result_keys: str) -> int:
    v = kpis.get(kpi_key)
    if isinstance(v, (int, float)) and v > 0:
        return int(v)
    stage = result_keys[0].split(".")[0] if result_keys else ""
    blob = results.get(stage, {}) if stage else {}
    if not isinstance(blob, dict):
        return 0
    for key in result_keys:
        if "." in key:
            parts = key.split(".")
            cur: Any = blob
            for part in parts:
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(part)
            val = cur
        else:
            val = blob.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return 0


def validate_operational_consistency(
    *,
    kpis: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    errors: list[dict[str, Any]] | None = None,
    failed_stages: list[str] | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect impossible UI/backend states (signals>0 but unavailable, etc.)."""
    kpis = kpis or {}
    results = results or {}
    errors = errors or []
    failed_stages = failed_stages or []
    schema = schema or {}

    signals = _fusion_signal_count(kpis, results)
    metadata = _metric(kpis, results, "metadata", "metadata.metadata_total", "metadata_total")
    graph_nodes = _metric(kpis, results, "graph_nodes", "knowledge_graph.total_nodes", "total_nodes")
    aviation_ok = bool(schema.get("canonical_aviation_valid")) and not bool(
        schema.get("aviation_semantic_drift", True)
    )

    inconsistencies: list[dict[str, str]] = []

    fusion_result = results.get("fusion", {})
    fusion_err = str(fusion_result.get("error", "")) if isinstance(fusion_result, dict) else ""
    if signals > 0 and (
        "fusion" in failed_stages
        or _SIGNALS_UNAVAILABLE_RE.search(fusion_err)
        or any(e.get("stage") == "fusion" for e in errors)
    ):
        inconsistencies.append(
            {"stage": "fusion", "reason": "signals_positive_but_marked_unavailable", "signals": str(signals)}
        )

    aviation_result = results.get("aviation_master", {})
    aviation_err = str(aviation_result.get("error", "")) if isinstance(aviation_result, dict) else ""
    if aviation_ok and _IATA_MISSING_RE.search(aviation_err):
        inconsistencies.append(
            {"stage": "aviation_master", "reason": "aviation_healthy_but_iata_missing_reported"}
        )

    if graph_nodes > 0 and "knowledge_graph" in failed_stages:
        inconsistencies.append(
            {
                "stage": "knowledge_graph",
                "reason": "graph_populated_but_stage_failed",
                "graph_nodes": str(graph_nodes),
            }
        )

    if metadata > 0 and "metadata" in failed_stages:
        inconsistencies.append(
            {"stage": "metadata", "reason": "metadata_populated_but_stage_failed", "metadata": str(metadata)}
        )

    return {
        "inconsistency_detected": len(inconsistencies) > 0,
        "inconsistencies": inconsistencies,
        "live_kpis": {
            "signals": signals,
            "metadata": metadata,
            "graph_nodes": graph_nodes,
        },
        "aviation_schema_healthy": aviation_ok,
    }


def _mark_reconciled_stage(
    stage: str,
    results: dict[str, Any],
    *,
    reason: str,
) -> None:
    blob = results.get(stage)
    if not isinstance(blob, dict):
        blob = {}
    blob.pop("error", None)
    blob["reconciled"] = True
    blob["degraded_classification"] = _FALSE_DEGRADED_CLASS
    blob["reconcile_reason"] = reason
    results[stage] = blob


def _should_reconcile_aviation(schema: dict[str, Any], runtime: dict[str, Any], error: str) -> bool:
    if not _IATA_MISSING_RE.search(error):
        return False
    canonical_ok = bool(schema.get("canonical_aviation_valid"))
    runtime_ok = bool(runtime.get("runtime_schema_consistent", True))
    return canonical_ok and runtime_ok


def _fusion_signal_count(kpis: dict[str, Any], results: dict[str, Any]) -> int:
    signals = _metric(kpis, results, "signals", "fusion.signals_generated", "signals_generated")
    if signals > 0:
        return signals
    signals = _metric(kpis, results, "signals", "fusion.signals_total", "signals_total")
    if signals > 0:
        return signals
    fusion_blob = results.get("fusion", {})
    if isinstance(fusion_blob, dict):
        for key in ("signals_generated", "signals_total"):
            val = fusion_blob.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return int(val)
    root = results.get("signals_generated")
    if isinstance(root, (int, float)) and root > 0:
        return int(root)
    return 0


def _should_reconcile_fusion(kpis: dict[str, Any], results: dict[str, Any], error: str) -> bool:
    if _fusion_signal_count(kpis, results) <= 0:
        return False
    if re.search(r"aviation enrichment|enrichment timeout|aviation_enrichment", error, re.I):
        return True
    return bool(
        _SIGNALS_UNAVAILABLE_RE.search(error)
        or results.get("dependency_contract_failed")
        or (isinstance(results.get("fusion"), dict) and results["fusion"].get("dependency_contract_failed"))
    )


def _should_reconcile_graph(kpis: dict[str, Any], results: dict[str, Any], error: str) -> bool:
    nodes = _metric(kpis, results, "graph_nodes", "knowledge_graph.total_nodes", "total_nodes")
    return nodes > 0 and bool(_UPSTREAM_EMPTY_RE.search(error))


def _should_reconcile_metadata(kpis: dict[str, Any], results: dict[str, Any], error: str) -> bool:
    meta = _metric(kpis, results, "metadata", "metadata.metadata_total", "metadata_total")
    return meta > 0 and bool(_UPSTREAM_EMPTY_RE.search(error))


def reconcile_soft_failures(
    *,
    errors: list[dict[str, Any]],
    results: dict[str, Any],
    events: list[dict[str, str]],
    operation_id: str,
    kpis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible alias — full pipeline event reconciliation."""
    out = reconcile_pipeline_events(
        operation_id=operation_id,
        errors=errors,
        results=results,
        events=events,
        kpis=kpis,
    )
    return out["errors"]


def reconcile_pipeline_events(
    *,
    operation_id: str,
    errors: list[dict[str, Any]],
    results: dict[str, Any],
    events: list[dict[str, str]],
    kpis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile errors, stage results, events, and derived failed stages for one run."""
    kpis = kpis or {}
    pruned = list(errors)
    reconciled_stages: list[str] = []
    stale_events_removed = 0

    schema: dict[str, Any] = {}
    runtime: dict[str, Any] = {}
    try:
        from database.session import engine
        from database.schema_health import validate_schema
        from database.runtime_schema import get_runtime_schema_report

        schema = validate_schema(engine, auto_migrate_dev=False)
        runtime = get_runtime_schema_report(engine)
    except Exception as exc:
        logger.warning("[PIPELINE_RECONCILE] schema/runtime load skipped: %s", exc)

    consistency_before = validate_operational_consistency(
        kpis=kpis,
        results=results,
        errors=pruned,
        failed_stages=[e.get("stage", "") for e in pruned],
        schema=schema,
    )

    def _drop_stage_failures(stage: str) -> None:
        nonlocal pruned
        pruned = [e for e in pruned if e.get("stage") != stage]

    # ── Aviation master ─────────────────────────────────────────────
    av_err = next((e for e in pruned if e.get("stage") == "aviation_master"), None)
    if av_err and _should_reconcile_aviation(schema, runtime, str(av_err.get("error", ""))):
        _drop_stage_failures("aviation_master")
        _mark_reconciled_stage("aviation_master", results, reason="aviation_schema_healthy")
        reconciled_stages.append("aviation_master")
        try:
            from app.runtime_state import remove_false_degraded_events

            remove_false_degraded_events(operation_id=operation_id, stage="aviation_master")
        except Exception:
            pass

    av_result = results.get("aviation_master", {})
    if isinstance(av_result, dict) and _should_reconcile_aviation(
        schema, runtime, str(av_result.get("error", ""))
    ):
        _mark_reconciled_stage("aviation_master", results, reason="aviation_schema_healthy")
        if "aviation_master" not in reconciled_stages:
            reconciled_stages.append("aviation_master")

    # ── Fusion / signals ────────────────────────────────────────────
    fusion_err = next((e for e in pruned if e.get("stage") == "fusion"), None)
    fusion_blob = results.get("fusion", {})
    fusion_error_text = str(
        (fusion_err or {}).get("error", "")
        or (fusion_blob.get("error", "") if isinstance(fusion_blob, dict) else "")
    )
    if _should_reconcile_fusion(kpis, results, fusion_error_text):
        _drop_stage_failures("fusion")
        _mark_reconciled_stage("fusion", results, reason="signals_available")
        reconciled_stages.append("fusion")
        try:
            from app.runtime_state import remove_false_degraded_events

            remove_false_degraded_events(operation_id=operation_id, stage="fusion")
        except Exception:
            pass

    # ── Knowledge graph ─────────────────────────────────────────────
    kg_err = next((e for e in pruned if e.get("stage") == "knowledge_graph"), None)
    kg_text = str((kg_err or {}).get("error", ""))
    if kg_err and _should_reconcile_graph(kpis, results, kg_text):
        _drop_stage_failures("knowledge_graph")
        _mark_reconciled_stage("knowledge_graph", results, reason="graph_populated")
        reconciled_stages.append("knowledge_graph")

    # ── Metadata ────────────────────────────────────────────────────
    md_err = next((e for e in pruned if e.get("stage") == "metadata"), None)
    md_text = str((md_err or {}).get("error", ""))
    if md_err and _should_reconcile_metadata(kpis, results, md_text):
        _drop_stage_failures("metadata")
        _mark_reconciled_stage("metadata", results, reason="metadata_populated")
        reconciled_stages.append("metadata")

    # ── Event timeline: run scope + stale pruning ───────────────────
    cleaned_events: list[dict[str, str]] = []
    for ev in events:
        ev_op = ev.get("operation_id") or operation_id
        if operation_id and ev_op and ev_op != operation_id:
            stale_events_removed += 1
            continue
        msg = ev.get("message", "")
        stale = False
        for stage in reconciled_stages:
            if f"Stage '{stage}' degraded" in msg or f"Stage '{stage}' failed" in msg:
                stale = True
                break
        if stale:
            stale_events_removed += 1
            continue
        cleaned_events.append({**ev, "operation_id": ev_op or operation_id})

    for stage in reconciled_stages:
        cleaned_events.append(
            {
                "time": format_operational_time(),
                "message": f"Stage '{stage}' recovered — stale operational status reconciled",
                "operation_id": operation_id,
            }
        )

    failed_stages = derive_failed_stages(pruned, results)
    consistency_after = validate_operational_consistency(
        kpis=kpis,
        results=results,
        errors=pruned,
        failed_stages=failed_stages,
        schema=schema,
    )

    if reconciled_stages:
        logger.warning(
            "[PIPELINE_RECONCILE] op=%s reconciled=%s stale_events_removed=%d inconsistencies_before=%d",
            operation_id,
            reconciled_stages,
            stale_events_removed,
            len(consistency_before.get("inconsistencies", [])),
        )
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_false_degraded_removed", float(len(reconciled_stages)))
            record_worker_metric("skytrax_stale_events_removed", float(stale_events_removed))
            record_worker_metric("skytrax_reconciled_pipeline_events", float(len(reconciled_stages)))
            if consistency_before.get("inconsistency_detected"):
                record_worker_metric("skytrax_impossible_states_detected", 1.0)
            record_worker_metric(
                "skytrax_ui_state_mismatch",
                0.0 if not consistency_after.get("inconsistency_detected") else 1.0,
            )
        except Exception:
            pass

    return {
        "errors": pruned,
        "results": results,
        "events": cleaned_events,
        "failed_stages": failed_stages,
        "reconciled_stages": reconciled_stages,
        "stale_events_removed": stale_events_removed,
        "operational_consistency": consistency_after,
        "false_degraded_removed": len(reconciled_stages),
    }


def derive_failed_stages(
    errors: list[dict[str, Any]],
    results: dict[str, Any],
) -> list[str]:
    """Failed stages from errors + unreconciled stage result errors."""
    failed: set[str] = set()
    for err in errors:
        stage = err.get("stage")
        if stage:
            failed.add(stage)
    for stage, blob in results.items():
        if not isinstance(blob, dict):
            continue
        if blob.get("reconciled"):
            continue
        if stage == "fusion" and blob.get("fusion_status") == "completed":
            if blob.get("enrichment_warning") and not blob.get("correlation_failed"):
                continue
            if blob.get("stage_warning") and not blob.get("error"):
                continue
        if blob.get("error") and not (
            stage == "fusion"
            and blob.get("fusion_status") == "completed"
            and int(blob.get("signals_generated") or 0) > 0
        ):
            failed.add(stage)
    return sorted(failed)


def reconcile_live_status_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Apply reconciliation to Redis live status before API/UI consumption."""
    if not data or data.get("stage") == "idle":
        return data

    operation_id = str(data.get("operation_id") or "")
    kpis = data.get("kpis") or {}
    results = dict(data.get("stage_results") or {})
    events = list(data.get("events") or [])
    errors = [
        {"stage": stage, "error": (results.get(stage) or {}).get("error", "stage failed"), "soft": True}
        for stage in (data.get("failed_stages") or [])
        if isinstance(results.get(stage), dict) and results[stage].get("error")
    ]

    out = reconcile_pipeline_events(
        operation_id=operation_id,
        errors=errors,
        results=results,
        events=events,
        kpis=kpis,
    )

    data = dict(data)
    data["stage_results"] = out["results"]
    data["events"] = out["events"]
    data["failed_stages"] = out["failed_stages"]
    data["operational_consistency"] = out["operational_consistency"]
    data["reconciled_stages"] = out.get("reconciled_stages", [])
    data["false_degraded_removed"] = out.get("false_degraded_removed", 0)
    data["stale_events_removed"] = out.get("stale_events_removed", 0)

    if out["failed_stages"]:
        data["pipeline_status"] = data.get("pipeline_status") or "running_degraded"
    elif data.get("stage") in ("completed_degraded",) and not out["failed_stages"]:
        data["stage"] = "completed"
        data["pipeline_status"] = "completed"

    if out.get("reconciled_stages"):
        data["reconciliation_status"] = "reconciled"
    return data
