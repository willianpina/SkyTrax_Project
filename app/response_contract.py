"""ASGI response contract — never return None from middleware or handlers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.observability import metrics

logger = logging.getLogger(__name__)

CLIENT_DISCONNECT_STATUS = 499
CANCELLED_STATUS = 204
FALLBACK_ERROR_STATUS = 500


def ensure_response(
    response: Response | None,
    *,
    path: str = "",
    fallback_status: int = FALLBACK_ERROR_STATUS,
    detail: str = "No response produced.",
) -> Response:
    """Guarantee a valid Starlette Response (never None)."""
    if response is not None:
        return response
    metrics.inc("skytrax_no_response_guard_hits", path=path or "unknown")
    logger.warning("[NO_RESPONSE_GUARD] path=%s", path)
    return JSONResponse(
        status_code=fallback_status,
        content={"detail": detail, "guard": "no_response", "path": path},
    )


def safe_json_response(
    content: Any,
    *,
    status_code: int = 200,
    path: str = "",
) -> JSONResponse:
    """JSONResponse with contract logging on failure paths."""
    try:
        return JSONResponse(status_code=status_code, content=content)
    except Exception as exc:
        logger.exception("[SAFE_RESPONSE] serialization failed path=%s: %s", path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Response serialization failed.", "guard": "safe_json"},
        )


def fallback_operational_response(
    *,
    path: str = "",
    reason: str = "degraded",
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Minimal operational payload when hot-path handlers fail."""
    body: dict[str, Any] = {
        "status": "degraded",
        "readiness": "degraded",
        "reason": reason,
        "path": path,
        "guard": True,
    }
    if extra:
        body.update(extra)
    logger.info("[SAFE_RESPONSE] fallback path=%s reason=%s", path, reason)
    return safe_json_response(body, status_code=200, path=path)


def _is_client_disconnect(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("ClientDisconnect", "ClientDisconnected", "ConnectionResetError", "BrokenPipeError"):
        return True
    mod = type(exc).__module__ or ""
    if "starlette" in mod and "Disconnect" in name:
        return True
    return False


def _is_end_of_stream(exc: BaseException) -> bool:
    name = type(exc).__name__
    return name in ("EndOfStream", "WouldBlock", "BrokenResourceError")


async def defensive_call_next(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Wrap call_next with disconnect / cancel / no-response guards."""
    path = request.url.path
    try:
        response = await call_next(request)
        if response is None:
            return ensure_response(None, path=path)
        return response
    except asyncio.CancelledError:
        if await request.is_disconnected():
            metrics.inc("skytrax_client_disconnects", path=path)
            logger.info("[CLIENT_DISCONNECT] cancelled path=%s", path)
            return Response(status_code=CLIENT_DISCONNECT_STATUS)
        metrics.inc("skytrax_timeout_recoveries", path=path)
        logger.info("[SAFE_RESPONSE] cancelled path=%s", path)
        return Response(status_code=CANCELLED_STATUS)
    except Exception as exc:
        if _is_end_of_stream(exc):
            metrics.inc("skytrax_client_disconnects", path=path)
            logger.info("[CLIENT_DISCONNECT] end_of_stream path=%s", path)
            return Response(status_code=CLIENT_DISCONNECT_STATUS)
        if _is_client_disconnect(exc):
            metrics.inc("skytrax_client_disconnects", path=path)
            logger.info("[CLIENT_DISCONNECT] %s path=%s", type(exc).__name__, path)
            return Response(status_code=CLIENT_DISCONNECT_STATUS)
        if isinstance(exc, RuntimeError) and "No response returned" in str(exc):
            metrics.inc("skytrax_no_response_guard_hits", path=path)
            logger.warning("[NO_RESPONSE_GUARD] runtime path=%s", path)
            return fallback_operational_response(path=path, reason="no_response_returned")
        raise
