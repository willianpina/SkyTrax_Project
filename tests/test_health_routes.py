"""Operations health endpoint registration and availability."""

from __future__ import annotations

import ast
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Drop stale `api` entries (pytest may cache a wrong module before pythonpath applies).
for _key in list(sys.modules):
    if _key == "api" or _key.startswith("api."):
        del sys.modules[_key]

EXPECTED_HEALTH_ROUTES = (
    "/api/operations/health/schema",
    "/api/operations/health/native",
    "/api/operations/health/integrity",
    "/api/operations/health/pipeline",
)

# Stub DB before loading ops_health router.
_session_stub = types.ModuleType("database.session")
_session_stub.engine = MagicMock()
_session_stub.SessionLocal = MagicMock()
_session_stub.get_session = MagicMock()
_session_stub.Base = MagicMock()
sys.modules.setdefault("database.session", _session_stub)


def _get_ops_health_router():
    """Load ops_health without relying on pytest's `api` package resolution."""
    import importlib.util

    for pkg_name, pkg_dir in (
        ("api", _ROOT / "api"),
        ("api.routers", _ROOT / "api" / "routers"),
    ):
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
            sys.modules[pkg_name] = pkg

    path = _ROOT / "api" / "routers" / "ops_health.py"
    mod_name = "api.routers.ops_health"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.router


def _collect_route_paths(app: FastAPI) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes if getattr(route, "path", None)}


def _validate_health_routes(app: FastAPI) -> dict:
    paths = _collect_route_paths(app)
    missing = [p for p in EXPECTED_HEALTH_ROUTES if p not in paths]
    present = [p for p in EXPECTED_HEALTH_ROUTES if p in paths]
    return {"valid": len(missing) == 0, "missing": missing, "present": present}


def _build_health_app() -> FastAPI:
    """Minimal app mirroring production mount: /api/operations/health/*."""
    app = FastAPI()
    api_router = APIRouter(prefix="/api")
    api_router.include_router(_get_ops_health_router(), prefix="/operations")
    app.include_router(api_router)
    return app


@pytest.fixture
def ops_health_module():
    _get_ops_health_router()
    return sys.modules["api.routers.ops_health"]


@pytest.fixture
def health_app(ops_health_module):
    app = FastAPI()
    api_router = APIRouter(prefix="/api")
    api_router.include_router(ops_health_module.router, prefix="/operations")
    app.include_router(api_router)
    return app


@pytest.fixture
def client(health_app):
    return TestClient(health_app)


def test_health_routes_registered_on_app():
    report = _validate_health_routes(_build_health_app())
    assert report["valid"] is True, f"Missing routes: {report['missing']}"


def test_openapi_exposes_health_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for route in EXPECTED_HEALTH_ROUTES:
        assert route in paths, f"{route} not in OpenAPI"


def test_schema_health_endpoint(client):
    mock_report = {
        "healthy": True,
        "status": "ok",
        "readiness": "ready",
        "missing_tables": [],
        "migration_drift": False,
        "summary_source": "startup_cache",
    }
    with patch("api.routers.ops_health.get_schema_health_fast", return_value=mock_report):
        res = client.get("/api/operations/health/schema")
    assert res.status_code == 200
    body = res.json()
    assert body["healthy"] is True
    assert body["summary_source"] == "startup_cache"


def test_pipeline_health_endpoint(client, ops_health_module):
    mock_payload = {
        "status": "ready",
        "readiness": "ready",
        "environment": "test",
        "degraded": False,
        "pipeline": {"running": False, "stage": "idle"},
        "schema": {"healthy": True, "summary_source": "startup_cache"},
        "canonical_kpis": {"graph_nodes": 1},
        "accumulated_kpis": {"graph_nodes": 1},
        "delta_kpis": {},
        "kpi_governance": {},
        "metric_lineage": {},
        "metric_semantics": {},
        "payload_safe": True,
    }
    with patch(
        "api.pipeline_health_service.build_pipeline_health_payload",
        return_value=mock_payload,
    ):
        res = client.get("/api/operations/health/pipeline")
    assert res.status_code == 200
    body = res.json()
    assert body["readiness"] == "ready"
    assert body["payload_safe"] is True
    assert "canonical_kpis" in body


def test_integrity_health_endpoint(client):
    mock_body = {
        "status": "ok",
        "readiness": "ready",
        "healthy": True,
        "integrity_consistent": True,
        "table_counts": {},
        "summary_source": "redis_snapshot",
    }
    with patch("api.routers.ops_health.get_integrity_health_fast", return_value=mock_body):
        res = client.get("/api/operations/health/integrity")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_native_health_endpoint(client, ops_health_module):
    with patch("app.native_health.collect_native_health") as mock_native:
        mock_native.return_value = {"any_segfault_detected": False, "dependencies": {}}
    with patch.object(ops_health_module, "get_state", return_value={}):
        res = client.get("/api/operations/health/native")
    assert res.status_code == 200


def test_legacy_ops_paths_not_registered(client):
    assert client.get("/ops/health/schema").status_code == 404


def test_routes_py_includes_ops_health_router():
    source = (_ROOT / "api" / "routes.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.ImportFrom) and node.module == "api.routers.ops_health"
        for node in ast.walk(tree)
    )
    assert "ops_health_router" in source
    assert 'prefix="/operations"' in source


def test_main_py_does_not_mount_ops_health_standalone():
    source = (_ROOT / "api" / "main.py").read_text(encoding="utf-8")
    assert "ops_health_router" not in source or "include_router(ops_health_router)" not in source
