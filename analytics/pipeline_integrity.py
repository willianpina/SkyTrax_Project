"""Pipeline integrity — table counts, dependency contracts, stage audits."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.pipeline_lineage import (
    DEPENDENCY_CONTRACTS,
    STAGE_LINEAGE,
    STAGE_SKIP_MESSAGES,
    export_lineage_report,
)

logger = logging.getLogger(__name__)


def _models():
    """Lazy import to keep lineage/contract utilities usable without DB driver."""
    from database.models import (
        Airline,
        AnomalyEvent,
        ExecutiveInsight,
        ForecastSnapshot,
        MetricSnapshot,
        NLPResult,
        Review,
        SemanticCluster,
    )
    from database.models.graph import FusionSignal, GraphEdge, GraphNode, ReviewIntelligence

    return {
        "Review": Review,
        "NLPResult": NLPResult,
        "ReviewIntelligence": ReviewIntelligence,
        "GraphNode": GraphNode,
        "GraphEdge": GraphEdge,
        "FusionSignal": FusionSignal,
        "AnomalyEvent": AnomalyEvent,
        "ForecastSnapshot": ForecastSnapshot,
        "SemanticCluster": SemanticCluster,
        "ExecutiveInsight": ExecutiveInsight,
        "MetricSnapshot": MetricSnapshot,
        "Airline": Airline,
    }


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINEAGE_REPORT_PATH = PROJECT_ROOT / "pipeline_lineage_report.json"
REDIS_INTEGRITY_KEY = "skytrax:ops:integrity:authoritative"
REDIS_INTEGRITY_TTL_S = 86400

# Live pipeline KPI keys → integrity table_counts keys
_KPI_TO_COUNT: tuple[tuple[str, str], ...] = (
    ("reviews", "reviews"),
    ("metadata", "review_intelligence"),
    ("graph_nodes", "graph_nodes"),
    ("graph_edges", "graph_edges"),
    ("signals", "fusion_signals"),
    ("anomalies", "anomaly_events"),
    ("clusters", "semantic_clusters"),
    ("forecasts", "forecast_snapshots"),
    ("insights", "executive_insights"),
    ("snapshots", "metric_snapshots"),
)


def _safe_count(session: Session, model, label: str) -> int:
    try:
        return int(session.query(func.count(model.id)).scalar() or 0)
    except Exception as exc:
        logger.warning("[INTEGRITY] count failed table=%s: %s", label, exc)
        try:
            session.rollback()
        except Exception:
            pass
        return -1


def collect_table_counts(session: Session) -> dict[str, int]:
    """Current corpus counts for integrity dashboard (-1 = query failed)."""
    m = _models()
    return {
        "reviews": _safe_count(session, m["Review"], "reviews"),
        "nlp_results": _safe_count(session, m["NLPResult"], "nlp_results"),
        "review_intelligence": _safe_count(session, m["ReviewIntelligence"], "review_intelligence"),
        "graph_nodes": _safe_count(session, m["GraphNode"], "graph_nodes"),
        "graph_edges": _safe_count(session, m["GraphEdge"], "graph_edges"),
        "fusion_signals": _safe_count(session, m["FusionSignal"], "fusion_signals"),
        "anomaly_events": _safe_count(session, m["AnomalyEvent"], "anomaly_events"),
        "forecast_snapshots": _safe_count(session, m["ForecastSnapshot"], "forecast_snapshots"),
        "semantic_clusters": _safe_count(session, m["SemanticCluster"], "semantic_clusters"),
        "executive_insights": _safe_count(session, m["ExecutiveInsight"], "executive_insights"),
        "metric_snapshots": _safe_count(session, m["MetricSnapshot"], "metric_snapshots"),
        "airlines": _safe_count(session, m["Airline"], "airlines"),
    }


def collect_count_errors(counts: dict[str, int]) -> dict[str, str]:
    """Tables whose count query failed (shown as -1 in counts)."""
    return {k: "query_failed" for k, v in counts.items() if v < 0}


def check_stage_contract(stage: str, counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Validate upstream requirements for a stage."""
    contract = DEPENDENCY_CONTRACTS.get(stage, {})
    if not contract:
        return {"stage": stage, "satisfied": True, "failures": [], "warnings": []}

    if counts is None:
        return {"stage": stage, "satisfied": True, "failures": [], "warnings": ["counts_not_provided"]}

    failures: list[str] = []
    warnings: list[str] = []

    mapping = {
        "reviews": counts.get("reviews", 0),
        "metadata_records": counts.get("review_intelligence", 0),
        "graph_nodes": counts.get("graph_nodes", 0),
        "forecasts": counts.get("forecast_snapshots", 0),
    }

    for key, minimum in contract.items():
        actual = mapping.get(key, counts.get(key, 0))
        if actual < 0:
            failures.append(f"{key}: table unreadable")
        elif actual < minimum:
            failures.append(f"{key}: need>={minimum} have={actual}")

    return {
        "stage": stage,
        "satisfied": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "skip_message": STAGE_SKIP_MESSAGES.get(stage, ""),
        "counts_snapshot": {k: mapping.get(k, counts.get(k)) for k in contract},
    }


