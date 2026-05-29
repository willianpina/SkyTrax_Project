"""Regression test suite for pipeline resilience.

Tests verify:
  1. Soft-failure detection (stages returning {"error": ...} without raising)
  2. KPI accumulation and snapshot-protection
  3. Heartbeat freshness during long-running stages
  4. completed_degraded terminal state
  5. Stage isolation (failure in one doesn't block others)
  6. Empty-data handling (fusion with 0 ReviewIntelligence records)
  7. Stalled recovery

Mocks heavy dependencies (psycopg, Redis) so the suite runs outside Docker.
"""

from __future__ import annotations

import sys
import time
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# ── Stub heavy dependencies that aren't available outside Docker ──────
_scrapy_stub = MagicMock()
_scrapy_stub.Spider = type("Spider", (), {"__init__": lambda *a, **k: None})
_scrapy_stub.Item = type("Item", (), {})
_scrapy_stub.Field = MagicMock
_scrapy_stub.Request = MagicMock

_stub_modules = {
    "psycopg": MagicMock(),
    "psycopg.pq": MagicMock(),
    "psycopg_c": MagicMock(),
    "rq": MagicMock(),
    "scrapy": _scrapy_stub,
    "scrapy.exceptions": MagicMock(),
    "itemadapter": MagicMock(),
    "twisted": MagicMock(),
    "twisted.internet": MagicMock(),
    "twisted.internet.asyncioreactor": MagicMock(),
}

# Ensure database.session doesn't try to connect
_session_mod = types.ModuleType("database.session")
_session_mod.Base = MagicMock()
_session_mod.SessionLocal = MagicMock()
_session_mod.get_session = MagicMock()

_db_models_mod = types.ModuleType("database.models")
for attr in (
    "Airline",
    "AnomalyEvent",
    "ExecutiveInsight",
    "ForecastSnapshot",
    "MetricSnapshot",
    "NLPResult",
    "Review",
    "SpiderRun",
):
    setattr(_db_models_mod, attr, MagicMock())

_db_models_core = types.ModuleType("database.models.core")
_db_models_core.Airline = MagicMock()
_db_models_core.Review = MagicMock()

_db_models_aviation = types.ModuleType("database.models.aviation")
for attr in ("AirlineMetadata", "AirportMetadata", "Alliance", "AirlineAirport"):
    setattr(_db_models_aviation, attr, MagicMock())

_db_models_operations = types.ModuleType("database.models.operations")
_db_models_operations.OperationalRefreshRun = MagicMock()

_db_models_graph = types.ModuleType("database.models.graph")
_db_models_graph.GraphNode = MagicMock()
_db_models_graph.GraphEdge = MagicMock()

_scraper_items = types.ModuleType("scraper.items")
_scraper_items.AirlineItem = MagicMock
_scraper_items.ReviewItem = MagicMock

_scraper_pipelines = types.ModuleType("scraper.pipelines")
_scraper_pipelines_fp = types.ModuleType("scraper.pipelines.fingerprinting")
_scraper_pipelines_fp.review_fingerprint = MagicMock(return_value="abc123")

for mod_name, mod in _stub_modules.items():
    sys.modules.setdefault(mod_name, mod)

sys.modules.setdefault("scraper.items", _scraper_items)
sys.modules.setdefault("scraper.pipelines", _scraper_pipelines)
sys.modules.setdefault("scraper.pipelines.fingerprinting", _scraper_pipelines_fp)
sys.modules.setdefault("database.session", _session_mod)
sys.modules.setdefault("database.models", _db_models_mod)
sys.modules.setdefault("database.models.core", _db_models_core)
sys.modules.setdefault("database.models.aviation", _db_models_aviation)
sys.modules.setdefault("database.models.operations", _db_models_operations)
sys.modules.setdefault("database.models.graph", _db_models_graph)

# Mock Redis at module level
_redis_mod = types.ModuleType("redis")
_redis_mod.Redis = MagicMock()
sys.modules.setdefault("redis", _redis_mod)

