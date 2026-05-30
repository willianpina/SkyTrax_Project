from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.observability import metrics
from app.request_context import request_id_var, trace_id_var
from app.response_contract import (
    CANCELLED_STATUS,
    CLIENT_DISCONNECT_STATUS,
    defensive_call_next,
    safe_json_response,
)

logger = logging.getLogger(__name__)

# Hot polling paths — exempt from global HTTP timeout (handlers must stay fast).
_HOT_POLL_PREFIXES = (
    "/api/operations/status",
    "/api/operations/live",
    "/api/operations/health/",
    "/health",
    "/metrics",
)

# Async pipeline dispatch — never subject to HTTP timeout.
_ASYNC_DISPATCH_PREFIX = "/api/operations/refresh"

# Aviation dashboards — hub-intelligence can exceed default 30s on cold mention-index builds.
_AVIATION_EXTENDED_PREFIXES = (
    "/api/aviation/hub-intelligence",
    "/api/aviation/catalog",
)
_AVIATION_EXTENDED_TIMEOUT_S = float(
    __import__("os").getenv("API_AVIATION_TIMEOUT_SECONDS", "120")
)


def _path_matches(path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = path.rstrip("/")
    for prefix in prefixes:
        p = prefix.rstrip("/")
        if normalized == p or normalized.startswith(f"{p}/"):
            return True
    return False


def _is_hot_poll_path(path: str) -> bool:
    return _path_matches(path, _HOT_POLL_PREFIXES)


def _is_async_dispatch(request: Request) -> bool:
    if request.method != "POST":
        return False
    path = request.url.path.rstrip("/")
    base = _ASYNC_DISPATCH_PREFIX.rstrip("/")
    return path == base or path.startswith(f"{base}/")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request and trace IDs, record latency and propagate IDs to responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        trace_id = request.headers.get("traceparent") or request.headers.get("x-trace-id") or request_id
        request_token = request_id_var.set(request_id)
        trace_token = trace_id_var.set(trace_id)
        started_at = time.perf_counter()
        status_code = 500
        response: Response | None = None
        try:
            response = await defensive_call_next(request, call_next)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - started_at
            metrics.inc(
                "skytrax_api_requests",
                method=request.method,
                path=request.url.path,
                status=status_code,
            )
            metrics.observe(
                "skytrax_api_request_duration_seconds",
                duration,
                method=request.method,
                path=request.url.path,
                status=status_code,
            )
            request_id_var.reset(request_token)
            trace_id_var.reset(trace_token)
            if response is not None:
                try:
                    response.headers["x-request-id"] = request_id
                    response.headers["x-trace-id"] = trace_id
                except Exception:
                    pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set baseline API security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await defensive_call_next(request, call_next)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("permissions-policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("x-permitted-cross-domain-policies", "none")
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests larger than the configured content length."""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request payload too large."})
        return await defensive_call_next(request, call_next)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-client fixed window limiter for API protection."""

    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = self._requests[client]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.requests_per_minute:
            metrics.inc("skytrax_api_rate_limited", client=client)
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
        bucket.append(now)
        return await defensive_call_next(request, call_next)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Coarse request timeout — skipped for hot polling and async dispatch paths."""

    def __init__(self, app, timeout_seconds: float) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
        self._hot_poll_timeout = min(timeout_seconds, 8.0)

    def _effective_timeout(self, request: Request) -> float | None:
        path = request.url.path
        if _is_async_dispatch(request) or _is_hot_poll_path(path):
            return None
        if _path_matches(path, _AVIATION_EXTENDED_PREFIXES):
            return _AVIATION_EXTENDED_TIMEOUT_S
        if _path_matches(path, _HOT_POLL_PREFIXES):
            return self._hot_poll_timeout
        return self.timeout_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        timeout = self._effective_timeout(request)
        path = request.url.path
        try:
            if timeout is None:
                return await defensive_call_next(request, call_next)
            return await asyncio.wait_for(
                defensive_call_next(request, call_next),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            metrics.inc("skytrax_api_timeouts", path=path)
            logger.warning("[ENDPOINT_TIMEOUT] path=%s timeout=%.1fs", path, timeout or 0)
            return safe_json_response(
                {"detail": "Request timed out.", "path": path},
                status_code=504,
                path=path,
            )
        except asyncio.CancelledError:
            if await request.is_disconnected():
                metrics.inc("skytrax_client_disconnects", path=path)
                logger.info("[CLIENT_DISCONNECT] timeout middleware path=%s", path)
                return Response(status_code=CLIENT_DISCONNECT_STATUS)
            return Response(status_code=CANCELLED_STATUS)
