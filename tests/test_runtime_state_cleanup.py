"""Tests for stale degraded/runtime state cleanup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.runtime_state import remove_false_degraded_events, runtime_state_reset


def test_remove_false_degraded_events_updates_memory_state():
    seed = {
        "degraded_history": [
            {"stage": "aviation_master", "operation_id": "op1", "error": "stale"},
            {"stage": "fusion", "operation_id": "op1", "error": "real"},
        ]
    }
    with patch("app.runtime_state._load", return_value=seed):
        with patch("app.runtime_state.merge_state") as mock_merge:
            with patch("app.runtime_state._redis", return_value=None):
                removed = remove_false_degraded_events(operation_id="op1", stage="aviation_master")
    assert removed == 1
    mock_merge.assert_called_once()


def test_runtime_state_reset_cleans_previous_operation_payload():
    redis_mock = MagicMock()
    redis_mock.get.return_value = (
        '{"operation_id":"old-op","events":[{"message":"old"}],"failed_stages":["aviation_master"],'
        '"stage_results":{"aviation_master":{"error":"stale"}},"pipeline_status":"completed_degraded",'
        '"running":false,"stage":"completed_degraded"}'
    )
    with patch("app.runtime_state._redis", return_value=redis_mock):
        with patch("app.runtime_state._load", return_value={}):
            with patch("app.runtime_state._save"):
                result = runtime_state_reset(operation_id="new-op", clear_degraded_history=False)
    assert result["status"] == "ok"
    assert redis_mock.set.call_count == 1
