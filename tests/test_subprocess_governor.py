"""Tests for the subprocess lifecycle governor.

Covers all termination triggers, kill protocol, and state transitions.
"""

from __future__ import annotations

import json
import subprocess
import time
from unittest.mock import MagicMock, patch


from worker.subprocess_governor import (
    SubprocessGovernor,
    CrawlState,
    TelemetrySnapshot,
    TerminationEvent,
    MAX_NO_INSERT_SECONDS,
    MAX_STATIC_PAGE_SECONDS,
    MAX_TELEMETRY_STATIC_SECONDS,
    MAX_ZERO_THROUGHPUT_SECONDS,
    CRAWL_HARD_TIMEOUT_S,
)


# ── Fixtures ─────────────────────────────────────────────────────────


class FakeRedis:
    """Minimal in-memory Redis substitute for testing."""

    def __init__(self, data: dict | None = None):
        self._store: dict[str, str] = {}
        if data:
            for k, v in data.items():
                self._store[k] = json.dumps(v) if isinstance(v, dict) else v

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class FakeProcess:
    """Controllable subprocess.Popen substitute."""

    def __init__(self, exit_after_polls: int = 5, returncode: int = 0):
        self._polls_remaining = exit_after_polls
        self.returncode: int | None = None
        self._final_returncode = returncode
        self.pid = 99999
        self._terminated = False
        self._killed = False

    def poll(self) -> int | None:
        if self._terminated or self._killed:
            self.returncode = self._final_returncode
            return self.returncode
        self._polls_remaining -= 1
        if self._polls_remaining <= 0:
            self.returncode = self._final_returncode
            return self.returncode
        return None

    def terminate(self) -> None:
        self._terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self._killed = True
        self.returncode = -9

    def wait(self, timeout: float = 30) -> int:
        if self._terminated or self._killed:
            return self.returncode or 0
        raise subprocess.TimeoutExpired(cmd="scrapy", timeout=timeout)

    def communicate(self, timeout: float = 30) -> tuple[str, str]:
        return ("", "")


def _make_governor(
    proc: FakeProcess | None = None,
    telemetry: dict | None = None,
    heartbeat_fn: MagicMock | None = None,
) -> SubprocessGovernor:
    """Build a SubprocessGovernor with test doubles."""
    if proc is None:
        proc = FakeProcess(exit_after_polls=3)

    redis_data = {}
    if telemetry:
        redis_data["skytrax:ops:refresh:status"] = {
            "crawl_telemetry": telemetry,
        }

    fake_redis = FakeRedis(redis_data)
    metrics = MagicMock()

    gov = SubprocessGovernor(
        proc=proc,
        redis_status_key="skytrax:ops:refresh:status",
        redis_fn=lambda: fake_redis,
        heartbeat_fn=heartbeat_fn or MagicMock(),
        operation_id="test-op",
        metrics_fn=metrics,
    )
    return gov


# ── TelemetrySnapshot tests ──────────────────────────────────────────


class TestTelemetrySnapshot:
    def test_content_hash_deterministic(self):
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3, airline="test")
        h1 = snap.content_hash()
        h2 = snap.content_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_changes_on_different_data(self):
        s1 = TelemetrySnapshot(pages=10, inserts=5, dupes=3, airline="test")
        s2 = TelemetrySnapshot(pages=11, inserts=5, dupes=3, airline="test")
        assert s1.content_hash() != s2.content_hash()

    def test_content_hash_ignores_timestamp(self):
        s1 = TelemetrySnapshot(pages=10, inserts=5, dupes=3, airline="test", timestamp=1.0)
        s2 = TelemetrySnapshot(pages=10, inserts=5, dupes=3, airline="test", timestamp=999.0)
        assert s1.content_hash() == s2.content_hash()


# ── CrawlState tests ────────────────────────────────────────────────


