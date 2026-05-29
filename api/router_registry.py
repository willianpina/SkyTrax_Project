"""FastAPI route registry — health route validation and startup diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Canonical operations health endpoints (under /api prefix).
EXPECTED_HEALTH_ROUTES: tuple[str, ...] = (
    "/api/operations/health/schema",
    "/api/operations/health/native",
    "/api/operations/health/integrity",
    "/api/operations/health/pipeline",
)

# Legacy paths — logged as warnings if still the only mount (should not be primary).
DEPRECATED_HEALTH_ROUTES: tuple[str, ...] = (
    "/ops/health/schema",
    "/ops/health/native",
    "/ops/health/integrity",
    "/ops/health/pipeline",
)


def collect_route_paths(app: FastAPI) -> set[str]:
    """All registered route paths on the application."""
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


def validate_health_routes(app: FastAPI) -> dict[str, Any]:
    """Compare registered routes against expected operations health endpoints."""
    paths = collect_route_paths(app)
    missing = [p for p in EXPECTED_HEALTH_ROUTES if p not in paths]
    present = [p for p in EXPECTED_HEALTH_ROUTES if p in paths]
    deprecated_present = [p for p in DEPRECATED_HEALTH_ROUTES if p in paths]
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present,
        "deprecated_present": deprecated_present,
        "total_routes": len(paths),
    }


def log_registered_health_routes(app: FastAPI) -> None:
    """Emit [ROUTER] startup diagnostics for health endpoints."""
    report = validate_health_routes(app)
    logger.info("[BOOTSTRAP] API route registration complete total_routes=%d", report["total_routes"])

    if report["present"]:
        logger.info("[ROUTER] Mounted operations health routes:")
        for path in report["present"]:
            logger.info("[ROUTER]   * %s", path)

    if report["missing"]:
        logger.error("[ROUTER] Missing expected health routes: %s", report["missing"])

    if report["deprecated_present"]:
        logger.warning(
            "[ROUTER] Deprecated /ops health aliases still mounted: %s",
            report["deprecated_present"],
        )

    health_related = sorted(
        p
        for p in collect_route_paths(app)
        if "/health" in p and ("operations" in p or p.startswith("/ops/health"))
    )
    if health_related:
        logger.info("[API] All health-related paths: %s", health_related)
