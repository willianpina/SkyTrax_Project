"""Pipeline integrity — lineage, dependency contracts, KPI mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from analytics.pipeline_integrity import (
    check_stage_contract,
    kpi_totals_from_db,
    signal_dependency_report,
    validate_graph_consistency,
)
from analytics.pipeline_lineage import export_lineage_report
from analytics.pipeline_lineage import DEPENDENCY_CONTRACTS, STAGE_LINEAGE


def test_lineage_export_has_all_stages():
    report = export_lineage_report()
    assert report["version"] == "1.0"
    stage_names = {s["stage"] for s in report["stages"]}
    assert "metadata" in stage_names
    assert "knowledge_graph" in stage_names
    assert "fusion" in stage_names


def test_dependency_contract_knowledge_graph_requires_metadata():
    contract = DEPENDENCY_CONTRACTS["knowledge_graph"]
    assert contract.get("metadata_records") == 1
    result = check_stage_contract("knowledge_graph", {"review_intelligence": 0, "reviews": 100})
    assert result["satisfied"] is False
    assert any("metadata_records" in f for f in result["failures"])


def test_dependency_contract_satisfied():
    result = check_stage_contract(
        "knowledge_graph",
        {"review_intelligence": 50, "reviews": 100},
    )
    assert result["satisfied"] is True


def test_fusion_requires_graph_nodes():
    result = check_stage_contract("fusion", {"reviews": 100, "graph_nodes": 0})
    assert result["satisfied"] is False


def test_anomalies_requires_forecasts():
    result = check_stage_contract("anomalies", {"reviews": 100, "forecast_snapshots": 0})
    assert result["satisfied"] is False
    ok = check_stage_contract("anomalies", {"reviews": 100, "forecast_snapshots": 10})
    assert ok["satisfied"] is True


def test_signal_dependency_report_blockers():
    counts = {"reviews": 0, "review_intelligence": 0, "graph_nodes": 0, "fusion_signals": 0}
    with patch("analytics.pipeline_integrity.collect_table_counts", return_value=counts):
        report = signal_dependency_report(MagicMock())
    assert "no_reviews" in report["blockers"]


def test_signal_dependency_knowledge_graph_blocked_by_metadata():
    counts = {"reviews": 100, "review_intelligence": 0, "graph_nodes": 0, "fusion_signals": 0}
    with patch("analytics.pipeline_integrity.collect_table_counts", return_value=counts):
        report = signal_dependency_report(MagicMock())
    assert report["knowledge_graph_blocked_by"] == "metadata"
    assert "no_metadata" in report["blockers"]


def test_dependency_contract_unreadable_metadata_fails():
    result = check_stage_contract(
        "knowledge_graph",
        {"review_intelligence": -1, "reviews": 100},
    )
    assert result["satisfied"] is False
    assert any("unreadable" in f for f in result["failures"])


def test_safe_count_on_query_failure_returns_negative():
    from analytics.pipeline_integrity import _safe_count

    session = MagicMock()
    session.query.side_effect = Exception("no db")
    model = MagicMock()
    model.id = "id"
    assert _safe_count(session, model, "reviews") == -1


def test_kpi_totals_from_db_mapping():
    session = MagicMock()
    with patch("analytics.pipeline_integrity.collect_table_counts") as mock_counts:
        mock_counts.return_value = {
            "reviews": 100,
            "review_intelligence": 80,
            "graph_nodes": 50,
            "graph_edges": 120,
            "fusion_signals": 5,
            "anomaly_events": 2,
            "semantic_clusters": 10,
            "forecast_snapshots": 3,
            "executive_insights": 4,
        }
        totals = kpi_totals_from_db(session)
    assert totals["metadata"] == 80
    assert totals["signals"] == 5


def test_validate_graph_consistency_no_edges():
    session = MagicMock()
    m = {"GraphNode": MagicMock(), "GraphEdge": MagicMock()}
    with patch("analytics.pipeline_integrity._models", return_value=m):
        with patch("analytics.pipeline_integrity._safe_count", side_effect=[10, 0]):
            result = validate_graph_consistency(session)
    assert result["valid"] is True


def test_stage_lineage_metadata_downstream():
    meta = STAGE_LINEAGE["metadata"]
    assert "knowledge_graph" in meta["downstream"]
