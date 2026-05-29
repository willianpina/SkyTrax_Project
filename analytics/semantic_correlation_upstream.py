"""Upstream validation for semantic correlation (fusion) — prevents false empty-graph skips."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from sqlalchemy.orm import Session

from analytics.pipeline_integrity import (
    check_stage_contract,
    collect_table_counts,
    signal_dependency_report,
    validate_graph_consistency,
)

logger = logging.getLogger(__name__)

# Minimum thresholds for correlation (env-tunable)
_MIN_GRAPH_NODES = int(os.getenv("FUSION_MIN_GRAPH_NODES", "1"))
_MIN_METADATA = int(os.getenv("FUSION_MIN_METADATA_RECORDS", "1"))
_MIN_REVIEWS = int(os.getenv("FUSION_MIN_REVIEWS", "1"))


def _positive(val: Any) -> int:
    if isinstance(val, (int, float)) and val >= 0 and val == val:
        return int(val)
    return 0


def merge_upstream_counts(
    db_counts: dict[str, int],
    *,
    stage_results: dict[str, Any] | None = None,
    pipeline_kpis: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Authoritative counts = max(DB snapshot, in-run stage outputs, accumulated KPIs)."""
    merged = dict(db_counts)
    stage_results = stage_results or {}
    pipeline_kpis = pipeline_kpis or {}

    kg = stage_results.get("knowledge_graph")
    if isinstance(kg, dict):
        merged["graph_nodes"] = max(merged.get("graph_nodes", 0), _positive(kg.get("total_nodes")))
        merged["graph_edges"] = max(merged.get("graph_edges", 0), _positive(kg.get("total_edges")))

    meta = stage_results.get("metadata")
    if isinstance(meta, dict):
        merged["review_intelligence"] = max(
            merged.get("review_intelligence", 0),
            _positive(meta.get("metadata_total")),
        )

    crawl = stage_results.get("crawl")
    if isinstance(crawl, dict):
        merged["reviews"] = max(merged.get("reviews", 0), _positive(crawl.get("total_reviews_in_db")))

    kpi_map = {
        "graph_nodes": "graph_nodes",
        "graph_edges": "graph_edges",
        "metadata": "review_intelligence",
        "reviews": "reviews",
        "signals": "fusion_signals",
    }
    for kpi_key, count_key in kpi_map.items():
        merged[count_key] = max(merged.get(count_key, 0), _positive(pipeline_kpis.get(kpi_key)))

    return merged


