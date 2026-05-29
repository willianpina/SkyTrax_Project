"""Distributed operation lifecycle governance for async pipeline refresh."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from redis import Redis

from app.config import get_settings
from app.observability import record_worker_metric
from app.timezone import operational_timestamp

logger = logging.getLogger(__name__)

REDIS_OPERATION_KEY = "skytrax:ops:refresh:operation"
REDIS_DISPATCH_LOCK_KEY = "skytrax:ops:refresh:dispatch:lock"

OPERATION_TTL_S = 14400
DISPATCH_LOCK_TTL_S = 8

TERMINAL_LIFECYCLE_STATES = frozenset(
    {
        "completed",
        "completed_degraded",
        "failed",
        "cancelled",
        "stalled",
    }
)

ACTIVE_LIFECYCLE_STATES = frozenset(
    {
        "queued",
        "starting",
        "running",
        "running_slow",
        "finalizing",
        "recovering",
    }
)

LIFECYCLE_STATES = TERMINAL_LIFECYCLE_STATES | ACTIVE_LIFECYCLE_STATES

_REDIS_SOCKET_TIMEOUT_S = 2.0


def _redis() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=_REDIS_SOCKET_TIMEOUT_S,
        socket_timeout=_REDIS_SOCKET_TIMEOUT_S,
    )


def lifecycle_from_stage(stage: str | None, pipeline_status: str | None = None) -> str | None:
    """Map pipeline stage / status labels to lifecycle states."""
    ps = (pipeline_status or "").strip()
    st = (stage or "").strip()

    if ps in ACTIVE_LIFECYCLE_STATES | TERMINAL_LIFECYCLE_STATES:
        return ps
    if st in TERMINAL_LIFECYCLE_STATES:
        return st
    if st in ("finalizing", "persisting"):
        return "finalizing"
    if st == "stalled":
        return "stalled"
    if st == "failed":
        return "failed"
    if ps == "stalled":
        return "stalled"
    if ps == "recovering":
        return "recovering"
    if st in ("idle", "", None):
        return None
    if st == "starting":
        return "starting"
    if st in ("running_slow", "busy_without_heartbeat"):
        return "running_slow"
    if st and st not in ("idle",):
        return "running"
    return None


class OperationLifecycleManager:
    """Redis-backed lifecycle for refresh operations (accept path + worker transitions)."""

    def __init__(self, redis_client: Redis | None = None) -> None:
        self._redis = redis_client

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = _redis()
        return self._redis

    def get_active_operation(self) -> dict[str, Any] | None:
        try:
            raw = self.redis.get(REDIS_OPERATION_KEY)
            if not raw:
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            state = data.get("lifecycle_state") or data.get("state")
            if state in TERMINAL_LIFECYCLE_STATES:
                return None
            return data
        except Exception as exc:
            logger.warning("[PIPELINE_ORCHESTRATION] active operation read failed: %s", exc)
            return None

    def is_active(self) -> bool:
        return self.get_active_operation() is not None

    def try_acquire_dispatch_lock(self) -> bool:
        try:
            acquired = self.redis.set(
                REDIS_DISPATCH_LOCK_KEY,
                "1",
                nx=True,
                ex=DISPATCH_LOCK_TTL_S,
            )
            if not acquired:
                record_worker_metric("skytrax_blocked_refresh_attempts", 1.0)
            return bool(acquired)
        except Exception as exc:
            logger.warning("[PIPELINE_ORCHESTRATION] dispatch lock failed: %s", exc)
            return True

    def release_dispatch_lock(self) -> None:
        try:
            self.redis.delete(REDIS_DISPATCH_LOCK_KEY)
        except Exception:
            pass

    def create_queued(
        self,
        operation_id: str,
        *,
        triggered_by: str = "manual",
        pipeline_type: str = "full",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        payload = {
            "operation_id": operation_id,
            "lifecycle_state": "queued",
            "state": "queued",
            "pipeline_type": pipeline_type,
            "triggered_by": triggered_by,
            "queued_at": operational_timestamp(),
            "updated_at": operational_timestamp(),
        }
        self.redis.set(REDIS_OPERATION_KEY, json.dumps(payload), ex=OPERATION_TTL_S)
        record_worker_metric(
            "skytrax_refresh_dispatch_latency",
            (time.perf_counter() - started) * 1000.0,
        )
        logger.info("[PIPELINE_ACCEPTED] op=%s type=%s trigger=%s", operation_id, pipeline_type, triggered_by)
        return payload

    def transition(self, operation_id: str, lifecycle_state: str, **extra: Any) -> None:
        if lifecycle_state not in LIFECYCLE_STATES:
            return
        try:
            raw = self.redis.get(REDIS_OPERATION_KEY)
            payload: dict[str, Any] = {}
            if raw:
                payload = json.loads(raw)
            if payload.get("operation_id") and payload.get("operation_id") != operation_id:
                return
            payload["operation_id"] = operation_id
            payload["lifecycle_state"] = lifecycle_state
            payload["state"] = lifecycle_state
            payload["updated_at"] = operational_timestamp()
            payload.update(extra)
            self.redis.set(REDIS_OPERATION_KEY, json.dumps(payload), ex=OPERATION_TTL_S)
            logger.info(
                "[PIPELINE_ORCHESTRATION] transition op=%s state=%s",
                operation_id,
                lifecycle_state,
            )
        except Exception as exc:
            logger.warning("[PIPELINE_ORCHESTRATION] transition failed: %s", exc)

    def mark_dispatch_failed(self, operation_id: str, error: str) -> None:
        self.transition(operation_id, "failed", dispatch_error=error[:300], queued=False)

    def clear_terminal(self, operation_id: str) -> None:
        try:
            raw = self.redis.get(REDIS_OPERATION_KEY)
            if not raw:
                return
            data = json.loads(raw)
            if data.get("operation_id") == operation_id:
                self.redis.delete(REDIS_OPERATION_KEY)
        except Exception:
            pass

    def accept_refresh(
        self,
        *,
        operation_id: str,
        triggered_by: str,
        pipeline_type: str = "full",
    ) -> dict[str, Any]:
        """Fast idempotent accept: lock → active check → persist queued."""
        if not self.try_acquire_dispatch_lock():
            active = self.get_active_operation()
            record_worker_metric("skytrax_concurrent_refresh_prevented", 1.0)
            return {
                "accepted": False,
                "reason": "dispatch_locked",
                "active_operation": active,
            }

        try:
            active = self.get_active_operation()
            if active:
                record_worker_metric("skytrax_concurrent_refresh_prevented", 1.0)
                return {
                    "accepted": False,
                    "reason": "already_running",
                    "active_operation": active,
                }

            op = self.create_queued(
                operation_id,
                triggered_by=triggered_by,
                pipeline_type=pipeline_type,
            )
            return {"accepted": True, "operation": op}
        finally:
            self.release_dispatch_lock()
