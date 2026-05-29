"""Canonical KPI registry — single source of truth, accumulated vs delta semantics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MetricKind = Literal["accumulated", "delta", "runtime", "snapshot", "semantic", "computed"]

CANONICAL_KPI_REGISTRY: dict[str, dict[str, Any]] = {
    "reviews": {
        "label": "Reviews",
        "kind": "accumulated",
        "table": "reviews",
        "count_key": "reviews",
        "authoritative": True,
        "semantic": "Total review corpus in PostgreSQL",
    },
    "metadata": {
        "label": "Metadata",
        "kind": "accumulated",
        "table": "review_intelligence",
        "count_key": "review_intelligence",
        "authoritative": True,
        "semantic": "Enriched review intelligence records",
    },
    "graph_nodes": {
        "label": "Graph nodes",
        "kind": "accumulated",
        "table": "graph_nodes",
        "count_key": "graph_nodes",
        "authoritative": True,
        "semantic": "Canonical knowledge-graph nodes (NOT nodes+edges)",
    },
    "graph_edges": {
        "label": "Graph edges",
        "kind": "accumulated",
        "table": "graph_edges",
        "count_key": "graph_edges",
        "authoritative": True,
        "semantic": "Knowledge-graph relationships",
    },
    "graph_entities": {
        "label": "Graph entities",
        "kind": "computed",
        "authoritative": True,
        "semantic": "nodes + edges (display-only aggregate; do not compare to graph_nodes alone)",
        "compute": lambda acc: int(acc.get("graph_nodes", 0)) + int(acc.get("graph_edges", 0)),
    },
    "signals": {
        "label": "Fusion signals",
        "kind": "accumulated",
        "table": "fusion_signals",
        "count_key": "fusion_signals",
        "authoritative": True,
        "semantic": "Strategic fusion signals persisted",
    },
    "anomalies": {
        "label": "Anomalies",
        "kind": "accumulated",
        "table": "anomaly_events",
        "count_key": "anomaly_events",
        "authoritative": True,
        "semantic": "Detected anomaly events",
    },
    "clusters": {
        "label": "Semantic clusters",
        "kind": "accumulated",
        "table": "semantic_clusters",
        "count_key": "semantic_clusters",
        "authoritative": True,
        "semantic": "Semantic cluster entities",
    },
    "snapshots": {
        "label": "Metric snapshots",
        "kind": "accumulated",
        "table": "metric_snapshots",
        "count_key": "metric_snapshots",
        "authoritative": True,
        "semantic": "Persisted metric snapshots",
    },
    "aviation_metadata_total": {
        "label": "Aviation metadata airlines",
        "kind": "accumulated",
        "table": "airline_metadata",
        "authoritative": True,
        "semantic": "Total airline_metadata rows",
    },
    "aviation_linked_total": {
        "label": "Aviation linked",
        "kind": "accumulated",
        "table": "airline_metadata",
        "authoritative": True,
        "semantic": "airline_metadata rows linked to core airlines",
    },
    "aviation_processed_this_run": {
        "label": "Aviation processed (run)",
        "kind": "delta",
        "stage": "aviation_master",
        "authoritative": False,
        "semantic": "airlines_created + airlines_updated in this pipeline run",
    },
    "aviation_linked_this_run": {
        "label": "Aviation linked (run)",
        "kind": "delta",
        "stage": "aviation_master",
        "authoritative": False,
        "semantic": "links_created in this pipeline run",
    },
}


def _aviation_accumulated_counts(session: Session) -> dict[str, int]:
    try:
        from database.models.aviation import AirlineMetadata

        total = int(session.scalar(select(func.count(AirlineMetadata.id))) or 0)
        linked = int(
            session.scalar(
                select(func.count(AirlineMetadata.id)).where(AirlineMetadata.airline_id.isnot(None))
            )
            or 0
        )
        return {"aviation_metadata_total": total, "aviation_linked_total": linked}
    except Exception as exc:
        logger.warning("[KPI_GOVERNANCE] aviation counts skipped: %s", exc)
        try:
            session.rollback()
        except Exception:
            pass
        return {"aviation_metadata_total": 0, "aviation_linked_total": 0}


def _delta_from_stage(stage_results: dict[str, Any] | None) -> dict[str, int]:
    sr = stage_results if isinstance(stage_results, dict) else {}
    av = sr.get("aviation_master") if isinstance(sr.get("aviation_master"), dict) else {}
    created = int(av.get("airlines_created") or 0)
    updated = int(av.get("airlines_updated") or 0)
    return {
        "aviation_processed_this_run": created + updated,
        "aviation_linked_this_run": int(av.get("links_created") or 0),
    }


def _detect_divergences(
    accumulated: dict[str, int], live_kpis: dict[str, Any] | None
) -> list[dict[str, Any]]:
    divergences: list[dict[str, Any]] = []
    live = live_kpis if isinstance(live_kpis, dict) else {}
    nodes = int(accumulated.get("graph_nodes", 0))
    edges = int(accumulated.get("graph_edges", 0))
    entities = nodes + edges

    live_nodes = int(live.get("graph_nodes") or 0)
    live_edges = int(live.get("graph_edges") or 0)
    live_graph_kpi = live_nodes + live_edges

    if live_graph_kpi > 0 and nodes > 0 and live_graph_kpi == entities and live_graph_kpi != nodes:
        divergences.append(
            {
                "metric": "graph_display",
                "reason": "live_graph_kpi_sums_nodes_and_edges",
                "nodes": nodes,
                "edges": edges,
                "entities": entities,
                "mislabeled_as": "single_graph_number",
            }
        )
    return divergences


def resolve_authoritative_kpis(
    session: Session,
    *,
    live_kpis: dict[str, Any] | None = None,
    stage_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build canonical accumulated + delta KPI payload with lineage."""
    from analytics.pipeline_integrity import kpi_totals_from_db

    now = datetime.now(timezone.utc).isoformat()
    accumulated = dict(kpi_totals_from_db(session))
    accumulated.update(_aviation_accumulated_counts(session))

    graph_nodes = int(accumulated.get("graph_nodes", 0))
    graph_edges = int(accumulated.get("graph_edges", 0))
    accumulated["graph_entities"] = graph_nodes + graph_edges

    delta = _delta_from_stage(stage_results)
    divergences = _detect_divergences(accumulated, live_kpis)

    _KPI_ACCUM_KEY = {
        "reviews": "reviews",
        "metadata": "metadata",
        "graph_nodes": "graph_nodes",
        "graph_edges": "graph_edges",
        "signals": "signals",
        "anomalies": "anomalies",
        "clusters": "clusters",
        "snapshots": "snapshots",
    }

    lineage: dict[str, dict[str, Any]] = {}
    for key, spec in CANONICAL_KPI_REGISTRY.items():
        kind = spec.get("kind", "accumulated")
        if kind == "computed":
            val = (
                int(spec["compute"](accumulated))
                if callable(spec.get("compute"))
                else int(accumulated.get(key, 0))
            )
        elif kind == "delta":
            val = int(delta.get(key, 0))
        else:
            acc_key = spec.get("count_key") or _KPI_ACCUM_KEY.get(key, key)
            val = int(accumulated.get(acc_key, accumulated.get(key, 0)))

        lineage[key] = {
            "label": spec.get("label", key),
            "kind": kind,
            "semantic": spec.get("semantic", ""),
            "authoritative": spec.get("authoritative", True),
            "value": val,
            "source": spec.get("table") or spec.get("stage") or "computed",
            "reconciled_at": now,
        }

    if divergences:
        logger.warning("[KPI_GOVERNANCE][GRAPH_RECONCILE] divergences=%s", divergences)
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_kpi_divergence_detected", float(len(divergences)))
            record_worker_metric("skytrax_graph_metric_mismatch", 1.0)
        except Exception:
            pass

    from app.payload_serialization import safe_json_value

    payload = {
        "canonical_kpis": accumulated,
        "accumulated_kpis": {
            k: v
            for k, v in accumulated.items()
            if k in CANONICAL_KPI_REGISTRY
            or k
            in (
                "reviews",
                "metadata",
                "graph_nodes",
                "graph_edges",
                "graph_entities",
                "signals",
                "anomalies",
                "clusters",
                "snapshots",
                "aviation_metadata_total",
                "aviation_linked_total",
            )
        },
        "delta_kpis": delta,
        "kpi_governance": {
            "registry_version": 1,
            "divergences": divergences,
            "graph_semantics": {
                "nodes": graph_nodes,
                "edges": graph_edges,
                "entities_sum": graph_nodes + graph_edges,
                "note": "UI must label nodes and edges separately; entities_sum is not graph_nodes",
            },
            "aviation_semantics": {
                "total": accumulated.get("aviation_metadata_total", 0),
                "linked_total": accumulated.get("aviation_linked_total", 0),
                "processed_this_run": delta.get("aviation_processed_this_run", 0),
                "linked_this_run": delta.get("aviation_linked_this_run", 0),
            },
        },
        "metric_lineage": lineage,
        "metric_semantics": {k: v.get("semantic", "") for k, v in CANONICAL_KPI_REGISTRY.items()},
        "integrity_consistent": len(divergences) == 0,
    }
    return safe_json_value(payload)


def resolve_authoritative_kpi(key: str, payload: dict[str, Any]) -> int:
    """Resolve one canonical KPI from a governance payload."""
    acc = payload.get("accumulated_kpis") or payload.get("canonical_kpis") or {}
    delta = payload.get("delta_kpis") or {}
    spec = CANONICAL_KPI_REGISTRY.get(key, {})
    if spec.get("kind") == "delta":
        return int(delta.get(key, 0))
    if spec.get("kind") == "computed" and callable(spec.get("compute")):
        return int(spec["compute"](acc))
    ck = spec.get("count_key")
    if ck and ck in acc:
        return int(acc[ck])
    return int(acc.get(key, 0))