def validate_semantic_correlation_upstream(
    session: Session,
    *,
    stage_results: dict[str, Any] | None = None,
    pipeline_kpis: dict[str, Any] | None = None,
    operation_id: str = "",
) -> dict[str, Any]:
    """Mandatory pre-flight before fusion/correlation — never false-empty when data exists."""
    started = time.perf_counter()
    logger.info("[SEMANTIC_CORRELATION] stage_start op=%s", operation_id or "—")

    db_counts = collect_table_counts(session)
    counts = merge_upstream_counts(
        db_counts,
        stage_results=stage_results,
        pipeline_kpis=pipeline_kpis,
    )

    graph_nodes = max(counts.get("graph_nodes", 0), 0)
    graph_edges = max(counts.get("graph_edges", 0), 0)
    metadata = counts.get("review_intelligence", 0)
    reviews = max(counts.get("reviews", 0), 0)

    logger.info(
        "[UPSTREAM_VALIDATION] records_loaded reviews=%d metadata=%d graph_nodes=%d graph_edges=%d "
        "db_nodes=%d pipeline_nodes=%s op=%s",
        reviews,
        metadata,
        graph_nodes,
        graph_edges,
        db_counts.get("graph_nodes", 0),
        (stage_results or {}).get("knowledge_graph", {}).get("total_nodes"),
        operation_id or "—",
    )

    graph_runtime = validate_graph_consistency(session)
    logger.info(
        "[GRAPH_RUNTIME] valid=%s node_count=%d edge_count=%d issues=%s op=%s",
        graph_runtime.get("valid"),
        graph_runtime.get("node_count"),
        graph_runtime.get("edge_count"),
        graph_runtime.get("issues"),
        operation_id or "—",
    )

    runtime_reconciled = False
    if graph_runtime.get("node_count", 0) > graph_nodes:
        graph_nodes = int(graph_runtime["node_count"])
        counts["graph_nodes"] = graph_nodes
        runtime_reconciled = True
    if graph_runtime.get("edge_count", 0) > graph_edges:
        graph_edges = int(graph_runtime["edge_count"])
        counts["graph_edges"] = graph_edges
        runtime_reconciled = True

    dep_report = signal_dependency_report(session)
    contract = check_stage_contract("fusion", counts)

    blockers: list[str] = []
    if reviews < _MIN_REVIEWS:
        blockers.append("no_reviews")
    if metadata < 0:
        blockers.append("metadata_unreadable")
    elif metadata < _MIN_METADATA:
        blockers.append("no_metadata")
    if graph_nodes < 0:
        blockers.append("graph_unreadable")
    elif graph_nodes < _MIN_GRAPH_NODES:
        blockers.append("no_graph_nodes")

    # False-empty guard: DB or runtime graph populated but contract failed on stale snapshot
    false_empty = (
        len(blockers) > 0
        and (
            graph_runtime.get("node_count", 0) >= _MIN_GRAPH_NODES
            or _positive((stage_results or {}).get("knowledge_graph", {}).get("total_nodes"))
            >= _MIN_GRAPH_NODES
        )
        and graph_nodes < _MIN_GRAPH_NODES
    )
    if false_empty:
        logger.warning(
            "[RECONCILIATION] false_empty_graph_detected runtime_nodes=%d contract_nodes=%d op=%s",
            graph_runtime.get("node_count"),
            graph_nodes,
            operation_id or "—",
        )
        graph_nodes = int(graph_runtime.get("node_count") or graph_nodes)
        counts["graph_nodes"] = graph_nodes
        contract = check_stage_contract("fusion", counts)
        blockers = [b for b in blockers if b != "no_graph_nodes"]

    ready = len(blockers) == 0 and contract.get("satisfied", False)
    timeout_ms = int((time.perf_counter() - started) * 1000)

    if not ready:
        degraded_reason = "; ".join(contract.get("failures") or blockers) or "upstream_not_ready"
        logger.warning(
            "[PIPELINE_DEGRADED] semantic_correlation_upstream_not_ready reason=%s blockers=%s op=%s",
            degraded_reason,
            blockers,
            operation_id or "—",
        )
    else:
        logger.info(
            "[SEMANTIC_CORRELATION] upstream_ready nodes=%d edges=%d metadata=%d timeout_ms=%d op=%s",
            graph_nodes,
            graph_edges,
            metadata,
            timeout_ms,
            operation_id or "—",
        )

    return {
        "ready": ready,
        "counts": counts,
        "db_counts": db_counts,
        "graph_runtime": graph_runtime,
        "dependency_report": dep_report,
        "contract": contract,
        "blockers": blockers,
        "false_empty_prevented": false_empty or runtime_reconciled,
        "runtime_graph_reconciled": runtime_reconciled,
        "graph_nodes_loaded": graph_nodes,
        "graph_edges_loaded": graph_edges,
        "metadata_loaded": max(metadata, 0),
        "records_loaded": reviews,
        "validation_ms": timeout_ms,
    }


def should_skip_aviation_enrichment(
    session: Session,
    *,
    validation: dict[str, Any],
) -> tuple[bool, str]:
    """Skip expensive aviation pass when corpus already linked or env requests it."""
    if os.getenv("FUSION_SKIP_AVIATION_ENRICHMENT", "0").lower() in ("1", "true", "yes"):
        return True, "env_skip"

    if os.getenv("FUSION_SAFE_MODE", "0").lower() in ("1", "true", "yes"):
        return False, "safe_mode_still_runs_limited"

    counts = validation.get("counts") or {}
    nodes = counts.get("graph_nodes", 0)
    meta = counts.get("review_intelligence", 0)
    if nodes >= 1000 and meta >= 500:
        try:
            from database.models.aviation import AirlineAirport

            links = session.query(AirlineAirport).count()
            if links >= 50:
                logger.info(
                    "[SEMANTIC_CORRELATION] skip_aviation_enrichment links=%d nodes=%d metadata=%d",
                    links,
                    nodes,
                    meta,
                )
                return True, f"sufficient_links_{links}"
        except Exception as exc:
            logger.debug("[UPSTREAM_VALIDATION] link check skipped: %s", exc)

    return False, "enrichment_required"