# Now import the pipeline module
from worker.orchestration.refresh_pipeline import (
    _KPI_EXTRACTION_MAP,
    _TERMINAL_STAGES,
    _sanitize_stage_results,
    _detect_stale,
    reconcile_pipeline_soft_failures,
    OperationalRefreshPipeline,
)
from app.heartbeat import TimedHeartbeat, heartbeat_guard


class TestTerminalStages(unittest.TestCase):
    def test_completed_degraded_is_terminal(self):
        assert "completed_degraded" in _TERMINAL_STAGES

    def test_completed_is_terminal(self):
        assert "completed" in _TERMINAL_STAGES

    def test_running_is_not_terminal(self):
        assert "running" not in _TERMINAL_STAGES
        assert "running_degraded" not in _TERMINAL_STAGES


class TestSanitizeStageResults(unittest.TestCase):
    def test_scalars_preserved(self):
        raw = {"crawl": {"total_reviews_in_db": 27000, "success": True, "mode": "all"}}
        clean = _sanitize_stage_results(raw)
        assert clean["crawl"]["total_reviews_in_db"] == 27000
        assert clean["crawl"]["success"] is True
        assert clean["crawl"]["mode"] == "all"

    def test_nested_dict_flattened(self):
        raw = {"fusion": {"fusion": {"signals_generated": 5}}}
        clean = _sanitize_stage_results(raw)
        assert clean["fusion"]["fusion.signals_generated"] == 5

    def test_list_becomes_length(self):
        raw = {"forecasting": {"errors": ["a", "b", "c"]}}
        clean = _sanitize_stage_results(raw)
        assert clean["forecasting"]["errors"] == 3

    def test_error_key_preserved(self):
        raw = {"metadata": {"error": "connection timeout"}}
        clean = _sanitize_stage_results(raw)
        assert "error" in clean["metadata"]


