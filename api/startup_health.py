"""Startup-safe validation for operations health — no router imports."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def boot_pipeline_health_contract() -> bool:
    """Validate PipelineHealthResponse once at startup; never raises."""
    logger.info("[PIPELINE_HEALTH_BOOT] validating enterprise health contract")
    try:
        from api.schemas import PipelineHealthResponse
        from app.payload_serialization import safe_json_payload

        sample = safe_json_payload(
            {
                "status": "ready",
                "readiness": "ready",
                "environment": "development",
                "degraded": False,
                "pipeline": {"running": False, "stage": "idle"},
                "schema": {"healthy": True, "summary_source": "boot"},
                "native": {},
                "runtime": {},
                "runtime_health": {},
                "canonical_kpis": {},
                "accumulated_kpis": {},
                "delta_kpis": {},
                "kpi_governance": {},
                "metric_lineage": {},
                "metric_semantics": {},
                "payload_safe": True,
                "governance_source": "boot",
            },
            context="pipeline_health_boot",
        )
        model = PipelineHealthResponse.model_validate(sample)
        dumped = model.model_dump(mode="json", by_alias=True)
        assert "schema" in dumped
        assert dumped["schema"]["healthy"] is True
        logger.info("[PYDANTIC_SCHEMA] PipelineHealthResponse contract OK")
        return True
    except Exception as exc:
        logger.warning("[PYDANTIC_SCHEMA] contract validation skipped: %s", exc)
        return False


def boot_router_governance(app) -> None:
    """Log health route ownership after routers are mounted."""
    try:
        from api.router_registry import validate_health_routes

        report = validate_health_routes(app)
        logger.info(
            "[ROUTER_GOVERNANCE] health routes valid=%s present=%s",
            report.get("valid"),
            report.get("present"),
        )
        if not report.get("valid"):
            logger.error("[ROUTER_GOVERNANCE] missing routes: %s", report.get("missing"))
    except Exception as exc:
        logger.warning("[ROUTER_GOVERNANCE] audit skipped: %s", exc)


def audit_import_graph() -> None:
    """Lightweight import-order check — logs only, never fails startup."""
    logger.info("[CIRCULAR_IMPORT] auditing health module graph")
    modules = (
        "app.payload_serialization",
        "api.schemas",
        "api.pipeline_health_service",
        "api.routers.ops_health",
    )
    for name in modules:
        try:
            __import__(name)
            logger.debug("[CIRCULAR_IMPORT] ok %s", name)
        except Exception as exc:
            logger.error("[CIRCULAR_IMPORT] failed %s: %s", name, exc)
