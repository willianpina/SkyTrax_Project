"""Health endpoints use startup/redis snapshots — no validate_schema per request."""

from __future__ import annotations

import os
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_session_stub = types.ModuleType("database.session")
_session_stub.engine = MagicMock()
sys.modules.setdefault("database.session", _session_stub)


def test_schema_health_uses_snapshot_not_validate_schema():
    from app.health_snapshot import get_schema_health_fast, seed_from_startup_report
    from app.startup_governance import StartupReport

    report = StartupReport(service="test", environment="test")
    report.schema = {"healthy": True, "missing_tables": [], "migration_drift": False}
    seed_from_startup_report(report)

    out = get_schema_health_fast()
    assert out["healthy"] is True
    assert out["summary_source"] == "startup_cache"


def test_native_health_fast_no_subprocess():
    from app.health_snapshot import get_native_health_fast, seed_from_startup_report
    from app.startup_governance import StartupReport

    report = StartupReport(service="test", environment="test")
    report.native = {"any_segfault_detected": False, "numpy_version": "1.0"}
    seed_from_startup_report(report)

    with (
        patch("app.native_health.collect_native_health") as collect,
        patch("app.runtime_state.is_forecast_safe_mode", return_value=False),
    ):
        collect.side_effect = AssertionError("must not probe per request")
        out = get_native_health_fast()
    assert out["status"] == "ok"
    assert out["summary_source"] == "startup_cache"


def test_integrity_fast_redis_only():
    from app.health_snapshot import get_integrity_health_fast

    cached = {
        "healthy": True,
        "integrity_consistent": True,
        "table_counts": {"reviews": 10},
        "cached_at": "2026-01-01T00:00:00Z",
    }
    with (
        patch(
            "analytics.pipeline_integrity.load_authoritative_integrity_snapshot",
            return_value=cached,
        ),
        patch(
            "analytics.pipeline_integrity.load_live_kpis_from_redis",
            return_value={"reviews": 10},
        ),
        patch(
            "analytics.pipeline_integrity.build_authoritative_integrity",
        ) as build,
    ):
        build.side_effect = AssertionError("no full db audit on fast path")
        out = get_integrity_health_fast()
    assert out["summary_source"] == "redis_snapshot"
    assert out["table_counts"]["reviews"] == 10


def test_schema_health_latency_budget():
    from app.health_snapshot import get_schema_health_fast, seed_from_startup_report
    from app.startup_governance import StartupReport

    seed_from_startup_report(
        StartupReport(service="t", environment="t", schema={"healthy": True}),
    )
    t0 = time.perf_counter()
    for _ in range(50):
        get_schema_health_fast()
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 50
    assert elapsed_ms < 200, f"avg {elapsed_ms:.1f}ms exceeds 200ms budget"