class TestCrawlState:
    def test_all_states_defined(self):
        expected = {
            "running",
            "running_no_progress",
            "saturated",
            "terminating",
            "terminated",
            "zombie",
            "stalled",
            "completed",
            "completed_degraded",
        }
        actual = {s.value for s in CrawlState}
        assert expected == actual

    def test_state_is_string_enum(self):
        assert CrawlState.RUNNING == "running"
        assert str(CrawlState.ZOMBIE) == "CrawlState.ZOMBIE"


# ── Natural exit tests ──────────────────────────────────────────────


class TestNaturalExit:
    @patch("worker.subprocess_governor.HEARTBEAT_INTERVAL_S", 0)
    def test_process_exits_naturally(self):
        proc = FakeProcess(exit_after_polls=2, returncode=0)
        gov = _make_governor(proc=proc)
        result = gov.run()
        assert result["state"] == CrawlState.COMPLETED.value
        assert result["returncode"] == 0
        assert "termination" not in result

    @patch("worker.subprocess_governor.HEARTBEAT_INTERVAL_S", 0)
    def test_process_exits_with_error(self):
        proc = FakeProcess(exit_after_polls=2, returncode=1)
        gov = _make_governor(proc=proc)
        result = gov.run()
        assert result["state"] == CrawlState.COMPLETED_DEGRADED.value
        assert result["returncode"] == 1


# ── Saturation trigger tests ────────────────────────────────────────


