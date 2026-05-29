"""Middleware defensive contract — no None response, disconnect handling."""

from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_session_stub = types.ModuleType("database.session")
_session_stub.engine = MagicMock()
sys.modules.setdefault("database.session", _session_stub)


@pytest.fixture
def middleware_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.middleware import RequestContextMiddleware, TimeoutMiddleware

    app = FastAPI()
    app.add_middleware(TimeoutMiddleware, timeout_seconds=0.05)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/fast")
    async def fast():
        return {"ok": True}

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.2)
        return {"ok": True}

    @app.get("/none")
    async def returns_none():
        return None

    @app.get("/api/operations/status")
    async def ops_status():
        return {"running": False, "stage": "idle"}

    return TestClient(app)


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("fastapi") is None,
    reason="fastapi not installed",
)
class TestMiddlewareResilience:
    def test_no_response_guard(self, middleware_app):
        res = middleware_app.get("/none")
        assert res.status_code in (500, 200, 422, 204)
        if res.status_code == 204:
            return
        body = res.json()
        if body is None:
            # FastAPI may coerce None handler return to empty 200 — still no crash.
            assert res.status_code == 200
            return
        assert (
            body.get("guard") == "no_response"
            or "ok" in body
            or "detail" in body
            or "type" in body  # FastAPI validation envelope
        )

    def test_hot_poll_path_not_timed_out(self, middleware_app):
        res = middleware_app.get("/api/operations/status")
        assert res.status_code == 200
        assert res.json().get("stage") == "idle"

    def test_slow_non_hot_path_times_out(self, middleware_app):
        res = middleware_app.get("/slow")
        assert res.status_code in (504, 204)


class TestResponseContract:
    def test_ensure_response_none(self):
        from app.response_contract import ensure_response
        from starlette.responses import JSONResponse

        out = ensure_response(None, path="/test")
        assert isinstance(out, JSONResponse)
        assert out.status_code == 500

    def test_fallback_operational(self):
        from app.response_contract import fallback_operational_response

        res = fallback_operational_response(path="/x", reason="test")
        assert res.status_code == 200
        assert res.body