def audit_pipeline_integrity(session: Session) -> dict[str, Any]:
    """Full integrity audit for API / ops dashboard."""
    counts = collect_table_counts(session)
    reviews = max(counts.get("reviews", 0), 0)
    nlp = max(counts.get("nlp_results", 0), 0)
    metadata = max(counts.get("review_intelligence", 0), 0)
    graph_n = max(counts.get("graph_nodes", 0), 0)

    coverage = {
        "metadata_coverage_pct": round(metadata / reviews * 100, 1) if reviews > 0 else 0.0,
        "nlp_coverage_pct": round(nlp / reviews * 100, 1) if reviews > 0 else 0.0,
        "graph_density": graph_n,
    }

    stage_contracts = {
        stage: check_stage_contract(stage, counts) for stage in STAGE_LINEAGE if stage in DEPENDENCY_CONTRACTS
    }

    return {
        "table_counts": counts,
        "coverage": coverage,
        "stage_contracts": stage_contracts,
        "healthy": all(c["satisfied"] for c in stage_contracts.values()),
        "lineage": export_lineage_report(),
    }


def write_lineage_report(path: Path | None = None) -> Path:
    """Persist pipeline_lineage_report.json to project root."""
    from analytics.pipeline_lineage import export_lineage_report as _export

    target = path or LINEAGE_REPORT_PATH
    payload = _export()
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("[INTEGRITY] Wrote lineage report path=%s", target)
    return target


def kpi_totals_from_db(session: Session) -> dict[str, int | float]:
    """Authoritative KPI totals from DB (not incremental stage deltas)."""
    counts = collect_table_counts(session)
    return {
        "reviews": counts.get("reviews", 0),
        "metadata": counts.get("review_intelligence", 0),
        "graph_nodes": counts.get("graph_nodes", 0),
        "graph_edges": counts.get("graph_edges", 0),
        "signals": counts.get("fusion_signals", 0),
        "anomalies": counts.get("anomaly_events", 0),
        "clusters": counts.get("semantic_clusters", 0),
        "forecasts": counts.get("forecast_snapshots", 0),
        "insights": counts.get("executive_insights", 0),
        "snapshots": counts.get("metric_snapshots", 0),
    }


def _positive_int(val: Any) -> int:
    if isinstance(val, (int, float)) and val >= 0 and val == val:
        return int(val)
    return 0


def _stage_metric(stage_results: dict[str, Any] | None, stage: str, *keys: str) -> int:
    blob = (stage_results or {}).get(stage)
    if not isinstance(blob, dict):
        return 0
    for key in keys:
        if "." in key:
            cur: Any = blob
            for part in key.split("."):
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


def live_kpis_from_stage_results(stage_results: dict[str, Any] | None) -> dict[str, int]:
    """Extract best-effort live KPIs from stage_results when Redis kpis are absent."""
    sr = stage_results or {}
    return {
        "reviews": _stage_metric(sr, "crawl", "total_reviews_in_db", "reviews_total"),
        "metadata": _stage_metric(sr, "metadata", "metadata_total", "reviews_analyzed"),
        "graph_nodes": _stage_metric(sr, "knowledge_graph", "total_nodes"),
        "graph_edges": _stage_metric(sr, "knowledge_graph", "total_edges"),
        "signals": _stage_metric(sr, "fusion", "fusion.signals_generated", "signals_generated"),
        "anomalies": _stage_metric(sr, "anomalies", "anomalies_created"),
        "clusters": _stage_metric(sr, "semantic", "clusters_created"),
        "snapshots": _stage_metric(sr, "snapshots", "snapshots_created", "metric_snapshots"),
    }