class TestSaturationTrigger:
    @patch("worker.subprocess_governor.HEARTBEAT_INTERVAL_S", 0)
    def test_scrapy_saturation_triggers_termination(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(
            proc=proc,
            telemetry={"saturated": True, "pages_processed": 50, "reviews_added": 10},
        )
        result = gov.run()
        assert result["state"] in (CrawlState.TERMINATED.value, CrawlState.SATURATED.value)
        assert result.get("termination", {}).get("trigger") == "scrapy_saturation"
        assert proc._terminated


# ── No inserts trigger ──────────────────────────────────────────────


class TestNoInsertsTrigger:
    def test_evaluate_no_inserts(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=20, inserts=0, dupes=50)
        gov._last_insert_time = time.time() - (MAX_NO_INSERT_SECONDS + 10)
        gov._last_insert_count = 0
        trigger = gov._evaluate_triggers(snap, 200)
        assert trigger == "no_inserts"

    def test_no_trigger_when_inserts_recent(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=20, inserts=10, dupes=5)
        gov._last_insert_time = time.time()
        gov._last_insert_count = 5
        trigger = gov._evaluate_triggers(snap, 60)
        assert trigger is None


# ── Reactor hanging trigger ─────────────────────────────────────────


class TestReactorHangingTrigger:
    def test_evaluate_reactor_hanging(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=10, inserts=10, dupes=5)
        gov._last_page_count = 10
        gov._last_page_time = time.time() - (MAX_STATIC_PAGE_SECONDS + 10)
        gov._last_insert_count = 10
        gov._last_insert_time = time.time()
        trigger = gov._evaluate_triggers(snap, 200)
        assert trigger == "reactor_hanging"


# ── Telemetry frozen trigger ────────────────────────────────────────


class TestTelemetryFrozenTrigger:
    def test_evaluate_telemetry_frozen(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)
        gov._last_telemetry_hash = snap.content_hash()
        gov._last_telemetry_hash_time = time.time() - (MAX_TELEMETRY_STATIC_SECONDS + 10)
        gov._last_insert_count = 5
        gov._last_insert_time = time.time()
        gov._last_page_count = 10
        gov._last_page_time = time.time()
        trigger = gov._evaluate_triggers(snap, 200)
        assert trigger == "telemetry_frozen"

    def test_no_trigger_when_hash_changes(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)
        gov._last_telemetry_hash = "different_hash"
        gov._last_telemetry_hash_time = time.time() - 300
        gov._last_insert_count = 5
        gov._last_insert_time = time.time()
        gov._last_page_count = 10
        gov._last_page_time = time.time()
        trigger = gov._evaluate_triggers(snap, 200)
        assert trigger is None


# ── Zero throughput trigger ─────────────────────────────────────────


class TestZeroThroughputTrigger:
    def test_evaluate_zero_throughput(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        gov.started_at = time.time() - 60

        snap = TelemetrySnapshot(pages=20, inserts=0, dupes=0, throughput=0.0)
        gov._last_throughput_time = time.time() - (MAX_ZERO_THROUGHPUT_SECONDS + 10)
        gov._last_insert_count = 0
        gov._last_insert_time = time.time() - (MAX_NO_INSERT_SECONDS - 10)
        gov._last_page_count = 20
        gov._last_page_time = time.time()
        gov._last_telemetry_hash = "something"
        gov._last_telemetry_hash_time = time.time()
        trigger = gov._evaluate_triggers(snap, 200)
        assert trigger == "zero_throughput"


# ── Hard timeout trigger ────────────────────────────────────────────


class TestHardTimeoutTrigger:
    def test_evaluate_hard_timeout(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        snap = TelemetrySnapshot()
        trigger = gov._evaluate_triggers(snap, CRAWL_HARD_TIMEOUT_S + 1)
        assert trigger == "hard_timeout"


# ── Graceful terminate protocol ─────────────────────────────────────


class TestGracefulTerminate:
    def test_terminate_sends_sigterm_first(self):
        proc = FakeProcess(exit_after_polls=100)
        gov = _make_governor(proc=proc)
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)
        gov._terminate("test_trigger", snap, 100.0)

        assert proc._terminated
        assert gov.state == CrawlState.TERMINATED
        assert gov.termination_event is not None
        assert gov.termination_event.trigger == "test_trigger"
        assert gov.termination_event.kill_type == "graceful"


# ── Hard kill fallback ──────────────────────────────────────────────


class TestHardKillFallback:
    def test_hard_kill_when_sigterm_timeout(self):
        proc = FakeProcess(exit_after_polls=100)

        def stubborn_wait(timeout=30):
            if not proc._killed:
                raise subprocess.TimeoutExpired(cmd="scrapy", timeout=timeout)
            return -9

        proc.wait = stubborn_wait
        gov = _make_governor(proc=proc)
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)
        gov._terminate("test_trigger", snap, 100.0)

        assert proc._killed
        assert gov.termination_event.kill_type == "hard_kill"


# ── Zombie detection ────────────────────────────────────────────────


class TestZombieDetection:
    def test_zombie_state_on_unkillable_process(self):
        proc = FakeProcess(exit_after_polls=100)

        def stubborn_wait(timeout=30):
            raise subprocess.TimeoutExpired(cmd="scrapy", timeout=timeout)

        proc.wait = stubborn_wait
        gov = _make_governor(proc=proc)
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)

        with patch.object(gov, "_force_kill_tree"):
            gov._terminate("test_trigger", snap, 100.0)

        assert gov.state == CrawlState.ZOMBIE
        assert gov.termination_event.kill_type == "zombie"


# ── State update tests ──────────────────────────────────────────────


class TestStateUpdates:
    def test_state_running_with_progress(self):
        gov = _make_governor()
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3)
        gov._last_insert_time = time.time()
        gov._update_state(snap, 30)
        assert gov.state == CrawlState.RUNNING

    def test_state_saturated(self):
        gov = _make_governor()
        snap = TelemetrySnapshot(pages=50, inserts=0, saturated=True)
        gov._update_state(snap, 300)
        assert gov.state == CrawlState.SATURATED

    def test_state_running_no_progress(self):
        gov = _make_governor()
        snap = TelemetrySnapshot(pages=30, inserts=0, dupes=50)
        gov._last_insert_time = time.time() - 90
        gov._update_state(snap, 120)
        assert gov.state == CrawlState.RUNNING_NO_PROGRESS

    def test_state_stalled(self):
        gov = _make_governor()
        snap = TelemetrySnapshot(pages=5, inserts=3, stalled=True)
        gov._last_insert_time = time.time()
        gov._update_state(snap, 100)
        assert gov.state == CrawlState.STALLED


