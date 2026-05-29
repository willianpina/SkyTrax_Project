"""FastAPI startup stability — imports, routes, Pydantic contract."""

from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_module(dotted: str, rel: str):
    if dotted in sys.modules:
        return sys.modules[dotted]
    path = _ROOT / rel
    spec = importlib.util.spec_from_file_location(dotted, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pipeline_health_response_schema_alias_no_shadow_warning():
    schemas_mod = _load_module("api.schemas", "api/schemas.py")
    PipelineHealthResponse = schemas_mod.PipelineHealthResponse

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PipelineHealthResponse.model_json_schema()
    for item in caught:
        assert "shadows an attribute" not in str(item.message)


def test_pipeline_health_response_serializes_schema_key():
    PipelineHealthResponse = _load_module("api.schemas", "api/schemas.py").PipelineHealthResponse

    model = PipelineHealthResponse.model_validate(
        {"status": "ready", "schema": {"healthy": True, "summary_source": "test"}},
    )
    dumped = model.model_dump(mode="json", by_alias=True)
    assert "schema" in dumped
    assert dumped["schema"]["healthy"] is True
    json.dumps(dumped)


def test_boot_pipeline_health_contract():
    boot_fn = _load_module("api.startup_health", "api/startup_health.py").boot_pipeline_health_contract
    assert boot_fn() is True


def test_ops_health_router_import_without_service_at_module_level():
    """ops_health must not bind pipeline_health_service at import (lazy load)."""
    mod = _load_module("api.routers.ops_health", "api/routers/ops_health.py")
    assert "build_pipeline_health_payload" not in mod.__dict__


def test_routes_register_enterprise_pipeline_before_runtime():
    from tests.test_health_routes import _build_health_app

    app = _build_health_app()
    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/operations/health/pipeline" in paths


def test_degraded_payload_never_raises():
    ops = _load_module("api.routers.ops_health", "api/routers/ops_health.py")
    _empty_governance_fields = ops._empty_governance_fields
    safe_json_payload = _load_module(
        "app.payload_serialization", "app/payload_serialization.py"
    ).safe_json_payload

    fallback = safe_json_payload(
        {
            "status": "degraded",
            "readiness": "degraded",
            "schema": {"healthy": False},
            **_empty_governance_fields(),
        },
        context="test",
    )
    json.dumps(fallback)


def test_validate_pipeline_health_contract_repair():
    validate_pipeline_health_contract = _load_module(
        "api.pipeline_health_service", "api/pipeline_health_service.py"
    ).validate_pipeline_health_contract

    out = validate_pipeline_health_contract({"status": "ready", "schema": {"healthy": True}})
    assert out["status"] == "ready"
    assert out["schema"]["healthy"] is True
