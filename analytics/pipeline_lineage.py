"""Pipeline data lineage — stage contracts, dependencies, and audit definitions."""

from __future__ import annotations

from typing import Any

# Each stage: inputs, outputs, tables, KPI keys, upstream/downstream
STAGE_LINEAGE: dict[str, dict[str, Any]] = {
    "discovery": {
        "inputs": ["airlines table", "airline_discovery spider"],
        "outputs": ["airline URLs", "active airline count"],
        "tables": ["airlines"],
        "kpi_keys": ["airlines"],
        "depends_on": [],
        "required_upstream": {},
        "downstream": ["crawl"],
    },
    "crawl": {
        "inputs": ["airline review URLs", "max_pages config"],
        "outputs": ["reviews", "airline records"],
        "tables": ["airlines", "reviews"],
        "kpi_keys": ["reviews"],
        "depends_on": ["discovery"],
        "required_upstream": {},
        "downstream": ["metadata", "semantic"],
    },
    "metadata": {
        "inputs": ["reviews without review_intelligence"],
        "outputs": ["review_intelligence rows"],
        "tables": ["reviews", "review_intelligence"],
        "kpi_keys": ["metadata"],
        "depends_on": ["crawl"],
        "required_upstream": {"reviews": 1},
        "downstream": ["knowledge_graph", "fusion"],
    },
    "semantic": {
        "inputs": ["reviews without nlp_results"],
        "outputs": ["nlp_results", "semantic_clusters", "topic_snapshots"],
        "tables": ["reviews", "nlp_results", "semantic_clusters", "topic_snapshots"],
        "kpi_keys": ["clusters", "enriched"],
        "depends_on": ["crawl"],
        "required_upstream": {"reviews": 1},
        "downstream": ["insights", "snapshots"],
    },
    "knowledge_graph": {
        "inputs": ["airlines", "review_intelligence", "aviation metadata"],
        "outputs": ["graph_nodes", "graph_edges"],
        "tables": ["graph_nodes", "graph_edges", "review_intelligence", "airlines"],
        "kpi_keys": ["graph_nodes", "graph_edges"],
        "depends_on": ["metadata", "crawl"],
        "required_upstream": {"metadata_records": 1},
        "downstream": ["fusion"],
    },
    "forecasting": {
        "inputs": ["reputation history", "reviews", "nlp_results"],
        "outputs": ["forecast_snapshots"],
        "tables": ["forecast_snapshots", "reputation_score_history", "reviews", "nlp_results"],
        "kpi_keys": ["forecasts"],
        "depends_on": ["crawl", "semantic"],
        "required_upstream": {"reviews": 1},
        "downstream": ["anomalies"],
    },
    "anomalies": {
        "inputs": ["reviews", "nlp_results", "topic_snapshots", "forecast_snapshots"],
        "outputs": ["anomaly_events"],
        "tables": ["anomaly_events", "reviews", "nlp_results", "forecast_snapshots"],
        "kpi_keys": ["anomalies"],
        "depends_on": ["crawl", "semantic", "forecasting"],
        "required_upstream": {"reviews": 1, "forecasts": 1},
        "downstream": ["insights", "fusion"],
    },
    "insights": {
        "inputs": ["reviews", "nlp_results", "reputation scores"],
        "outputs": ["executive_insights"],
        "tables": ["executive_insights", "reviews", "nlp_results"],
        "kpi_keys": ["insights"],
        "depends_on": ["semantic", "crawl"],
        "required_upstream": {"reviews": 1},
        "downstream": ["snapshots"],
    },
    "aviation_master": {
        "inputs": ["OpenFlights", "OurAirports"],
        "outputs": ["airline_metadata", "airport_metadata"],
        "tables": ["airline_metadata", "airport_metadata", "alliances"],
        "kpi_keys": [],
        "depends_on": [],
        "required_upstream": {},
        "downstream": ["knowledge_graph", "fusion"],
    },
    "fusion": {
        "inputs": ["reviews", "review_intelligence", "graph_nodes", "alliances"],
        "outputs": ["fusion_signals"],
        "tables": ["fusion_signals", "review_intelligence", "reviews", "graph_nodes"],
        "kpi_keys": ["signals"],
        "depends_on": ["metadata", "knowledge_graph", "crawl"],
        "required_upstream": {"reviews": 1, "graph_nodes": 1},
        "downstream": [],
    },
    "snapshots": {
        "inputs": ["reviews", "nlp_results", "reputation scores", "topic_snapshots"],
        "outputs": ["metric_snapshots"],
        "tables": ["metric_snapshots", "reviews", "nlp_results"],
        "kpi_keys": [],
        "depends_on": ["crawl", "semantic"],
        "required_upstream": {"reviews": 1},
        "downstream": [],
    },
}

DEPENDENCY_CONTRACTS: dict[str, dict[str, Any]] = {
    stage: spec["required_upstream"] for stage, spec in STAGE_LINEAGE.items() if spec.get("required_upstream")
}

STAGE_SKIP_MESSAGES: dict[str, str] = {
    "metadata": "Metadata skipped — no reviews in corpus",
    "knowledge_graph": "Knowledge graph skipped — review_intelligence empty (run metadata first)",
    "fusion": "Correlação semântica adiada — contrato upstream não satisfeito (verificar contagens reais)",
    "anomalies": "Anomaly detection skipped — insufficient review history",
    "insights": "Executive insights skipped — no enriched reviews",
    "snapshots": "Snapshot persistence skipped — missing upstream data",
    "forecasting": "Forecasting degraded — insufficient time series",
}


def export_lineage_report() -> dict[str, Any]:
    """Full lineage document for pipeline_lineage_report.json."""
    stages = []
    for name, spec in STAGE_LINEAGE.items():
        stages.append(
            {
                "stage": name,
                "inputs": spec["inputs"],
                "outputs": spec["outputs"],
                "tables": spec["tables"],
                "kpi_keys": spec["kpi_keys"],
                "depends_on": spec["depends_on"],
                "required_upstream": spec["required_upstream"],
                "downstream": spec["downstream"],
            }
        )
    return {
        "version": "1.0",
        "flow": (
            "discovery → crawl → metadata → semantic → knowledge_graph → "
            "forecasting → anomalies → insights → aviation_master → fusion → snapshots"
        ),
        "stages": stages,
        "dependency_contracts": DEPENDENCY_CONTRACTS,
    }
