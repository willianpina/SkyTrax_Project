"""Async refresh orchestration — 202 accept, queue dispatch, timeout isolation."""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_session_stub = types.ModuleType("database.session")
_session_stub.engine = MagicMock()
_session_stub.SessionLocal = MagicMock()
_session_stub.get_session = MagicMock()
_session_stub.Base = MagicMock()
sys.modules.setdefault("database.session", _session_stub)

_db_ops = types.ModuleType("database.models.operations")
_db_ops.OperationalRefreshRun = MagicMock()
sys.modules.setdefault("database.models.operations", _db_ops)

_redis_mod = types.ModuleType("redis")
_redis_mod.Redis = MagicMock()
sys.modules.setdefault("redis", _redis_mod)


def _mock_redis_store() -> tuple[MagicMock, dict[str, str]]:
    store: dict[str, str] = {}
    mock_redis = MagicMock()

    def mock_set(key, val, ex=None, nx=False):
        if nx and key in store:
            return False
        store[key] = val
        return True

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = lambda key: store.get(key)
    mock_redis.delete = lambda key: store.pop(key, None)
    return mock_redis, store


class TestOperationLifecycle(unittest.TestCase):
    def test_lifecycle_from_stage_mapping(self):
        from worker.orchestration.operation_lifecycle import lifecycle_from_stage

        self.assertEqual(lifecycle_from_stage("crawl"), "running")
        self.assertEqual(lifecycle_from_stage("snapshots", "finalizing"), "finalizing")
        self.assertEqual(lifecycle_from_stage("completed"), "completed")

    def test_transitions_and_terminal_clear(self):
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        mock_redis, _ = _mock_redis_store()
        mgr = OperationLifecycleManager(redis_client=mock_redis)
        accept = mgr.accept_refresh(operation_id="op1", triggered_by="test")
        self.assertTrue(accept["accepted"])
        mgr.transition("op1", "running")
        self.assertEqual(mgr.get_active_operation()["lifecycle_state"], "running")
        mgr.transition("op1", "completed")
        self.assertIsNone(mgr.get_active_operation())

    def test_duplicate_refresh_prevented(self):
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        mock_redis, _ = _mock_redis_store()
        mgr = OperationLifecycleManager(redis_client=mock_redis)
        self.assertTrue(mgr.accept_refresh(operation_id="op-a", triggered_by="manual")["accepted"])
        second = mgr.accept_refresh(operation_id="op-b", triggered_by="manual")
        self.assertFalse(second["accepted"])
        self.assertEqual(second["reason"], "already_running")


class TestRefreshPipelineFastPath(unittest.TestCase):
    def test_get_live_status_fast_skips_integrity(self):
        from worker.orchestration import refresh_pipeline as rp

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(
            {
                "operation_id": "x1",
                "stage": "crawl",
                "running": True,
                "progress": 40,
            }
        )
        with (
            patch.object(rp, "_redis", return_value=mock_redis),
            patch.object(
                rp,
                "_detect_stale",
                side_effect=lambda _r, d: d,
            ),
        ):
            data = rp.get_live_status_fast()
        self.assertEqual(data["stage"], "crawl")
        self.assertEqual(data["operation_id"], "x1")


class TestDispatchOnly(unittest.TestCase):
    def test_enqueue_no_inline_pipeline(self):
        from api import operations_dispatch as od

        mock_queue = MagicMock()
        mock_queue.count = 0
        mock_queue.name = "default"
        mock_job = MagicMock()
        mock_job.id = "j-99"
        mock_queue.enqueue.return_value = mock_job

        with (
            patch.object(od, "get_redis_and_queue", return_value=(MagicMock(), mock_queue)),
            patch(
                "worker.orchestration.refresh_pipeline.set_initial_status",
            ),
            patch(
                "worker.orchestration.operation_lifecycle.OperationLifecycleManager.accept_refresh",
                return_value={"accepted": True, "operation": {"operation_id": "op99"}},
            ),
        ):
            result = od.accept_and_dispatch_refresh(triggered_by="test")
        self.assertEqual(result["http_status"], 202)
        self.assertTrue(result["body"]["queued"])
        mock_queue.enqueue.assert_called_once()


@unittest.skipUnless(
    __import__("importlib").util.find_spec("fastapi"),
    "fastapi not installed",
)
class TestRefreshHttpContract(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routers.operations import router as operations_router
        from app.middleware import TimeoutMiddleware

        app = FastAPI()
        app.add_middleware(TimeoutMiddleware, timeout_seconds=0.05)
        app.include_router(operations_router, prefix="/api")
        self.client = TestClient(app)

    def test_refresh_returns_202(self):
        with patch("api.routers.operations.accept_and_dispatch_refresh") as dispatch:
            dispatch.return_value = {
                "http_status": 202,
                "body": {
                    "status": "accepted",
                    "queued": True,
                    "operation_id": "abc123",
                    "job_id": "job-1",
                },
            }
            res = self.client.post("/api/operations/refresh")
        self.assertEqual(res.status_code, 202)
        self.assertEqual(res.json()["status"], "accepted")

    def test_refresh_exempt_from_middleware_timeout(self):
        def slow_dispatch(**_kwargs):
            import time

            time.sleep(0.2)
            return {
                "http_status": 202,
                "body": {"status": "accepted", "queued": True, "operation_id": "slow-op"},
            }

        with patch(
            "api.routers.operations.accept_and_dispatch_refresh",
            side_effect=slow_dispatch,
        ):
            res = self.client.post("/api/operations/refresh")
        self.assertEqual(res.status_code, 202)

    def test_status_endpoint_still_subject_to_timeout(self):
        with (
            patch("app.middleware._is_hot_poll_path", return_value=False),
            patch("api.routers.operations._STATUS_BUDGET_S", 0.05),
            patch("api.routers.operations.get_live_status_fast") as live,
        ):

            def blocking_status(**_kwargs):
                import time

                time.sleep(0.35)
                return {"running": False, "stage": "idle"}

            live.side_effect = blocking_status
            res = self.client.get("/api/operations/status")
        # Handler budget timeout → fallback JSON (200) or middleware cancel (204).
        self.assertIn(res.status_code, (200, 204))
        if res.status_code == 200:
            body = res.json()
            self.assertTrue(body.get("guard") or body.get("reason") == "status_timeout")


if __name__ == "__main__":
    unittest.main()
