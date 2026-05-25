from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.observability import metrics
from app.request_context import request_id_var, trace_id_var


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request and trace IDs, record latency and propagate IDs to responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        trace_id = request.headers.get("traceparent") or request.headers.get("x-trace-id") or request_id
        request_token = request_id_var.set(request_id)
        trace_token = trace_id_var.set(trace_id)
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
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
            if "response" in locals():
                response.headers["x-request-id"] = request_id
                response.headers["x-trace-id"] = trace_id


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set baseline API security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
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
        return await call_next(request)


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
        return await call_next(request)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Apply a coarse request timeout at the ASGI middleware layer."""

    def __init__(self, app, timeout_seconds: float) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            metrics.inc("skytrax_api_timeouts", path=request.url.path)
            raise HTTPException(status_code=504, detail="Request timed out.")
