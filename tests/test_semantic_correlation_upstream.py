"""Semantic correlation upstream validation — false empty graph prevention."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from analytics.semantic_correlation_upstream import (
    merge_upstream_counts,
    validate_semantic_correlation_upstream,
)


def test_merge_upstream_counts_prefers_pipeline_knowledge_graph():
    db = {"graph_nodes": 0, "graph_edges": 0, "review_intelligence": 10, "reviews": 100}
    merged = merge_upstream_counts(
        db,
        stage_results={"knowledge_graph": {"total_nodes": 5224, "total_edges": 9492}},
        pipeline_kpis={"graph_nodes": 5200, "metadata": 28019},
    )
    assert merged["graph_nodes"] == 5224
    assert merged["graph_edges"] == 9492
    assert merged["review_intelligence"] == 28019


def test_validate_prevents_false_empty_when_runtime_has_nodes():
    """DB count=0 but runtime graph populated (stale snapshot / race) must not block fusion."""
    session = MagicMock()
    db_counts = {"reviews": 500, "review_intelligence": 28019, "graph_nodes": 0, "graph_edges": 0}
    with patch("analytics.semantic_correlation_upstream.collect_table_counts", return_value=db_counts):
        with patch(
            "analytics.semantic_correlation_upstream.validate_graph_consistency",
            return_value={"valid": True, "node_count": 5224, "edge_count": 9492, "issues": []},
        ):
            with patch(
                "analytics.semantic_correlation_upstream.signal_dependency_report",
                return_value={"blockers": []},
            ):
                out = validate_semantic_correlation_upstream(
                    session,
                    stage_results={},
                    operation_id="op-test",
                )
    assert out["ready"] is True
    assert out.get("runtime_graph_reconciled") or out.get("false_empty_prevented")
    assert out["graph_nodes_loaded"] == 5224


def test_validate_ready_when_pipeline_stage_results_have_graph():
    session = MagicMock()
    db_counts = {"reviews": 500, "review_intelligence": 28019, "graph_nodes": 0, "graph_edges": 0}
    with patch("analytics.semantic_correlation_upstream.collect_table_counts", return_value=db_counts):
        with patch(
            "analytics.semantic_correlation_upstream.validate_graph_consistency",
            return_value={"valid": True, "node_count": 5224, "edge_count": 9492, "issues": []},
        ):
            with patch(
                "analytics.semantic_correlation_upstream.signal_dependency_report",
                return_value={"blockers": []},
            ):
                out = validate_semantic_correlation_upstream(
                    session,
                    stage_results={"knowledge_graph": {"total_nodes": 5224, "total_edges": 9492}},
                    operation_id="op-kg",
                )
    assert out["ready"] is True
    assert out["graph_nodes_loaded"] == 5224


def test_validate_fails_when_truly_empty():
    session = MagicMock()
    db_counts = {"reviews": 0, "review_intelligence": 0, "graph_nodes": 0, "graph_edges": 0}
    with patch("analytics.semantic_correlation_upstream.collect_table_counts", return_value=db_counts):
        with patch(
            "analytics.semantic_correlation_upstream.validate_graph_consistency",
            return_value={"valid": True, "node_count": 0, "edge_count": 0, "issues": []},
        ):
            with patch(
                "analytics.semantic_correlation_upstream.signal_dependency_report",
                return_value={"blockers": ["no_reviews", "no_metadata", "no_graph_nodes"]},
            ):
                out = validate_semantic_correlation_upstream(session, operation_id="op-empty")
    assert out["ready"] is False
    assert "no_reviews" in out["blockers"] or out["contract"]["satisfied"] is False


def test_fusion_stage_enrichment_warning_not_counted_as_failed():
    from worker.orchestration.operational_reconciliation import derive_failed_stages

    results = {
        "fusion": {
            "signals_generated": 155,
            "fusion_status": "completed",
            "enrichment_warning": True,
            "stage_warning": True,
            "warning_reason": "aviation_enrichment_timeout",
            "fusion": {"signals_generated": 155},
        },
    }
    errors = []
    failed = derive_failed_stages(errors, results)
    assert "fusion" not in failed
