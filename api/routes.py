"""Backwards-compatible aggregator that re-exports all domain routers as a
single ``router`` object.  api/main.py imports ``router`` from here, so the
variable name and ``/api`` prefix must stay unchanged."""

from __future__ import annotations

from fastapi import APIRouter

from api.routers.admin import router as admin_router
from api.routers.analytics_router import router as analytics_router
from api.routers.aviation import router as aviation_router
from api.routers.intelligence import router as intelligence_router
from api.routers.operations import router as operations_router
from api.routers.ops_health import router as ops_health_router
from api.routers.reviews import router as reviews_router
from api.routers.search import router as search_router

router = APIRouter(prefix="/api", tags=["airline-intelligence"])

router.include_router(reviews_router)
router.include_router(analytics_router)
router.include_router(intelligence_router)
router.include_router(search_router)
router.include_router(admin_router)
router.include_router(aviation_router)
router.include_router(operations_router)
router.include_router(ops_health_router, prefix="/operations")
