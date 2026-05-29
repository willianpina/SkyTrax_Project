"""Tests for enterprise startup governance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.runtime_state import (
    activate_forecast_safe_mode,
    is_forecast_safe_mode,
    is_stage_blocked,
    set_schema_drift,
)
from app.startup_governance import (
    StartupBlockedError,
    resolve_auto_migrate,
    run_native_startup_probe,
)


def test_resolve_auto_migrate_development():
    s = Settings(environment="development", schema_auto_migrate_dev=True)
    assert resolve_auto_migrate(s) is True


def test_resolve_auto_migrate_production_never():
    s = Settings(
        environment="production",
        schema_auto_migrate_dev=True,
        schema_auto_migrate_staging=True,
    )
    assert resolve_auto_migrate(s) is False


def test_resolve_auto_migrate_staging_flag():
    s = Settings(environment="staging", schema_auto_migrate_staging=True)
    assert resolve_auto_migrate(s) is True
    s2 = Settings(environment="staging", schema_auto_migrate_staging=False)
    assert resolve_auto_migrate(s2) is False


def test_schema_drift_blocks_stages():
    set_schema_drift(True, ["review_intelligence", "graph_nodes"])
    assert is_stage_blocked("metadata")
    assert is_stage_blocked("knowledge_graph")
    assert not is_stage_blocked("crawl")


def test_activate_forecast_safe_mode():
    import os

    os.environ.pop("FORECAST_SAFE_MODE", None)
    activate_forecast_safe_mode("test")
    assert is_forecast_safe_mode()


def test_startup_blocked_on_production_drift():
    engine = MagicMock()
    unhealthy_schema = {
        "healthy": False,
        "missing_tables": ["graph_nodes"],
        "migration_drift": True,
        "present_tables": [],
        "tables_by_group": {},
        "pending_migrations": ["0010"],
        "current_revision": "0001",
        "head_revision": "0010",
        "missing_indexes": [],
        "broken_constraints": [],
        "bootstrap_attempted": False,
        "bootstrap_result": None,
    }
    settings = Settings(
        environment="production",
        schema_block_on_drift=True,
        schema_validate_on_startup=True,
        startup_native_probe=False,
    )

    with patch("app.startup_governance.get_settings", return_value=settings):
        with patch("database.schema_health.validate_schema", return_value=unhealthy_schema):
            with patch("app.startup_governance.set_schema_drift"):
                with patch("app.startup_governance.set_startup_report"):
                    with pytest.raises(StartupBlockedError):
                        from app.startup_governance import run_startup_governance

                        run_startup_governance(engine, service="api", block_on_failure=True)


def test_bootstrap_schema_flow():
    from database.schema_health import bootstrap_schema

    engine = MagicMock()
    initial = {
        "healthy": False,
        "missing_tables": ["graph_nodes"],
        "migration_drift": True,
        "present_tables": ["airlines"],
        "tables_by_group": {},
        "pending_migrations": [],
        "current_revision": None,
        "head_revision": "0010",
        "missing_indexes": [],
        "broken_constraints": [],
    }
    after = {**initial, "healthy": True, "missing_tables": [], "migration_drift": False}

    with patch("database.schema_health.validate_schema", side_effect=[initial, after]):
        with patch(
            "database.schema_health.run_migrations_upgrade", return_value={"success": True, "duration_ms": 42}
        ):
            report, ms = bootstrap_schema(engine)
    assert report["healthy"] is True
    assert ms >= 0


def test_startup_refreshes_runtime_after_schema_validation():
    from app.startup_governance import run_startup_governance

    engine = MagicMock()
    healthy_schema = {
        "healthy": True,
        "missing_tables": [],
        "migration_drift": False,
        "present_tables": ["airlines"],
        "tables_by_group": {},
        "pending_migrations": [],
        "current_revision": "0012",
        "head_revision": "0012",
        "missing_indexes": [],
        "broken_constraints": [],
        "semantic_drift": False,
        "semantic_audit": {},
        "semantic_blocked_stages": [],
        "canonical_aviation_valid": True,
        "aviation_semantic_drift": False,
        "bootstrap_attempted": False,
        "bootstrap_result": None,
    }
    settings = Settings(
        environment="development",
        schema_validate_on_startup=True,
        schema_auto_migrate_dev=False,
        startup_native_probe=False,
    )

    with patch("app.startup_governance.get_settings", return_value=settings):
        with patch("database.schema_health.validate_schema", return_value=healthy_schema):
            with patch("app.startup_governance.set_schema_drift"):
                with patch("app.startup_governance.set_startup_report"):
                    with patch(
                        "database.runtime_schema.refresh_sqlalchemy_runtime_after_migrations"
                    ) as mock_refresh:
                        run_startup_governance(engine, service="api")

    mock_refresh.assert_called_once()


def test_native_startup_probe_architecture():
    native = run_native_startup_probe(full_smoke=False)
    assert "architecture" in native
    assert "dependencies" in native


def test_apple_silicon_triggers_safe_mode_recommendation():
    import os

    os.environ.pop("FORECAST_SAFE_MODE", None)
    settings = Settings(forecast_auto_safe_mode=True, forecast_safe_mode=False)
    native = {
        "apple_silicon": "true",
        "any_segfault_detected": False,
        "any_import_failure": True,
        "forecast_safe_mode_recommended": False,
    }
    from app.startup_governance import _apply_native_governance

    with patch("app.startup_governance.activate_forecast_safe_mode") as mock_activate:
        actions = _apply_native_governance(native, settings)
    assert "forecast_safe_mode_auto_enabled" in actions
    mock_activate.assert_called_once()
