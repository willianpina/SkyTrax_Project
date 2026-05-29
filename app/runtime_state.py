"""Shared operational runtime state — Redis-backed with in-process fallback."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

RUNTIME_KEY = "skytrax:runtime:state"
DEGRADED_HISTORY_KEY = "skytrax:runtime:degraded_history"
TTL_S = 86400

# Stages blocked when schema groups are incomplete
STAGE_SCHEMA_DEPENDENCIES: dict[str, list[str]] = {
    "metadata": ["metadata"],
    "knowledge_graph": ["knowledge_graph"],
    "forecasting": ["forecasting"],
    "anomalies": ["anomalies"],
    "semantic": ["semantic"],
}

_memory_state: dict[str, Any] = {}


def _redis():
    try:
        from redis import Redis
        from app.config import get_settings

        return Redis.from_url(get_settings().redis_url, decode_responses=True)
    except Exception:
        return None


def _load() -> dict[str, Any]:
    r = _redis()
    if r:
        try:
            raw = r.get(RUNTIME_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("runtime_state_load_failed: %s", exc)
    return dict(_memory_state)


def _save(state: dict[str, Any]) -> None:
    _memory_state.clear()
    _memory_state.update(state)
    r = _redis()
    if r:
        try:
            r.set(RUNTIME_KEY, json.dumps(state), ex=TTL_S)
        except Exception as exc:
            logger.debug("runtime_state_save_failed: %s", exc)


def get_state() -> dict[str, Any]:
    return _load()


def merge_state(**updates: Any) -> dict[str, Any]:
    state = _load()
    state.update(updates)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(state)
    return state


def set_startup_report(report: dict[str, Any]) -> None:
    merge_state(startup_report=report, startup_at=datetime.now(timezone.utc).isoformat())


def set_schema_drift(
    active: bool,
    missing_tables: list[str] | None = None,
    semantic_blocked: list[str] | None = None,
) -> None:
    table_blocked = _compute_blocked_stages(missing_tables or []) if active else []
    semantic = semantic_blocked or []
    merge_state(
        schema_drift=active or bool(semantic),
        missing_tables=missing_tables or [],
        semantic_blocked_stages=semantic,
        blocked_stages=sorted(set(table_blocked + semantic)),
    )
    if active:
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_schema_drift", 1.0)
        except Exception:
            pass


def _compute_blocked_stages(missing_tables: list[str]) -> list[str]:
    from database.schema_health import REQUIRED_TABLES

    blocked: list[str] = []
    for stage, groups in STAGE_SCHEMA_DEPENDENCIES.items():
        for group in groups:
            group_tables = REQUIRED_TABLES.get(group, [])
            if any(t in missing_tables for t in group_tables):
                blocked.append(stage)
                break
    return sorted(set(blocked))


def is_stage_blocked(stage: str) -> bool:
    state = _load()
    blocked = set(state.get("blocked_stages") or [])
    blocked.update(state.get("semantic_blocked_stages") or [])
    return stage in blocked


def reconcile_schema_blocks(engine: Any) -> dict[str, Any]:
    """Re-sync Redis/in-memory stage blocks from live DB schema (clears stale metadata blocks)."""
    from database.runtime_schema import reconcile_runtime_with_physical
    from database.schema_health import validate_schema

    reconcile_runtime_with_physical(engine)
    report = validate_schema(engine, auto_migrate_dev=False)
    semantic = report.get("semantic_blocked_stages") or []
    if report.get("healthy"):
        set_schema_drift(False, [], semantic)
        logger.info(
            "[SCHEMA] Runtime blocks reconciled — healthy=true blocked_stages=%s",
            _load().get("blocked_stages", []),
        )
    else:
        set_schema_drift(
            True,
            report.get("missing_tables", []),
            semantic,
        )
        logger.warning(
            "[SCHEMA] Runtime blocks reconciled — degraded missing=%s semantic=%s",
            report.get("missing_tables", [])[:8],
            semantic,
        )
    return report


def activate_forecast_safe_mode(reason: str = "native_crash") -> None:
    """Enable safe forecasting for this process and persist flag."""
    os.environ["FORECAST_SAFE_MODE"] = "1"
    state = _load()
    crashes = int(state.get("native_crash_count", 0)) + 1
    merge_state(
        forecast_safe_mode_active=True,
        forecast_safe_mode_reason=reason,
        native_crash_count=crashes,
        last_native_crash_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        from app.observability import record_worker_metric

        record_worker_metric("skytrax_native_safe_mode", 1.0)
        record_worker_metric("skytrax_forecast_native_crash", 1.0)
    except Exception:
        pass
    logger.warning("[FORECAST_NATIVE] Safe mode activated reason=%s crashes=%d", reason, crashes)


def is_forecast_safe_mode() -> bool:
    if os.getenv("FORECAST_SAFE_MODE", "0").lower() in ("1", "true", "yes"):
        return True
    return bool(_load().get("forecast_safe_mode_active"))


def record_subprocess_crash(stage: str = "forecasting") -> None:
    state = _load()
    now = time.time()
    window = [t for t in state.get("crash_timestamps", []) if now - t < 300]
    window.append(now)
    cooldown_until = state.get("subprocess_cooldown_until", 0)
    if len(window) >= 3:
        cooldown_until = now + 600
        logger.warning("[WORKHORSE_CRASH] Crash loop detected — cooldown 600s stage=%s", stage)
    merge_state(crash_timestamps=window, subprocess_cooldown_until=cooldown_until)


def is_subprocess_cooldown_active() -> bool:
    return time.time() < float(_load().get("subprocess_cooldown_until", 0))


def record_degraded_stage(
    stage: str,
    *,
    operation_id: str = "",
    error: str = "",
    soft: bool = True,
) -> None:
    entry = {
        "stage": stage,
        "operation_id": operation_id,
        "error": error[:300],
        "soft": soft,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    r = _redis()
    if r:
        try:
            r.lpush(DEGRADED_HISTORY_KEY, json.dumps(entry))
            r.ltrim(DEGRADED_HISTORY_KEY, 0, 49)
            r.expire(DEGRADED_HISTORY_KEY, TTL_S)
        except Exception:
            pass
    history = _load().get("degraded_history", [])
    history = [entry] + history[:49]
    merge_state(degraded_history=history)


def get_degraded_history(limit: int = 20) -> list[dict]:
    r = _redis()
    if r:
        try:
            rows = r.lrange(DEGRADED_HISTORY_KEY, 0, limit - 1)
            return [json.loads(x) for x in rows]
        except Exception:
            pass
    return (_load().get("degraded_history") or [])[:limit]


def remove_false_degraded_events(*, operation_id: str, stage: str = "aviation_master") -> int:
    """Drop stale degraded entries for an operation/stage from Redis + memory."""
    removed = 0
    state_history = _load().get("degraded_history", [])
    filtered = []
    for entry in state_history:
        if entry.get("operation_id") == operation_id and entry.get("stage") == stage:
            removed += 1
            continue
        filtered.append(entry)
    if removed:
        merge_state(degraded_history=filtered[:50])

    r = _redis()
    if r:
        try:
            rows = r.lrange(DEGRADED_HISTORY_KEY, 0, 49)
            keep: list[str] = []
            for raw in rows:
                try:
                    parsed = json.loads(raw)
                except Exception:
                    keep.append(raw)
                    continue
                if parsed.get("operation_id") == operation_id and parsed.get("stage") == stage:
                    continue
                keep.append(raw)
            pipe = r.pipeline()
            pipe.delete(DEGRADED_HISTORY_KEY)
            for item in reversed(keep[:50]):
                pipe.lpush(DEGRADED_HISTORY_KEY, item)
            pipe.expire(DEGRADED_HISTORY_KEY, TTL_S)
            pipe.execute()
        except Exception:
            pass
    return removed


def runtime_state_reset(*, operation_id: str = "", clear_degraded_history: bool = True) -> dict[str, Any]:
    """Reset stale operational runtime residue between runs."""
    redis_status_key = "skytrax:ops:refresh:status"

    r = _redis()
    if r:
        try:
            raw = r.get(redis_status_key)
            if raw:
                payload = json.loads(raw)
                current_op = payload.get("operation_id", "")
                if operation_id and current_op and current_op != operation_id:
                    payload["events"] = []
                    payload["failed_stages"] = []
                    payload["stage_results"] = {}
                    payload["pipeline_status"] = "idle"
                    payload["running"] = False
                    payload["stage"] = "idle"
                    r.set(redis_status_key, json.dumps(payload), ex=TTL_S)
        except Exception:
            pass

    if clear_degraded_history and operation_id:
        removed = remove_false_degraded_events(operation_id=operation_id)
    else:
        removed = 0

    state = _load()
    state.pop("last_degraded_stage", None)
    state.pop("last_degraded_error", None)
    _save(state)
    logger.info(
        "[SOFT_FAILURE_CLEANUP] runtime_state_reset op=%s removed=%d",
        operation_id,
        removed,
    )
    return {"status": "ok", "removed_degraded_events": removed}