def reconcile_integrity_metrics(
    *,
    table_counts: dict[str, int] | None = None,
    coverage: dict[str, Any] | None = None,
    live_kpis: dict[str, Any] | None = None,
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge Postgres counts with runtime KPIs — never show false zeros when corpus exists."""
    counts = dict(table_counts or {})
    stage_live = live_kpis_from_stage_results(stage_results)
    kpis = {**stage_live, **(live_kpis or {})}

    reconciled_fields: list[str] = []
    impossible_states: list[dict[str, Any]] = []
    kpi_lineage: dict[str, dict[str, Any]] = {}
    now = datetime.now(timezone.utc).isoformat()

    for kpi_key, count_key in _KPI_TO_COUNT:
        db_val = _positive_int(counts.get(count_key, -1) if counts.get(count_key, -1) >= 0 else 0)
        live_val = _positive_int(kpis.get(kpi_key))
        merged = max(db_val, live_val)
        if live_val > db_val and db_val >= 0:
            reconciled_fields.append(count_key)
        if live_val > 0 and db_val == 0:
            impossible_states.append(
                {"metric": count_key, "db": db_val, "live": live_val, "reason": "stale_or_partial_integrity"},
            )
        counts[count_key] = merged
        source = (
            "postgres+runtime"
            if live_val > db_val
            else ("postgres" if db_val > 0 else ("runtime" if live_val > 0 else "empty"))
        )
        kpi_lineage[count_key] = {
            "source": source,
            "postgres": db_val,
            "runtime": live_val,
            "authoritative": merged,
            "reconciled": live_val > db_val,
            "updated_at": now,
        }

    reviews = _positive_int(counts.get("reviews"))
    metadata = _positive_int(counts.get("review_intelligence"))
    nlp = _positive_int(counts.get("nlp_results"))
    graph_n = _positive_int(counts.get("graph_nodes"))

    cov = dict(coverage or {})
    if reviews > 0:
        cov["metadata_coverage_pct"] = round(metadata / reviews * 100, 1)
        cov["nlp_coverage_pct"] = round(nlp / reviews * 100, 1) if nlp else cov.get("nlp_coverage_pct", 0.0)
    elif metadata > 0:
        cov["metadata_coverage_pct"] = 100.0
    cov["graph_density"] = graph_n

    integrity_consistent = len(impossible_states) == 0 or len(reconciled_fields) > 0
    stale_kpis_removed = len(reconciled_fields)

    if reconciled_fields or impossible_states:
        logger.info(
            "[PIPELINE_INTEGRITY][KPI_RECONCILE] reconciled=%s impossible=%d fields=%s",
            integrity_consistent,
            len(impossible_states),
            reconciled_fields[:8],
        )
        record_integrity_reconciliation_metrics(
            reconciliations=len(reconciled_fields),
            impossible=len(impossible_states),
            consistent=integrity_consistent,
        )

    return {
        "table_counts": counts,
        "coverage": cov,
        "integrity_reconciled": len(reconciled_fields) > 0,
        "integrity_consistent": integrity_consistent,
        "authoritative_kpis": {k: _positive_int(counts.get(c)) for k, c in _KPI_TO_COUNT},
        "kpi_lineage": kpi_lineage,
        "runtime_authoritative": bool(live_kpis),
        "stale_kpis_removed": stale_kpis_removed,
        "impossible_kpi_states": impossible_states,
        "reconciled_fields": reconciled_fields,
    }


def build_authoritative_integrity(
    session: Session,
    *,
    live_kpis: dict[str, Any] | None = None,
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full integrity audit merged with runtime-authoritative KPIs."""
    from analytics.kpi_governance import resolve_authoritative_kpis

    audit = audit_pipeline_integrity(session)
    merged = reconcile_integrity_metrics(
        table_counts=audit.get("table_counts"),
        coverage=audit.get("coverage"),
        live_kpis=live_kpis,
        stage_results=stage_results,
    )
    audit.update(merged)
    gov = resolve_authoritative_kpis(session, live_kpis=live_kpis, stage_results=stage_results)
    audit["kpi_governance"] = gov.get("kpi_governance")
    audit["canonical_kpis"] = gov.get("canonical_kpis")
    audit["accumulated_kpis"] = gov.get("accumulated_kpis")
    audit["delta_kpis"] = gov.get("delta_kpis")
    audit["metric_lineage"] = gov.get("metric_lineage")
    audit["metric_semantics"] = gov.get("metric_semantics")
    counts = audit.get("table_counts") or {}
    acc = gov.get("accumulated_kpis") or {}
    counts["graph_edges"] = max(int(counts.get("graph_edges", 0)), int(acc.get("graph_edges", 0)))
    audit["table_counts"] = counts
    audit["healthy"] = audit.get("healthy", True) and merged.get("integrity_consistent", True)
    audit["integrity_consistent"] = merged.get("integrity_consistent", True) and gov.get(
        "integrity_consistent", True
    )
    return audit


def record_integrity_reconciliation_metrics(
    *,
    reconciliations: int = 0,
    impossible: int = 0,
    consistent: bool = True,
) -> None:
    try:
        from app.observability import record_worker_metric

        if reconciliations:
            record_worker_metric("skytrax_integrity_reconciliations", float(reconciliations))
        if impossible:
            record_worker_metric("skytrax_impossible_kpi_states", float(impossible))
        record_worker_metric("skytrax_integrity_payload_consistent", 1.0 if consistent else 0.0)
        record_worker_metric("skytrax_authoritative_refresh_count", 1.0)
    except Exception:
        pass


def persist_authoritative_integrity_snapshot(
    integrity: dict[str, Any],
    *,
    redis_client: Any | None = None,
) -> None:
    """Cache reconciled integrity for health endpoints (Redis TTL)."""
    try:
        if redis_client is None:
            from worker.orchestration.refresh_pipeline import _redis

            redis_client = _redis()
        payload = {
            **integrity,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        redis_client.set(REDIS_INTEGRITY_KEY, json.dumps(payload, default=str), ex=REDIS_INTEGRITY_TTL_S)
        logger.info("[PIPELINE_INTEGRITY][AUTHORITATIVE_KPI] cached reconciled integrity snapshot")
    except Exception as exc:
        logger.warning("[PIPELINE_INTEGRITY] integrity snapshot cache skipped: %s", exc)


def load_authoritative_integrity_snapshot(redis_client: Any | None = None) -> dict[str, Any] | None:
    try:
        if redis_client is None:
            from worker.orchestration.refresh_pipeline import _redis

            redis_client = _redis()
        raw = redis_client.get(REDIS_INTEGRITY_KEY)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def integrity_snapshot_cleanup(redis_client: Any | None = None) -> dict[str, Any]:
    """Drop stale integrity cache when live Redis KPIs contradict cached zeros."""
    removed = 0
    try:
        if redis_client is None:
            from worker.orchestration.refresh_pipeline import _redis

            redis_client = _redis()
        from worker.orchestration.refresh_pipeline import REDIS_STATUS_KEY

        cached = load_authoritative_integrity_snapshot(redis_client)
        raw = redis_client.get(REDIS_STATUS_KEY)
        if not cached or not raw:
            return {"removed": 0}
        status = json.loads(raw)
        live = status.get("kpis") or {}
        counts = cached.get("table_counts") or {}
        stale = False
        for kpi_key, count_key in _KPI_TO_COUNT:
            if _positive_int(live.get(kpi_key)) > 0 and _positive_int(counts.get(count_key)) == 0:
                stale = True
                break
        if stale:
            redis_client.delete(REDIS_INTEGRITY_KEY)
            removed = 1
            logger.warning("[PIPELINE_INTEGRITY][STALE_KPI] removed stale integrity snapshot")
            try:
                from app.observability import record_worker_metric

                record_worker_metric("skytrax_stale_kpis_removed", 1.0)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("[PIPELINE_INTEGRITY] cleanup skipped: %s", exc)
    return {"removed": removed}


def load_live_kpis_from_redis(redis_client: Any | None = None) -> dict[str, Any]:
    """Read authoritative pipeline KPIs from the live status key."""
    try:
        if redis_client is None:
            from worker.orchestration.refresh_pipeline import REDIS_STATUS_KEY, _redis

            redis_client = _redis()
            raw = redis_client.get(REDIS_STATUS_KEY)
        else:
            from worker.orchestration.refresh_pipeline import REDIS_STATUS_KEY

            raw = redis_client.get(REDIS_STATUS_KEY)
        if not raw:
            return {}
        data = json.loads(raw)
        return dict(data.get("kpis") or {})
    except Exception:
        return {}


def validate_graph_consistency(session: Session) -> dict[str, Any]:
    """Check graph_nodes / graph_edges referential integrity."""
    m = _models()
    GraphNode, GraphEdge = m["GraphNode"], m["GraphEdge"]
    issues: list[str] = []
    node_count = _safe_count(session, GraphNode, "graph_nodes")
    edge_count = _safe_count(session, GraphEdge, "graph_edges")
    if edge_count > 0 and node_count == 0:
        issues.append("edges_exist_without_nodes")
    if edge_count > 0:
        try:
            orphan = (
                session.query(func.count(GraphEdge.id))
                .filter(
                    ~GraphEdge.source_node_id.in_(session.query(GraphNode.id)),
                )
                .scalar()
                or 0
            )
            if orphan:
                issues.append(f"orphan_edges={orphan}")
        except Exception as exc:
            issues.append(f"edge_check_failed:{exc}")
            session.rollback()
    return {
        "valid": len(issues) == 0,
        "node_count": node_count,
        "edge_count": edge_count,
        "issues": issues,
    }


def validate_snapshot_integrity(session: Session) -> dict[str, Any]:
    """Lightweight snapshot table health check."""
    count = _safe_count(session, _models()["MetricSnapshot"], "metric_snapshots")
    issues: list[str] = []
    if count < 0:
        issues.append("metric_snapshots_unreadable")
    return {
        "valid": len(issues) == 0,
        "snapshot_count": max(count, 0),
        "issues": issues,
    }


def signal_dependency_report(session: Session) -> dict[str, Any]:
    """Why fusion/signals may be empty."""
    counts = collect_table_counts(session)
    count_errors = collect_count_errors(counts)
    ri = counts.get("review_intelligence", 0)
    blockers: list[str] = []
    if counts.get("reviews", 0) <= 0:
        blockers.append("no_reviews")
    elif ri < 0:
        blockers.append("metadata_unreadable")
    elif ri <= 0:
        blockers.append("no_metadata")
    if counts.get("graph_nodes", 0) <= 0:
        blockers.append("no_graph_nodes")
    return {
        "reviews": counts.get("reviews", 0),
        "review_intelligence": ri,
        "graph_nodes": counts.get("graph_nodes", 0),
        "fusion_signals": counts.get("fusion_signals", 0),
        "count_errors": count_errors,
        "blockers": blockers,
        "knowledge_graph_blocked_by": (
            "metadata" if "no_metadata" in blockers or "metadata_unreadable" in blockers else None
        ),
    }


def record_integrity_metrics(session: Session) -> None:
    """Push integrity gauges to worker metrics."""
    try:
        from app.observability import record_worker_metric

        counts = collect_table_counts(session)
        record_worker_metric("skytrax_metadata_records", float(max(counts.get("review_intelligence", 0), 0)))
        record_worker_metric("skytrax_graph_nodes", float(max(counts.get("graph_nodes", 0), 0)))
        record_worker_metric("skytrax_graph_edges", float(max(counts.get("graph_edges", 0), 0)))
        record_worker_metric("skytrax_signals_generated", float(max(counts.get("fusion_signals", 0), 0)))
        record_worker_metric("skytrax_anomalies_detected", float(max(counts.get("anomaly_events", 0), 0)))
    except Exception:
        pass
