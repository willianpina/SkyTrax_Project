"""Enterprise startup governance — schema bootstrap, native probes, self-healing flags."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.runtime_state import (
    activate_forecast_safe_mode,
    merge_state,
    set_schema_drift,
    set_startup_report,
)

logger = logging.getLogger(__name__)


class StartupBlockedError(RuntimeError):
    """Raised when SCHEMA_BLOCK_ON_DRIFT prevents service start."""


@dataclass
class StartupReport:
    service: str
    environment: str
    ready: bool = True
    degraded: bool = False
    schema: dict[str, Any] = field(default_factory=dict)
    native: dict[str, Any] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    migration_duration_ms: int = 0
    bootstrap_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "environment": self.environment,
            "ready": self.ready,
            "degraded": self.degraded,
            "readiness": "ready"
            if self.ready and not self.degraded
            else ("degraded" if self.ready else "blocked"),
            "schema": self.schema,
            "native": self.native,
            "actions": self.actions,
            "errors": self.errors,
            "migration_duration_ms": self.migration_duration_ms,
            "forecast_safe_mode_active": os.getenv("FORECAST_SAFE_MODE", "0") in ("1", "true"),
            "schema_drift": self.schema.get("migration_drift", False),
            "missing_tables": self.schema.get("missing_tables", []),
        }


_last_report: StartupReport | None = None


def get_last_startup_report() -> StartupReport | None:
    return _last_report


def resolve_auto_migrate(settings: Settings) -> bool:
    """Environment-based auto-migration policy."""
    env = (settings.environment or "development").lower()
    if env == "production":
        return False
    if env == "development":
        return settings.schema_auto_migrate_dev
    if env == "staging":
        return settings.schema_auto_migrate_staging
    return False


def run_native_startup_probe(*, full_smoke: bool = False) -> dict[str, Any]:
    """Lightweight native probe at startup (import-only unless full_smoke)."""
    from app.native_health import _architecture_info, _safe_import_probe

    arch = _architecture_info()
    probes = {
        "numpy": _safe_import_probe("numpy"),
        "scipy": _safe_import_probe("scipy"),
        "pandas": _safe_import_probe("pandas"),
        "sklearn": _safe_import_probe("sklearn"),
    }

    any_segfault = any(p.get("segfault") for p in probes.values())
    any_unavailable = any(not p.get("available") for p in probes.values())

    result: dict[str, Any] = {
        **arch,
        "dependencies": probes,
        "any_segfault_detected": any_segfault,
        "any_import_failure": any_unavailable,
        "blas_backend": "unknown",
    }

    if full_smoke:
        from app.native_health import collect_native_health

        result = collect_native_health()

    if any_segfault:
        logger.error("[SEGFAULT] Native import probe segfault at startup")
    if arch.get("apple_silicon") == "true" and any_unavailable:
        logger.warning("[FORECAST_NATIVE] Apple Silicon with native import failures")

    return result


def _apply_native_governance(native: dict[str, Any], settings: Settings) -> list[str]:
    actions: list[str] = []
    force_safe = (
        settings.forecast_auto_safe_mode
        or native.get("any_segfault_detected")
        or native.get("forecast_safe_mode_recommended")
        or (native.get("apple_silicon") == "true" and native.get("any_import_failure"))
    )
    if force_safe and not os.getenv("FORECAST_SAFE_MODE"):
        activate_forecast_safe_mode("startup_native_probe")
        actions.append("forecast_safe_mode_auto_enabled")
        logger.warning("[FORECAST_NATIVE] Auto-enabled FORECAST_SAFE_MODE at startup")
    elif settings.forecast_safe_mode:
        merge_state(forecast_safe_mode_active=True, forecast_safe_mode_reason="env")
        actions.append("forecast_safe_mode_from_env")
    return actions


def run_startup_governance(
    engine,
    *,
    service: str = "api",
    block_on_failure: bool | None = None,
) -> StartupReport:
    """Full startup sequence: schema → optional migrate → revalidate → native → flags."""
    global _last_report
    settings = get_settings()
    env = settings.environment
    report = StartupReport(service=service, environment=env)
    t0 = time.perf_counter()

    auto_migrate = resolve_auto_migrate(settings)
    if auto_migrate:
        report.actions.append("auto_migrate_enabled")
    else:
        report.actions.append("auto_migrate_disabled")

    # ── Phase 0: Alembic version_num capacity ───────────────────────
    if settings.schema_validate_on_startup and settings.alembic_version_auto_repair:
        try:
            from database.alembic_version_repair import ensure_alembic_version_capacity

            alembic_preflight = ensure_alembic_version_capacity(engine)
            if alembic_preflight.get("actions"):
                report.actions.append("alembic_version_repaired")
                logger.warning("[ALEMBIC] Startup repair actions=%s", alembic_preflight["actions"])
            if not alembic_preflight.get("alembic_safe"):
                report.degraded = True
                report.actions.append("alembic_truncation_risk")
                if settings.alembic_block_on_truncation_risk and env == "production":
                    report.ready = False
                    report.errors.append("alembic_version_num_too_short")
        except Exception as exc:
            logger.warning("[ALEMBIC] Startup version repair skipped: %s", exc)

    # ── Phase 1: Schema validation ─────────────────────────────────
    from database.schema_health import bootstrap_schema, validate_schema

    if settings.schema_validate_on_startup:
        try:
            if auto_migrate:
                schema_report, mig_ms = bootstrap_schema(engine)
                report.migration_duration_ms = mig_ms
                report.actions.append("schema_bootstrap_executed")
            else:
                schema_report = validate_schema(engine, auto_migrate_dev=False)
                if schema_report.get("migration_drift"):
                    logger.warning(
                        "[MIGRATION] Drift in %s — auto-migrate disabled for env=%s",
                        service,
                        env,
                    )
                    report.actions.append("migration_drift_alert_only")

            report.schema = schema_report

            if not schema_report.get("healthy"):
                report.degraded = True
                set_schema_drift(
                    True,
                    schema_report.get("missing_tables", []),
                    schema_report.get("semantic_blocked_stages", []),
                )
                if schema_report.get("semantic_drift"):
                    report.actions.append("semantic_column_drift_detected")
                    logger.warning(
                        "[SCHEMA] Semantic drift tables=%s",
                        schema_report.get("semantic_audit", {}).get("drifted_tables"),
                    )
                if env == "production":
                    report.actions.append("schema_drift_production_alert")
                else:
                    report.actions.append("schema_incomplete_degraded")
            else:
                set_schema_drift(False, [], [])

            try:
                from database.runtime_schema import refresh_sqlalchemy_runtime_after_migrations

                refresh_sqlalchemy_runtime_after_migrations(
                    engine,
                    reason="startup_governance_schema_ready",
                )
                report.actions.append("runtime_schema_refreshed")
            except Exception as exc:
                logger.warning("[RUNTIME_SCHEMA] Startup runtime refresh skipped: %s", exc)

            br = schema_report.get("bootstrap_result") or {}
            if schema_report.get("bootstrap_attempted") and not br.get("success"):
                report.bootstrap_failures += 1
                report.errors.append(br.get("error", "bootstrap_failed"))
                try:
                    from app.observability import record_worker_metric

                    record_worker_metric("skytrax_bootstrap_failures", 1.0)
                except Exception:
                    pass

        except Exception as exc:
            report.degraded = True
            report.errors.append(f"schema: {exc}")
            logger.exception("[SCHEMA] Startup validation failed service=%s", service)

    # ── Phase 2: Native probe ────────────────────────────────────────
    if settings.startup_native_probe:
        try:
            native = run_native_startup_probe(full_smoke=False)
            report.native = native
            report.actions.extend(_apply_native_governance(native, settings))
        except Exception as exc:
            report.degraded = True
            report.errors.append(f"native: {exc}")
            activate_forecast_safe_mode("native_probe_exception")
            logger.warning("[FORECAST_NATIVE] Probe failed — safe mode on: %s", exc)

    # ── Phase 3: Production block ────────────────────────────────────
    should_block = block_on_failure
    if should_block is None:
        should_block = settings.schema_block_on_drift and env == "production"
    if (
        settings.aviation_schema_block_on_drift
        and env == "production"
        and report.schema.get("aviation_semantic_drift")
    ):
        should_block = True
        report.actions.append("startup_blocked_aviation_drift")

    if should_block and not report.schema.get("healthy", True):
        report.ready = False
        report.actions.append("startup_blocked_schema_drift")
        logger.critical(
            "[SCHEMA] Startup BLOCKED service=%s env=%s missing=%s drift=%s",
            service,
            env,
            report.schema.get("missing_tables"),
            report.schema.get("migration_drift"),
        )
        _last_report = report
        set_startup_report(report.to_dict())
        raise StartupBlockedError(
            f"Schema not healthy in production: missing={report.schema.get('missing_tables')}"
        )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    report.actions.append(f"startup_completed_{elapsed_ms}ms")

    if report.migration_duration_ms:
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_migration_duration", float(report.migration_duration_ms))
        except Exception:
            pass

    _last_report = report
    set_startup_report(report.to_dict())

    logger.warning(
        "[BOOTSTRAP] service=%s env=%s ready=%s degraded=%s actions=%s",
        service,
        env,
        report.ready,
        report.degraded,
        report.actions,
    )
    return report


def log_startup_summary(report: StartupReport) -> None:
    """Human-readable startup summary for Docker logs."""
    lines = [
        "========== SkyTrax Startup Summary ==========",
        f"  service:     {report.service}",
        f"  environment: {report.environment}",
        f"  readiness: {report.to_dict()['readiness']}",
        f"  degraded:  {report.degraded}",
        f"  safe mode: {report.to_dict().get('forecast_safe_mode_active')}",
        f"  drift:     {report.schema.get('migration_drift')}",
        f"  missing:   {len(report.schema.get('missing_tables', []))} tables",
        f"  actions:   {', '.join(report.actions)}",
    ]
    if report.errors:
        lines.append(f"  errors:    {report.errors}")
    lines.append("=============================================")
    for line in lines:
        logger.warning(line)
