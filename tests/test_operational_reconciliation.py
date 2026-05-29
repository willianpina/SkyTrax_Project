"""Tests for KPI-driven operational reconciliation."""

from __future__ import annotations

from unittest.mock import patch

from worker.orchestration.operational_reconciliation import (
    derive_failed_stages,
    reconcile_live_status_payload,
    reconcile_pipeline_events,
    validate_operational_consistency,
)


def test_validate_operational_consistency_detects_signals_mismatch():
    report = validate_operational_consistency(
        kpis={"signals": 121},
        results={"fusion": {"error": "Sinais indisponíveis — grafo ou metadados upstream vazios"}},
        errors=[{"stage": "fusion", "error": "unavailable"}],
        failed_stages=["fusion"],
        schema={},
    )
    assert report["inconsistency_detected"] is True
    assert any(i["stage"] == "fusion" for i in report["inconsistencies"])


def test_reconcile_pipeline_events_clears_fusion_when_signals_positive():
    errors = [
        {
            "stage": "fusion",
            "error": "Sinais indisponíveis — grafo ou metadados upstream vazios",
            "soft": True,
        }
    ]
    results = {
        "fusion": {
            "error": "Sinais indisponíveis — grafo ou metadados upstream vazios",
            "dependency_contract_failed": True,
        }
    }
    with patch("database.schema_health.validate_schema", return_value={"canonical_aviation_valid": True}):
        with patch(
            "database.runtime_schema.get_runtime_schema_report",
            return_value={"runtime_schema_consistent": True},
        ):
            with patch("app.runtime_state.remove_false_degraded_events"):
                out = reconcile_pipeline_events(
                    operation_id="op-fusion",
                    errors=errors,
                    results=results,
                    events=[
                        {
                            "message": "Stage 'fusion' degraded (120ms): unavailable",
                            "operation_id": "op-fusion",
                        }
                    ],
                    kpis={"signals": 121},
                )
    assert "fusion" not in out["failed_stages"]
    assert out["results"]["fusion"].get("reconciled") is True
    assert out["false_degraded_removed"] >= 1


def test_reconcile_aviation_when_schema_healthy():
    errors = [{"stage": "aviation_master", "error": "coluna airline_metadata.iata_code ausente"}]
    results = {"aviation_master": {"error": "coluna airline_metadata.iata_code ausente"}}
    with patch(
        "database.schema_health.validate_schema",
        return_value={
            "canonical_aviation_valid": True,
            "aviation_semantic_drift": False,
        },
    ):
        with patch(
            "database.runtime_schema.get_runtime_schema_report",
            return_value={"runtime_schema_consistent": True},
        ):
            with patch("app.runtime_state.remove_false_degraded_events"):
                out = reconcile_pipeline_events(
                    operation_id="op-av",
                    errors=errors,
                    results=results,
                    events=[],
                    kpis={},
                )
    assert "aviation_master" not in out["failed_stages"]


def test_event_run_isolation_removes_other_operation_events():
    out = reconcile_pipeline_events(
        operation_id="current-op",
        errors=[],
        results={},
        events=[
            {"message": "old", "operation_id": "previous-op"},
            {"message": "current", "operation_id": "current-op"},
        ],
        kpis={},
    )
    assert len(out["events"]) == 1
    assert out["events"][0]["message"] == "current"


def test_derive_failed_stages_ignores_reconciled_results():
    failed = derive_failed_stages(
        [],
        {"fusion": {"error": "gone", "reconciled": True}},
    )
    assert failed == []


def test_reconcile_live_status_payload_downgrades_completed_degraded():
    payload = {
        "operation_id": "op1",
        "stage": "completed_degraded",
        "running": False,
        "kpis": {"signals": 50},
        "failed_stages": ["fusion"],
        "stage_results": {
            "fusion": {"error": "Sinais indisponíveis — grafo ou metadados upstream vazios"},
        },
        "events": [],
    }
    with patch("database.schema_health.validate_schema", return_value={"canonical_aviation_valid": True}):
        with patch(
            "database.runtime_schema.get_runtime_schema_report",
            return_value={"runtime_schema_consistent": True},
        ):
            with patch("app.runtime_state.remove_false_degraded_events"):
                out = reconcile_live_status_payload(payload)
    assert out["stage"] == "completed"
    assert "fusion" not in (out.get("failed_stages") or [])
