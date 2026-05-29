"""KPI governance — graph semantics, aviation delta vs accumulated."""

from __future__ import annotations

from analytics.kpi_governance import (
    CANONICAL_KPI_REGISTRY,
    _detect_divergences,
    _delta_from_stage,
    resolve_authoritative_kpi,
)


def test_graph_entities_equals_nodes_plus_edges():
    acc = {"graph_nodes": 5219, "graph_edges": 9480}
    entities = acc["graph_nodes"] + acc["graph_edges"]
    assert entities == 14699


def test_detect_divergence_when_live_sums_nodes_and_edges():
    acc = {"graph_nodes": 5219, "graph_edges": 9480}
    live = {"graph_nodes": 5219, "graph_edges": 9480}
    div = _detect_divergences(acc, live)
    assert len(div) >= 1
    assert div[0]["reason"] == "live_graph_kpi_sums_nodes_and_edges"


def test_aviation_delta_from_stage():
    delta = _delta_from_stage(
        {
            "aviation_master": {
                "airlines_created": 1,
                "airlines_updated": 1,
                "links_created": 0,
                "airlines_total": 1246,
                "airlines_linked_total": 143,
            }
        }
    )
    assert delta["aviation_processed_this_run"] == 2
    assert delta["aviation_linked_this_run"] == 0


def test_registry_graph_nodes_semantic():
    spec = CANONICAL_KPI_REGISTRY["graph_nodes"]
    assert spec["kind"] == "accumulated"
    assert "NOT nodes+edges" in spec["semantic"]


def test_resolve_authoritative_kpi_delta_vs_accumulated():
    payload = {
        "accumulated_kpis": {"aviation_metadata_total": 1246, "aviation_linked_total": 143},
        "delta_kpis": {"aviation_processed_this_run": 2, "aviation_linked_this_run": 0},
    }
    assert resolve_authoritative_kpi("aviation_metadata_total", payload) == 1246
    assert resolve_authoritative_kpi("aviation_processed_this_run", payload) == 2
