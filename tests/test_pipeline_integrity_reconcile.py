"""Tests for pipeline integrity KPI reconciliation."""

from __future__ import annotations

from analytics.pipeline_integrity import (
    live_kpis_from_stage_results,
    reconcile_integrity_metrics,
)


def test_reconcile_metadata_coverage_when_live_metadata_positive():
    out = reconcile_integrity_metrics(
        table_counts={"reviews": 0, "review_intelligence": 0},
        coverage={},
        live_kpis={"reviews": 27998, "metadata": 27998},
    )
    assert out["coverage"]["metadata_coverage_pct"] == 100.0
    assert out["table_counts"]["reviews"] == 27998
    assert out["integrity_reconciled"] is True


def test_reconcile_graph_signals_anomalies_from_runtime():
    out = reconcile_integrity_metrics(
        table_counts={
            "graph_nodes": 0,
            "fusion_signals": 0,
            "anomaly_events": 0,
            "metric_snapshots": 0,
        },
        live_kpis={"graph_nodes": 14699, "signals": 1123, "anomalies": 8674, "snapshots": 42},
    )
    assert out["table_counts"]["graph_nodes"] == 14699
    assert out["table_counts"]["fusion_signals"] == 1123
    assert out["table_counts"]["anomaly_events"] == 8674
    assert out["table_counts"]["metric_snapshots"] == 42


def test_reconcile_impossible_state_detected():
    out = reconcile_integrity_metrics(
        table_counts={"fusion_signals": 0},
        live_kpis={"signals": 500},
    )
    assert any(i["metric"] == "fusion_signals" for i in out["impossible_kpi_states"])
    assert out["table_counts"]["fusion_signals"] == 500


def test_live_kpis_from_stage_results():
    kpis = live_kpis_from_stage_results(
        {
            "fusion": {"signals_generated": 99},
            "knowledge_graph": {"total_nodes": 1200},
        }
    )
    assert kpis["signals"] == 99
    assert kpis["graph_nodes"] == 1200


def test_postgres_wins_when_higher_than_runtime():
    out = reconcile_integrity_metrics(
        table_counts={"reviews": 50000},
        live_kpis={"reviews": 100},
    )
    assert out["table_counts"]["reviews"] == 50000
    assert out["integrity_reconciled"] is False