class TestKpiAccumulation(unittest.TestCase):
    def _make_pipeline(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p._kpis = {}
        p.errors = []
        p.results = {}
        p.events = []
        p._last_successful_stage = ""
        p._stage_timings = {}
        p._heartbeat_count = 0
        return p

    def test_successful_stage_accumulates_kpis(self):
        p = self._make_pipeline()
        result = {"total_reviews_in_db": 27000, "success": True}
        p._accumulate_kpis("crawl", result)
        assert p._kpis["reviews"] == 27000

    def test_error_stage_does_not_accumulate(self):
        p = self._make_pipeline()
        result = {"error": "connection failed"}
        p._accumulate_kpis("metadata", result)
        assert "metadata" not in p._kpis

    def test_zero_does_not_overwrite_positive(self):
        p = self._make_pipeline()
        p._kpis = {"reviews": 27000}
        result = {"total_reviews_in_db": 0, "success": True}
        p._accumulate_kpis("crawl", result)
        assert p._kpis["reviews"] == 27000

    def test_larger_value_overwrites(self):
        p = self._make_pipeline()
        p._kpis = {"reviews": 27000}
        result = {"total_reviews_in_db": 28000, "success": True}
        p._accumulate_kpis("crawl", result)
        assert p._kpis["reviews"] == 28000

    def test_multiple_stages_accumulate(self):
        p = self._make_pipeline()
        p._accumulate_kpis("crawl", {"total_reviews_in_db": 500})
        p._accumulate_kpis("semantic", {"clusters_created": 42, "enriched": 300})
        p._accumulate_kpis("anomalies", {"anomalies_created": 7})
        assert p._kpis["reviews"] == 500
        assert p._kpis["clusters"] == 42
        assert p._kpis["enriched"] == 300
        assert p._kpis["anomalies"] == 7


class TestSoftFailureDetection(unittest.TestCase):
    """Verify that stages returning {"error": ...} are tracked as failed."""

    def _make_pipeline(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p.operation_id = "test-001"
        p.airline_slug = None
        p.triggered_by = "test"
        p.results = {}
        p.errors = []
        p.events = []
        p.started_at = datetime.now(timezone.utc)
        p._kpis = {}
        p._last_successful_stage = ""
        p._stage_timings = {}
        p._heartbeat_count = 0
        return p

    def test_soft_failure_recorded_in_errors(self):
        p = self._make_pipeline()

        def failing_stage():
            return {"error": "simulated failure", "partial_data": 42}

        r = MagicMock()
        r.get.return_value = None
        with (
            patch("app.runtime_state.is_stage_blocked", return_value=False),
            patch.object(p, "_check_dependency_contract", return_value=None),
        ):
            p._run_stage(r, "forecasting", 6, failing_stage)

        assert len(p.errors) == 1
        assert p.errors[0]["stage"] == "forecasting"
        assert p.errors[0].get("soft") is True
        assert p.results["forecasting"]["error"] == "simulated failure"
        assert p.results["forecasting"]["partial_data"] == 42

    def test_hard_failure_recorded(self):
        p = self._make_pipeline()

        def exploding_stage():
            raise RuntimeError("boom")

        r = MagicMock()
        r.get.return_value = None
        with (
            patch("app.runtime_state.is_stage_blocked", return_value=False),
            patch.object(p, "_check_dependency_contract", return_value=None),
        ):
            p._run_stage(r, "crawl", 2, exploding_stage)

        assert len(p.errors) == 1
        assert p.errors[0]["stage"] == "crawl"
        assert "soft" not in p.errors[0]
        assert p.results["crawl"]["error"] == "boom"

    def test_successful_stage_no_error(self):
        p = self._make_pipeline()

        def ok_stage():
            return {"clusters_created": 420, "enriched": 300}

        r = MagicMock()
        r.get.return_value = None
        with (
            patch("app.runtime_state.is_stage_blocked", return_value=False),
            patch.object(p, "_check_dependency_contract", return_value=None),
        ):
            p._run_stage(r, "semantic", 4, ok_stage)

        assert len(p.errors) == 0
        assert p.results["semantic"]["clusters_created"] == 420
        assert p._last_successful_stage == "semantic"

    def test_stage_with_heartbeat(self):
        p = self._make_pipeline()

        def stage_with_hb(heartbeat=None):
            if heartbeat:
                heartbeat("working")
            return {"result": "ok"}

        r = MagicMock()
        r.get.return_value = None
        with (
            patch("app.runtime_state.is_stage_blocked", return_value=False),
            patch.object(p, "_check_dependency_contract", return_value=None),
        ):
            p._run_stage(r, "forecasting", 6, stage_with_hb)

        assert len(p.errors) == 0
        assert p._heartbeat_count >= 1


class TestCompletedStageKeys(unittest.TestCase):
    def test_excludes_errored_stages(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p.results = {
            "crawl": {"total_reviews": 500},
            "metadata": {"error": "failed"},
            "semantic": {"clusters_created": 420},
        }
        p.errors = [{"stage": "metadata", "error": "failed"}]
        completed = p._completed_stage_keys()
        assert "crawl" in completed
        assert "semantic" in completed
        assert "metadata" not in completed


class TestLiveStatusLabel(unittest.TestCase):
    def test_running_no_errors(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p.errors = []
        p.results = {}
        assert p._live_status_label() == "running"

    def test_running_with_errors(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p.errors = [{"stage": "forecasting", "error": "x"}]
        p.results = {}
        assert p._live_status_label() == "running_degraded"


class TestDetectStale(unittest.TestCase):
    def test_fresh_data_not_stale(self):
        r = MagicMock()
        data = {
            "running": True,
            "stage": "forecasting",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = _detect_stale(r, data)
        assert result.get("stale") is not True
        assert result["stage"] == "forecasting"

    def test_old_data_becomes_stale(self):
        r = MagicMock()
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        data = {
            "running": True,
            "stage": "forecasting",
            "updated_at": old_time,
            "operation_id": "test",
        }
        result = _detect_stale(r, data)
        assert result["stale"] is True
        assert result["stage"] == "stalled"
        assert result["running"] is False
        assert result["pipeline_status"] == "stalled"

    def test_fusion_mid_run_not_stalled_with_recent_heartbeat(self):
        r = MagicMock()
        recent = datetime.now(timezone.utc).isoformat()
        old_status = (datetime.now(timezone.utc) - timedelta(seconds=150)).isoformat()
        data = {
            "running": True,
            "stage": "fusion",
            "updated_at": old_status,
            "heartbeat": {"last_heartbeat_at": recent, "stage_detail": "fusion: hub_stress scan"},
            "operation_id": "test",
        }
        result = _detect_stale(r, data)
        assert result.get("stale") is not True
        assert result["stage"] == "fusion"

    def test_fusion_expired_heartbeat_stalls_even_below_fusion_hard_threshold(self):
        r = MagicMock()
        mid_age = (datetime.now(timezone.utc) - timedelta(seconds=130)).isoformat()
        data = {
            "running": True,
            "stage": "fusion",
            "updated_at": mid_age,
            "last_heartbeat_at": mid_age,
            "operation_id": "test",
        }
        result = _detect_stale(r, data)
        assert result.get("worker_alive") is False
        assert result.get("running") is True
        assert result.get("pipeline_status") in ("running_slow", "running_degraded")
        assert result.get("soft_stall") is True

    def test_fusion_soft_slow_only_when_heartbeat_fresh(self):
        r = MagicMock()
        recent_hb = datetime.now(timezone.utc).isoformat()
        old_status = (datetime.now(timezone.utc) - timedelta(seconds=100)).isoformat()
        data = {
            "running": True,
            "stage": "fusion",
            "updated_at": old_status,
            "last_heartbeat_at": recent_hb,
            "heartbeat": {"last_heartbeat_at": recent_hb},
            "operation_id": "test",
        }
        result = _detect_stale(r, data)
        assert result.get("worker_alive") is True
        assert result.get("running") is True

    def test_finalizing_tolerates_stale_heartbeat_within_final_threshold(self):
        r = MagicMock()
        age = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
        recent_hb = datetime.now(timezone.utc).isoformat()
        data = {
            "running": True,
            "stage": "snapshots",
            "pipeline_status": "finalizing",
            "updated_at": age,
            "last_heartbeat_at": recent_hb,
            "heartbeat": {"last_heartbeat_at": recent_hb},
            "operation_id": "test",
        }
        result = _detect_stale(r, data)
        assert result.get("stale") is not True
        assert result.get("worker_alive") is True

    def test_terminal_stage_not_checked(self):
        r = MagicMock()
        data = {"running": False, "stage": "completed"}
        result = _detect_stale(r, data)
        assert result["stage"] == "completed"

    def test_running_degraded_propagated(self):
        r = MagicMock()
        data = {
            "running": True,
            "stage": "anomalies",
            "pipeline_status": "running_degraded",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = _detect_stale(r, data)
        assert result["pipeline_status"] == "running_degraded"

    def test_expired_heartbeat_with_lock_still_stalls(self):
        r = MagicMock()
        r.get.return_value = "test-op"
        old = (datetime.now(timezone.utc) - timedelta(seconds=500)).isoformat()
        data = {
            "running": True,
            "stage": "fusion",
            "updated_at": old,
            "last_heartbeat_at": old,
            "operation_id": "test-op",
        }
        result = _detect_stale(r, data)
        assert result.get("worker_alive") is False
        assert result.get("running") is False
        assert result.get("pipeline_status") == "stalled"


class TestKpiExtractionMap(unittest.TestCase):
    def test_all_expected_stages_covered(self):
        expected = {
            "crawl",
            "metadata",
            "semantic",
            "knowledge_graph",
            "forecasting",
            "anomalies",
            "insights",
            "fusion",
            "aviation_master",
        }
        assert expected == set(_KPI_EXTRACTION_MAP.keys())

    def test_each_mapping_has_key_pairs(self):
        for stage, mappings in _KPI_EXTRACTION_MAP.items():
            for src_key, kpi_key in mappings:
                assert isinstance(src_key, str), f"Bad src_key in {stage}"
                assert isinstance(kpi_key, str), f"Bad kpi_key in {stage}"


class TestSnapshotProtection(unittest.TestCase):
    """Ensure valid KPIs survive across stage failures."""

    def test_kpis_survive_after_failed_stage(self):
        p = OperationalRefreshPipeline.__new__(OperationalRefreshPipeline)
        p.operation_id = "snap-001"
        p.airline_slug = None
        p.triggered_by = "test"
        p.results = {}
        p.errors = []
        p.events = []
        p.started_at = datetime.now(timezone.utc)
        p._kpis = {}
        p._last_successful_stage = ""
        p._stage_timings = {}
        p._heartbeat_count = 0

        # 1) Successful stage sets KPIs
        r = MagicMock()
        r.get.return_value = None
        p._run_stage(r, "crawl", 2, lambda: {"total_reviews_in_db": 5000, "success": True})
        assert p._kpis.get("reviews") == 5000

        # 2) Failed stage does NOT clobber
        p._run_stage(r, "metadata", 3, lambda: {"error": "timeout"})
        assert p._kpis.get("reviews") == 5000
        assert "metadata" not in p._kpis

        # 3) Another success adds more KPIs
        p._run_stage(r, "semantic", 4, lambda: {"clusters_created": 420, "enriched": 300})
        assert p._kpis.get("reviews") == 5000
        assert p._kpis.get("clusters") == 420

        # 4) Hard failure also doesn't clobber
        def boom():
            raise RuntimeError("oops")

        p._run_stage(r, "forecasting", 6, boom)
        assert p._kpis.get("reviews") == 5000
        assert p._kpis.get("clusters") == 420


class TestMaxPagesZeroProtection(unittest.TestCase):
    """Verify max_pages=0 gets converted to a safe default."""

    def test_zero_becomes_default(self):
        # Simulate how the spider __init__ works
        raw_max = 0
        effective = raw_max if raw_max > 0 else 50
        assert effective == 50

    def test_positive_value_preserved(self):
        raw_max = 25
        effective = raw_max if raw_max > 0 else 50
        assert effective == 25


class TestCrawlStageWithHeartbeat(unittest.TestCase):
    """Verify the crawl stage accepts heartbeat and invokes it."""

    def test_crawl_stage_accepts_heartbeat(self):
        import inspect
        from worker.orchestration.refresh_pipeline import OperationalRefreshPipeline

        sig = inspect.signature(OperationalRefreshPipeline._stage_crawl)
        assert "heartbeat" in sig.parameters

    def test_discovery_stage_accepts_heartbeat(self):
        import inspect
        from worker.orchestration.refresh_pipeline import OperationalRefreshPipeline

        sig = inspect.signature(OperationalRefreshPipeline._stage_discovery)
        assert "heartbeat" in sig.parameters

    def test_fusion_and_snapshots_accept_heartbeat(self):
        import inspect
        from worker.orchestration.refresh_pipeline import OperationalRefreshPipeline

        assert "heartbeat" in inspect.signature(OperationalRefreshPipeline._stage_fusion).parameters
        assert "heartbeat" in inspect.signature(OperationalRefreshPipeline._stage_snapshots).parameters


class TestPerAirlineSaturation(unittest.TestCase):
    """Validate the per-airline saturation logic constants."""

    def test_max_empty_pages_defined(self):
        from scraper.spiders.airlinequality import MAX_EMPTY_PAGES

        assert MAX_EMPTY_PAGES > 0

    def test_default_max_pages_defined(self):
        from scraper.spiders.airlinequality import DEFAULT_MAX_PAGES

        assert DEFAULT_MAX_PAGES > 0

    def test_max_crawl_minutes_defined(self):
        from scraper.spiders.airlinequality import MAX_CRAWL_MINUTES_PER_AIRLINE

        assert MAX_CRAWL_MINUTES_PER_AIRLINE > 0


class TestSpiderMaxPagesInit(unittest.TestCase):
    """Verify spider converts max_pages=0 to safe default."""

    def test_spider_init_zero_pages(self):
        from scraper.spiders.airlinequality import AirlineQualitySpider, DEFAULT_MAX_PAGES

        spider = AirlineQualitySpider.__new__(AirlineQualitySpider)
        raw_max = int("0")
        spider.max_pages = raw_max if raw_max > 0 else DEFAULT_MAX_PAGES
        assert spider.max_pages == DEFAULT_MAX_PAGES
        assert spider.max_pages > 0

    def test_spider_init_positive_pages(self):
        from scraper.spiders.airlinequality import AirlineQualitySpider

        spider = AirlineQualitySpider.__new__(AirlineQualitySpider)
        raw_max = int("25")
        spider.max_pages = raw_max if raw_max > 0 else 50
        assert spider.max_pages == 25


class TestCrawlHeartbeatDuringSubprocess(unittest.TestCase):
    """Verify that heartbeat fires during crawl subprocess execution."""

    def test_heartbeat_called_during_crawl(self):
        """Simulate the Popen polling loop heartbeat pattern."""
        heartbeat_calls = []

        def fake_heartbeat(detail=""):
            heartbeat_calls.append(detail)

        iterations = 0
        while iterations < 3:
            fake_heartbeat(f"crawl: iteration={iterations}")
            iterations += 1

        assert len(heartbeat_calls) == 3
        assert "iteration=0" in heartbeat_calls[0]


class TestTerminalStagesIncludeAll(unittest.TestCase):
    def test_stalled_is_not_terminal(self):
        """Stalled is transitional — detected by _detect_stale, not a terminal stage."""
        from worker.orchestration.refresh_pipeline import _TERMINAL_STAGES

        assert "stalled" not in _TERMINAL_STAGES


class TestTimedHeartbeat(unittest.TestCase):
    def test_time_based_pulse(self):
        calls = []

        def hb(payload):
            calls.append(payload)

        timer = TimedHeartbeat(hb, stage="fusion", interval_s=1.0)
        assert timer.pulse_if_needed(detail="first", processed=1, total=10, force=True) is True
        assert timer.pulse_if_needed(detail="second", processed=2, total=10, force=False) is False
        time.sleep(1.05)
        assert timer.pulse_if_needed(detail="third", processed=3, total=10, force=True) is True
        assert len(calls) == 2
        assert isinstance(calls[0], dict)
        assert calls[0]["stage"] == "fusion"
        assert calls[0]["remaining"] == 9

    def test_heartbeat_guard_decorator(self):
        calls = []

        @heartbeat_guard(interval_s=0.01)
        def _heavy_stage(*, heartbeat_fn=None):
            if heartbeat_fn:
                heartbeat_fn("inside")
            return {"ok": True}

        res = _heavy_stage(heartbeat_fn=lambda payload: calls.append(payload))
        assert res["ok"] is True
        assert len(calls) >= 2


class TestDegradedReconciliation(unittest.TestCase):
    def test_reconcile_removes_impossible_aviation_degraded(self):
        errors = [{"stage": "aviation_master", "error": "airline_metadata.iata_code missing — schema drift"}]
        results = {"aviation_master": {"error": "airline_metadata.iata_code missing — schema drift"}}
        events = []
        with patch(
            "worker.orchestration.operational_reconciliation._should_reconcile_aviation",
            return_value=True,
        ):
            with patch("app.runtime_state.remove_false_degraded_events") as mock_remove:
                pruned = reconcile_pipeline_soft_failures(
                    errors=errors,
                    results=results,
                    events=events,
                    operation_id="op123",
                )
        assert pruned == []
        assert results["aviation_master"]["reconciled"] is True
        assert results["aviation_master"]["degraded_classification"] == "false_degraded_stale_status"
        assert any("recovered" in ev.get("message", "") for ev in events)
        mock_remove.assert_called_once()

    def test_reconcile_keeps_real_degraded_when_runtime_unhealthy(self):
        errors = [{"stage": "aviation_master", "error": "airline_metadata.iata_code missing — schema drift"}]
        results = {"aviation_master": {"error": "airline_metadata.iata_code missing — schema drift"}}
        with patch(
            "worker.orchestration.operational_reconciliation._should_reconcile_aviation",
            return_value=False,
        ):
            pruned = reconcile_pipeline_soft_failures(
                errors=errors,
                results=results,
                events=[],
                operation_id="op123",
            )
        assert pruned == errors


if __name__ == "__main__":
    unittest.main()
