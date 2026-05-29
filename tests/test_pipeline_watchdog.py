"""Pipeline watchdog — heartbeat, stall detection, orphan recovery."""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

_redis_mod = types.ModuleType("redis")
_redis_mod.Redis = MagicMock()
sys.modules.setdefault("redis", _redis_mod)

_session_stub = types.ModuleType("database.session")
_session_stub.SessionLocal = MagicMock()
_session_stub.engine = MagicMock()
sys.modules.setdefault("database.session", _session_stub)


class TestWorkerAlive(unittest.TestCase):
    def test_worker_dead_when_heartbeat_expired(self):
        from worker.orchestration.pipeline_watchdog import compute_worker_alive, HEARTBEAT_TIMEOUT_S

        old = (datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_TIMEOUT_S + 10)).isoformat()
        data = {"running": True, "updated_at": old, "operation_id": "op1"}
        self.assertFalse(compute_worker_alive(data))

    def test_worker_alive_when_heartbeat_fresh(self):
        from worker.orchestration.pipeline_watchdog import compute_worker_alive

        recent = datetime.now(timezone.utc).isoformat()
        data = {"running": True, "updated_at": recent}
        self.assertTrue(compute_worker_alive(data))


class TestStartingOrphan(unittest.TestCase):
    def test_starting_stuck_becomes_stalled(self):
        from worker.orchestration import pipeline_watchdog as wd

        old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        data = {
            "running": True,
            "stage": "starting",
            "progress": 2,
            "updated_at": old,
            "started_at": old,
            "operation_id": "9c8c6bef-fa8",
            "pipeline_status": "running_slow",
            "events": [],
        }
        r = MagicMock()
        r.get.return_value = None
        r.set.return_value = True

        enriched, action = wd.evaluate_pipeline_health(data, r)
        self.assertEqual(action, wd.ReconcileAction.STALLED)
        self.assertFalse(enriched["running"])
        self.assertEqual(enriched["pipeline_status"], "stalled")
        self.assertFalse(enriched["worker_alive"])
        self.assertIn("stall_diagnosis", enriched)
        self.assertEqual(enriched["stall_diagnosis"]["failure_type"], "starting_orphan")

    def test_user_reported_zombie_payload(self):
        """Reproduce production JSON: starting, 178s no heartbeat, was running_slow + worker_alive true."""
        from worker.orchestration import pipeline_watchdog as wd

        ts = (datetime.now(timezone.utc) - timedelta(seconds=178)).isoformat()
        data = {
            "operation_id": "9c8c6bef-fa8",
            "running": True,
            "stage": "starting",
            "progress": 2,
            "updated_at": ts,
            "triggered_by": "manual",
            "events": [],
            "pipeline_status": "running_slow",
            "started_at": ts,
            "last_heartbeat_at": ts,
        }
        r = MagicMock()
        enriched, action = wd.evaluate_pipeline_health(data, r)
        self.assertFalse(enriched["worker_alive"])
        self.assertFalse(enriched["running"])
        self.assertEqual(enriched["pipeline_status"], "stalled")
        self.assertEqual(action, wd.ReconcileAction.STALLED)


class TestReconcilePersist(unittest.TestCase):
    def test_reconcile_persists_stall_to_redis(self):
        from worker.orchestration import pipeline_watchdog as wd

        old = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
        payload = {
            "running": True,
            "stage": "starting",
            "progress": 2,
            "updated_at": old,
            "operation_id": "op-zombie",
        }
        store = {wd.REDIS_STATUS_KEY: json.dumps(payload)}

        r = MagicMock()

        def mock_get(key):
            return store.get(key)

        def mock_set(key, val, ex=None, nx=False):
            if nx and key == wd.REDIS_WATCHDOG_LOCK_KEY:
                return True
            store[key] = val
            return True

        r.get.side_effect = mock_get
        r.set.side_effect = mock_set
        r.delete.return_value = 1

        with patch.object(wd, "_redis", return_value=r):
            result = wd.reconcile_pipeline_state(persist=True)

        self.assertEqual(result.get("action"), wd.ReconcileAction.STALLED)
        saved = json.loads(store[wd.REDIS_STATUS_KEY])
        self.assertFalse(saved["running"])
        self.assertEqual(saved["pipeline_status"], "stalled")


class TestQueuedGrace(unittest.TestCase):
    def test_queued_job_not_stalled_before_grace(self):
        from worker.orchestration import pipeline_watchdog as wd

        recent = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        data = {
            "running": True,
            "stage": "queued",
            "progress": 0,
            "pipeline_status": "queued",
            "updated_at": recent,
            "operation_id": "op-queued",
            "events": [],
        }
        enriched, action = wd.evaluate_pipeline_health(data, MagicMock())
        self.assertIn(action, (wd.ReconcileAction.ENRICHED, wd.ReconcileAction.SOFT_WARNING))
        self.assertTrue(enriched["running"])


class TestFusionHeartbeatGrace(unittest.TestCase):
    def test_fusion_60s_without_heartbeat_not_hard_stalled(self):
        from worker.orchestration import pipeline_watchdog as wd

        old = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        data = {
            "running": True,
            "stage": "fusion",
            "progress": 92,
            "pipeline_status": "finalizing",
            "updated_at": old,
            "last_heartbeat_at": old,
            "operation_id": "op-fusion",
            "events": [],
        }
        enriched, action = wd.evaluate_pipeline_health(data, MagicMock())
        self.assertNotEqual(action, wd.ReconcileAction.STALLED)
        self.assertTrue(enriched["running"])


if __name__ == "__main__":
    unittest.main()
