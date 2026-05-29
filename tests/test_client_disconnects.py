"""Client disconnect and cancelled request handling."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.mark.asyncio
async def test_cancelled_with_disconnect_returns_499():
    from app.response_contract import CLIENT_DISCONNECT_STATUS, defensive_call_next
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/operations/status",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)

    async def call_next(_req):
        raise asyncio.CancelledError()

    with patch.object(request, "is_disconnected", new=AsyncMock(return_value=True)):
        response = await defensive_call_next(request, call_next)
    assert response.status_code == CLIENT_DISCONNECT_STATUS


@pytest.mark.asyncio
async def test_cancelled_without_disconnect_returns_204():
    from app.response_contract import CANCELLED_STATUS, defensive_call_next
    from starlette.requests import Request

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""}
    request = Request(scope)

    async def call_next(_req):
        raise asyncio.CancelledError()

    with patch.object(request, "is_disconnected", new=AsyncMock(return_value=False)):
        response = await defensive_call_next(request, call_next)
    assert response.status_code == CANCELLED_STATUS


@pytest.mark.asyncio
async def test_runtime_error_no_response_guard():
    from app.response_contract import defensive_call_next
    from starlette.requests import Request

    scope = {"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b""}
    request = Request(scope)

    async def call_next(_req):
        raise RuntimeError("No response returned.")

    response = await defensive_call_next(request, call_next)
    assert response.status_code == 200
    body = response.body.decode()
    assert "guard" in body or "degraded" in body
