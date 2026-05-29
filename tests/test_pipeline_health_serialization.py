"""Pipeline health JSON-safe payloads and governance serialization."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_project_module(dotted: str, rel_path: str):
    """Load module by file path (pytest-safe when `api` package resolution differs)."""
    if dotted in sys.modules:
        return sys.modules[dotted]
    path = _ROOT / rel_path
    spec = importlib.util.spec_from_file_location(dotted, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod
    spec.loader.exec_module(mod)
    return mod


_load_project_module("app.payload_serialization", "app/payload_serialization.py")
phs = _load_project_module("api.pipeline_health_service", "api/pipeline_health_service.py")

safe_json_payload = sys.modules["app.payload_serialization"].safe_json_payload
safe_json_value = sys.modules["app.payload_serialization"].safe_json_value
build_pipeline_health_payload = phs.build_pipeline_health_payload
resolve_pipeline_governance = phs.resolve_pipeline_governance
_extract_governance_fields = phs._extract_governance_fields


class SampleEnum(Enum):
    ACTIVE = "active"


def test_safe_json_payload_datetime_decimal_set_enum():
    raw = {
        "at": datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        "amount": Decimal("12.5"),
        "tags": {"a", "b"},
        "state": SampleEnum.ACTIVE,
        "nested": [{"x": Decimal("1")}],
    }
    out = safe_json_payload(raw, context="test")
    json.dumps(out)
    assert out["at"].startswith("2026-05-27")
    assert out["amount"] == 12.5
    assert sorted(out["tags"]) == ["a", "b"]
    assert out["state"] == "active"


def test_safe_json_payload_max_depth():
    deep = {"a": 1}
    cur = deep
    for _ in range(40):
        cur["b"] = {}
        cur = cur["b"]
    out = safe_json_payload(deep)
    json.dumps(out)


def test_extract_governance_fields_serializable():
    report = {
        "canonical_kpis": {"graph_nodes": 5},
        "accumulated_kpis": {"graph_nodes": 5},
        "delta_kpis": {"aviation_processed_this_run": 2},
        "kpi_governance": {"registry_version": 1},
        "metric_lineage": {
            "graph_nodes": {
                "value": 5,
                "reconciled_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        "metric_semantics": {"graph_nodes": "nodes"},
        "integrity_reconciled": True,
        "integrity_consistent": True,
    }
    gov = _extract_governance_fields(report, source="test")
    normalized = safe_json_value(gov)
    json.dumps(normalized)
    assert normalized["governance_source"] == "test"


def test_resolve_pipeline_governance_empty_fallback():
    with patch("analytics.pipeline_integrity.load_authoritative_integrity_snapshot", return_value=None):
        with patch("analytics.pipeline_integrity.load_live_kpis_from_redis", return_value={}):
            gov = resolve_pipeline_governance({})
    json.dumps(safe_json_value(gov))
    assert gov["governance_source"] == "none"


def test_resolve_pipeline_governance_from_snapshot():
    cached = {
        "table_counts": {"graph_nodes": 10, "graph_edges": 5},
        "coverage": {},
        "canonical_kpis": {"graph_nodes": 10, "graph_edges": 5},
        "accumulated_kpis": {"graph_nodes": 10, "graph_edges": 5},
        "delta_kpis": {},
        "kpi_governance": {},
        "metric_lineage": {},
        "metric_semantics": {},
        "integrity_reconciled": True,
        "integrity_consistent": True,
    }
    with patch("analytics.pipeline_integrity.load_authoritative_integrity_snapshot", return_value=cached):
        with patch("analytics.pipeline_integrity.load_live_kpis_from_redis", return_value={}):
            with patch(
                "analytics.pipeline_integrity.reconcile_integrity_metrics",
                return_value={"integrity_consistent": True},
            ):
                gov = resolve_pipeline_governance({"kpis": {}, "stage_results": {}})
    json.dumps(safe_json_value(gov))
    assert gov["governance_source"] == "redis_snapshot"
    assert gov["authoritative_kpis"]["graph_nodes"] == 10


def test_build_pipeline_health_payload_minimal():
    settings = MagicMock()
    settings.environment = "test"
    settings.schema_block_on_drift = False

    flags = {
        "forecast_safe_mode_active": False,
        "forecast_safe_mode_env": "0",
        "schema_drift": False,
        "blocked_stages": [],
        "native_crash_count": 0,
        "subprocess_cooldown_active": False,
        "degraded_history_count": 0,
    }

    with patch("api.pipeline_health_service.get_state", return_value={"blocked_stages": []}):
        with patch("api.pipeline_health_service.get_last_startup_report", return_value=None):
            with patch(
                "api.pipeline_health_service._quick_pipeline_status",
                return_value={"running": False, "stage": "idle"},
            ):
                with patch(
                    "api.pipeline_health_service.resolve_pipeline_governance",
                    return_value={
                        "authoritative_kpis": {},
                        "canonical_kpis": {},
                        "accumulated_kpis": {},
                        "delta_kpis": {},
                        "kpi_governance": {},
                        "kpi_lineage": {},
                        "metric_lineage": {},
                        "metric_semantics": {},
                        "integrity_reconciled": False,
                        "integrity_consistent": True,
                        "runtime_authoritative": False,
                        "governance_source": "none",
                    },
                ):
                    with patch("api.pipeline_health_service.get_degraded_history", return_value=[]):
                        payload = build_pipeline_health_payload(
                            settings=settings,
                            runtime_flags=flags,
                            migrate_policy="validate_only",
                        )

    json.dumps(payload)
    assert payload["readiness"] in ("ready", "degraded", "blocked")
    assert payload["payload_safe"] is True
    assert "canonical_kpis" in payload


def test_kpi_governance_resolve_serializable():
    from analytics.kpi_governance import resolve_authoritative_kpis

    session = MagicMock()
    with patch(
        "analytics.pipeline_integrity.kpi_totals_from_db", return_value={"graph_nodes": 3, "graph_edges": 2}
    ):
        with patch(
            "analytics.kpi_governance._aviation_accumulated_counts",
            return_value={"aviation_metadata_total": 0, "aviation_linked_total": 0},
        ):
            gov = resolve_authoritative_kpis(session, live_kpis={"graph_nodes": 3, "graph_edges": 2})
    json.dumps(gov)
    assert gov["canonical_kpis"]["graph_nodes"] == 3


def test_malformed_governance_partial():
    report = {
        "canonical_kpis": "not-a-dict",
        "metric_lineage": None,
    }
    gov = _extract_governance_fields(report, source="malformed")
    out = safe_json_value(gov)
    json.dumps(out)
    assert out["authoritative_kpis"] == {}


def test_stage_results_bytes_json_serializable():
    """OperationalRefreshRun.stage_results must survive JSONB (crawl stderr may be bytes)."""
    raw = {
        "crawl": {"stderr": b"scrapy warning", "exit_code": 0},
        "governor": {"last_line": b"pid=1 state=running"},
    }
    normalized = safe_json_value(raw)
    payload = json.dumps(normalized)
    assert "scrapy warning" in payload
    assert isinstance(normalized["crawl"]["stderr"], str)