# ── Heartbeat emission tests ────────────────────────────────────────


class TestHeartbeatEmission:
    def test_heartbeat_includes_state(self):
        hb = MagicMock()
        gov = _make_governor(heartbeat_fn=hb)
        gov.state = CrawlState.RUNNING_NO_PROGRESS
        snap = TelemetrySnapshot(pages=10, inserts=5, dupes=3, airline="TestAir")
        gov._emit_heartbeat(snap, 60.0)

        hb.assert_called_once()
        detail = hb.call_args[0][0]
        assert "state=running_no_progress" in detail
        assert "TestAir" in detail

    def test_heartbeat_skipped_when_no_fn(self):
        gov = _make_governor(heartbeat_fn=None)
        gov.heartbeat_fn = None
        snap = TelemetrySnapshot()
        gov._emit_heartbeat(snap, 10.0)


# ── Trigger description ─────────────────────────────────────────────


class TestTriggerDescription:
    def test_known_triggers_have_descriptions(self):
        triggers = [
            "hard_timeout",
            "scrapy_saturation",
            "no_inserts",
            "reactor_hanging",
            "duplicate_streak",
            "static_airline",
            "telemetry_frozen",
            "zero_throughput",
        ]
        for trigger in triggers:
            desc = SubprocessGovernor._trigger_description(trigger)
            assert len(desc) > 10
            assert "Unknown" not in desc

    def test_unknown_trigger_returns_generic(self):
        desc = SubprocessGovernor._trigger_description("something_new")
        assert "Unknown" in desc


# ── Redis cleanup tests ─────────────────────────────────────────────


class TestRedisCleanup:
    def test_cleanup_writes_termination_data(self):
        fake_redis = FakeRedis(
            {
                "skytrax:ops:refresh:status": {
                    "crawl_telemetry": {"pages_processed": 10},
                    "updated_at": "2025-01-01T00:00:00Z",
                }
            }
        )
        proc = FakeProcess()
        gov = SubprocessGovernor(
            proc=proc,
            redis_status_key="skytrax:ops:refresh:status",
            redis_fn=lambda: fake_redis,
            operation_id="test",
        )
        gov.termination_event = TerminationEvent(
            reason="test",
            trigger="test_trigger",
            state=CrawlState.TERMINATED,
            elapsed_s=100,
            telemetry={},
            kill_type="graceful",
        )
        gov.state = CrawlState.TERMINATED
        snap = TelemetrySnapshot()
        gov._cleanup_redis(snap)

        raw = fake_redis.get("skytrax:ops:refresh:status")
        data = json.loads(raw)
        ct = data["crawl_telemetry"]
        assert ct["governor_terminated"] is True
        assert ct["termination_trigger"] == "test_trigger"
        assert ct["termination_state"] == "terminated"


# ── Early exit guard (first 30s) ────────────────────────────────────


class TestEarlyExitGuard:
    def test_no_triggers_in_warmup_period(self):
        gov = _make_governor()
        gov.started_at = time.time()
        snap = TelemetrySnapshot(pages=0, inserts=0, dupes=0, throughput=0.0)
        gov._last_insert_time = time.time() - 500
        gov._last_page_time = time.time() - 500
        trigger = gov._evaluate_triggers(snap, elapsed=10)
        assert trigger is None

    def test_hard_timeout_still_triggers_in_warmup(self):
        gov = _make_governor()
        snap = TelemetrySnapshot()
        trigger = gov._evaluate_triggers(snap, elapsed=CRAWL_HARD_TIMEOUT_S + 1)
        assert trigger == "hard_timeout"
