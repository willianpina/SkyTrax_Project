"""Pipeline heartbeat validation, stall detection, orphan cleanup, and state reconciliation."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from redis import Redis

from app.observability import record_worker_metric
from app.timezone import operational_timestamp
from worker.orchestration.pipeline_status import PipelineStatus

logger = logging.getLogger(__name__)

REDIS_STATUS_KEY = "skytrax:ops:refresh:status"
REDIS_LOCK_KEY = "skytrax:ops:refresh:lock"
REDIS_WATCHDOG_LOCK_KEY = "skytrax:ops:watchdog:reconcile:lock"

_STATUS_TTL = 14400
_WATCHDOG_LOCK_TTL_S = 25

# ── Tunable thresholds (env) ─────────────────────────────────────────
HEARTBEAT_TIMEOUT_S = int(os.getenv("PIPELINE_HEARTBEAT_TIMEOUT_S", "60"))
HEARTBEAT_FRESH_S = int(os.getenv("PIPELINE_HEARTBEAT_FRESH_S", "45"))
STALE_SOFT_S = int(os.getenv("PIPELINE_STALE_SOFT_S", "90"))
STALL_THRESHOLD_S = int(os.getenv("PIPELINE_STALL_THRESHOLD_S", "180"))
STARTING_ORPHAN_THRESHOLD_S = int(os.getenv("PIPELINE_STARTING_ORPHAN_THRESHOLD_S", "90"))
QUEUED_GRACE_S = int(os.getenv("PIPELINE_QUEUED_GRACE_S", "1800"))
NO_PROGRESS_STALL_S = int(os.getenv("PIPELINE_NO_PROGRESS_THRESHOLD_S", "240"))
STARTING_PROGRESS_MAX = int(os.getenv("PIPELINE_STARTING_PROGRESS_MAX", "5"))

_FINAL_STAGES = frozenset({"fusion", "snapshots"})
_STAGE_HARD_THRESHOLDS = {
    "fusion": int(os.getenv("FUSION_STALE_THRESHOLD_S", "360")),
    "aviation_master": int(os.getenv("AVIATION_MASTER_STALE_THRESHOLD_S", "240")),
}
_FINAL_STAGE_HARD_S = int(os.getenv("PIPELINE_FINAL_STAGE_STALE_S", "420"))


class StallType(str, Enum):
    NONE = "none"
    SOFT = "soft_stall"
    HARD = "hard_stall"
    STARTING_ORPHAN = "starting_orphan"
    NO_PROGRESS = "no_progress"


class ReconcileAction(str, Enum):
    NONE = "none"
    ENRICHED = "enriched"
    SOFT_WARNING = "soft_warning"
    STALLED = "stalled"
    SKIPPED = "skipped"


@dataclass
class PipelineHealthSnapshot:
    operation_id: str
    stage: str
    progress: int
    heartbeat_age_s: int
    no_progress_s: int
    worker_alive: bool
    stall_type: StallType
    pipeline_status: str
    running: bool
    lock_owner: str


def _redis() -> Redis:
    from worker.orchestration.refresh_pipeline import _redis as _r

    return _r()


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def last_activity_timestamp(data: dict[str, Any]) -> datetime | None:
    hb = data.get("heartbeat") or {}
    candidates = [
        data.get("last_heartbeat_at"),
        hb.get("last_heartbeat_at"),
        data.get("updated_at"),
    ]
    best: datetime | None = None
    for raw in candidates:
        ts = _parse_ts(raw if isinstance(raw, str) else None)
        if ts and (best is None or ts > best):
            best = ts
    return best


def heartbeat_age_seconds(data: dict[str, Any], *, now: datetime | None = None) -> int:
    last_ts = last_activity_timestamp(data)
    if not last_ts:
        return 0
    ref = now or datetime.now(timezone.utc)
    return max(0, int((ref - last_ts).total_seconds()))


def no_progress_seconds(data: dict[str, Any], *, now: datetime | None = None) -> int:
    ref = now or datetime.now(timezone.utc)
    progress = int(data.get("progress") or 0)
    last_progress = int(data.get("last_progress") if data.get("last_progress") is not None else progress)
    if progress > last_progress:
        return 0
    raw = data.get("last_progress_at") or data.get("updated_at") or data.get("started_at")
    ts = _parse_ts(raw if isinstance(raw, str) else None)
    if not ts:
        return 0
    return max(0, int((ref - ts).total_seconds()))


def compute_worker_alive(data: dict[str, Any], heartbeat_age_s: int | None = None) -> bool:
    """Worker is alive ONLY when heartbeat is fresh — never derived from running=true."""
    age = heartbeat_age_s if heartbeat_age_s is not None else heartbeat_age_seconds(data)
    alive = age < HEARTBEAT_TIMEOUT_S
    if not alive and data.get("running"):
        logger.info(
            "[WORKER] heartbeat expired worker considered offline op=%s age=%ds threshold=%ds",
            data.get("operation_id"),
            age,
            HEARTBEAT_TIMEOUT_S,
        )
        record_worker_metric("skytrax_worker_timeout_total", 1.0)
    return alive


def _hard_threshold_for_stage(stage: str, pipeline_status: str) -> int:
    if stage in _STAGE_HARD_THRESHOLDS:
        return _STAGE_HARD_THRESHOLDS[stage]
    if stage in _FINAL_STAGES or pipeline_status in (
        PipelineStatus.FINALIZING,
        PipelineStatus.PERSISTING,
    ):
        return _FINAL_STAGE_HARD_S
    return STALL_THRESHOLD_S


def classify_stall(
    data: dict[str, Any],
    *,
    heartbeat_age_s: int,
    no_progress_s: int,
    worker_alive: bool,
) -> StallType:
    stage = str(data.get("stage") or "")
    progress = int(data.get("progress") or 0)
    pipeline_status = str(data.get("pipeline_status") or "")

    if stage == "queued" or pipeline_status == "queued":
        if heartbeat_age_s >= QUEUED_GRACE_S:
            return StallType.STARTING_ORPHAN
        return StallType.NONE

    hard = _hard_threshold_for_stage(stage, pipeline_status)

    if not worker_alive:
        if heartbeat_age_s >= hard:
            return StallType.HARD
        if stage == "starting" and progress <= STARTING_PROGRESS_MAX:
            if heartbeat_age_s >= STARTING_ORPHAN_THRESHOLD_S:
                return StallType.STARTING_ORPHAN
        if heartbeat_age_s > STALE_SOFT_S:
            return StallType.SOFT
        return StallType.NONE

    if stage == "starting" and progress <= STARTING_PROGRESS_MAX:
        if heartbeat_age_s >= STARTING_ORPHAN_THRESHOLD_S:
            return StallType.STARTING_ORPHAN
        if no_progress_s >= STARTING_ORPHAN_THRESHOLD_S:
            return StallType.STARTING_ORPHAN

    if no_progress_s >= NO_PROGRESS_STALL_S:
        return StallType.NO_PROGRESS

    if heartbeat_age_s >= hard:
        return StallType.HARD

    if heartbeat_age_s > STALE_SOFT_S and no_progress_s > NO_PROGRESS_STALL_S // 2:
        return StallType.SOFT

    return StallType.NONE


def build_stall_diagnosis(
    data: dict[str, Any],
    *,
    snapshot: PipelineHealthSnapshot,
    failure_type: str,
    failure_reason: str,
    recovered: bool = False,
) -> dict[str, Any]:
    hb = data.get("heartbeat") or {}
    return {
        "failure_reason": failure_reason,
        "failure_type": failure_type,
        "heartbeat_age": snapshot.heartbeat_age_s,
        "last_stage": snapshot.stage,
        "last_progress": snapshot.progress,
        "stalled_detected_at": operational_timestamp(),
        "worker_last_seen": data.get("last_heartbeat_at") or hb.get("last_heartbeat_at"),
        "no_progress_seconds": snapshot.no_progress_s,
        "worker_alive": snapshot.worker_alive,
        "lock_owner": snapshot.lock_owner or None,
        "recovered": recovered,
        "stall_type": snapshot.stall_type.value,
    }


def evaluate_pipeline_health(
    data: dict[str, Any],
    r: Redis | None = None,
) -> tuple[dict[str, Any], ReconcileAction]:
    """Compute operational truth for a pipeline status blob (in-memory)."""
    out = dict(data)
    if not out.get("running"):
        out["worker_alive"] = False
        return out, ReconcileAction.NONE

    now = datetime.now(timezone.utc)
    hb_age = heartbeat_age_seconds(out, now=now)
    np_s = no_progress_seconds(out, now=now)
    worker_alive = compute_worker_alive(out, hb_age)

    lock_owner = ""
    if r is not None:
        try:
            lock_owner = str(r.get(REDIS_LOCK_KEY) or "")
        except Exception:
            lock_owner = ""

    stall_type = classify_stall(
        out,
        heartbeat_age_s=hb_age,
        no_progress_s=np_s,
        worker_alive=worker_alive,
    )
    stage = str(out.get("stage") or "unknown")
    progress = int(out.get("progress") or 0)
    op_id = str(out.get("operation_id") or "")

    snapshot = PipelineHealthSnapshot(
        operation_id=op_id,
        stage=stage,
        progress=progress,
        heartbeat_age_s=hb_age,
        no_progress_s=np_s,
        worker_alive=worker_alive,
        stall_type=stall_type,
        pipeline_status=str(out.get("pipeline_status") or ""),
        running=bool(out.get("running")),
        lock_owner=lock_owner,
    )

    out["heartbeat_age_s"] = hb_age
    out["stale_seconds"] = hb_age
    out["no_progress_seconds"] = np_s
    out["worker_alive"] = worker_alive
    last_ts = last_activity_timestamp(out)
    if last_ts:
        out["last_heartbeat_at"] = last_ts.isoformat()

    record_worker_metric("skytrax_average_heartbeat_age", float(hb_age))

    # ── Hard stall / orphan ───────────────────────────────────────────
    if stall_type in (StallType.HARD, StallType.STARTING_ORPHAN, StallType.NO_PROGRESS):
        hard_limit = _hard_threshold_for_stage(
            str(out.get("stage") or ""),
            str(out.get("pipeline_status") or ""),
        )
        reason = (
            f"Heartbeat expired ({hb_age}s > {hard_limit}s)"
            if stall_type == StallType.HARD
            else (
                f"Starting orphan: stuck at stage={stage} progress={progress} for {hb_age}s"
                if stall_type == StallType.STARTING_ORPHAN
                else f"No progress for {np_s}s (threshold {NO_PROGRESS_STALL_S}s)"
            )
        )
        logger.warning(
            "[STALL] operation_id=%s heartbeat_age=%d no_progress=%d stage=%s type=%s",
            op_id,
            hb_age,
            np_s,
            stage,
            stall_type.value,
        )
        out["stale"] = True
        out["stale_warning"] = True
        out["running"] = False
        out["stage"] = PipelineStatus.STALLED
        out["pipeline_status"] = PipelineStatus.STALLED
        out["soft_stall"] = False
        out["busy_without_heartbeat"] = False
        out["stall_diagnosis"] = build_stall_diagnosis(
            data,
            snapshot=snapshot,
            failure_type=stall_type.value,
            failure_reason=reason,
        )
        events = list(out.get("events") or [])
        events.append(
            {
                "time": operational_timestamp(),
                "message": f"[STALL] {reason}",
                "operation_id": op_id,
            }
        )
        out["events"] = events
        record_worker_metric("skytrax_pipelines_stalled_total", 1.0)
        if stall_type == StallType.STARTING_ORPHAN:
            record_worker_metric("skytrax_orphan_pipelines_total", 1.0)
        return out, ReconcileAction.STALLED

    # ── Soft stall (heartbeat alive, slow progress) ───────────────────
    if stall_type == StallType.SOFT or hb_age > STALE_SOFT_S:
        out["stale_warning"] = True
        out["soft_stall"] = True
        out["running"] = True
        ps = out.get("pipeline_status")
        if ps not in (
            PipelineStatus.RUNNING_DEGRADED,
            PipelineStatus.FINALIZING,
            PipelineStatus.PERSISTING,
        ):
            out["pipeline_status"] = PipelineStatus.RUNNING_SLOW
        logger.info(
            "[HEARTBEAT] running_slow op=%s heartbeat_age=%d no_progress=%d worker_alive=%s",
            op_id,
            hb_age,
            np_s,
            worker_alive,
        )
        record_worker_metric("skytrax_pipeline_running_slow", 1.0)
        return out, ReconcileAction.SOFT_WARNING

    out.pop("stale_warning", None)
    out.pop("soft_stall", None)
    if hb_age <= HEARTBEAT_FRESH_S:
        out.pop("stale", None)
    return out, ReconcileAction.ENRICHED


def _persist_status(r: Redis, payload: dict[str, Any]) -> None:
    from worker.orchestration.refresh_pipeline import _SafeEncoder

    r.set(REDIS_STATUS_KEY, json.dumps(payload, cls=_SafeEncoder), ex=_STATUS_TTL)


def release_stalled_state(r: Redis | None = None, operation_id: str | None = None) -> dict[str, Any]:
    """Clear locks + lifecycle so a new refresh can be accepted after stall/failure."""
    redis_client = r if r is not None else _redis()
    released: dict[str, Any] = {"released": True, "operation_id": operation_id}

    try:
        redis_client.delete(REDIS_LOCK_KEY)
        redis_client.delete(REDIS_WATCHDOG_LOCK_KEY)
    except Exception:
        pass

    try:
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        mgr = OperationLifecycleManager(redis_client)
        if operation_id:
            mgr.transition(operation_id, "stalled", stall_diagnosis={"recovered": True})
            mgr.clear_terminal(operation_id)
        else:
            active = mgr.get_active_operation()
            if active and active.get("operation_id"):
                op = str(active["operation_id"])
                mgr.transition(op, "stalled")
                mgr.clear_terminal(op)
                released["operation_id"] = op
    except Exception as exc:
        logger.warning("[RECOVERY] release_stalled_state failed: %s", exc)
        released["released"] = False
        released["error"] = str(exc)[:200]

    logger.info("[RECOVERY] stall state released op=%s", released.get("operation_id"))
    return released


def apply_stall_cleanup(r: Redis, data: dict[str, Any]) -> None:
    """Release lock and align lifecycle after stall."""
    op_id = str(data.get("operation_id") or "")
    try:
        r.delete(REDIS_LOCK_KEY)
    except Exception:
        pass
    try:
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        if op_id:
            OperationLifecycleManager(r).transition(
                op_id,
                "stalled",
                stall_diagnosis=data.get("stall_diagnosis"),
            )
            OperationLifecycleManager(r).clear_terminal(op_id)
    except Exception as exc:
        logger.warning("[RECOVERY] lifecycle transition failed op=%s: %s", op_id, exc)

    logger.warning("[RECOVERY] operation_id=%s marked_as=stalled", op_id)
    record_worker_metric("skytrax_recovery_attempts_total", 1.0)


def prepare_accept_path() -> dict[str, Any]:
    """Reconcile zombies and release stale locks before enqueueing a new refresh."""
    summary: dict[str, Any] = {"reconciled": False, "released": False}
    try:
        out = reconcile_pipeline_state(persist=True)
        summary["reconciled"] = True
        summary["reconcile_action"] = str(out.get("action", ""))
        if out.get("action") == ReconcileAction.STALLED:
            summary["released"] = True
            summary["released_operation_id"] = out.get("operation_id")
    except Exception as exc:
        logger.warning("[RECOVERY] prepare_accept_path reconcile failed: %s", exc)
        summary["reconcile_error"] = str(exc)[:200]

    try:
        from worker.orchestration.refresh_pipeline import get_live_status_fast

        live = get_live_status_fast()
        stage = str(live.get("stage") or "")
        ps = str(live.get("pipeline_status") or "")
        if (
            not live.get("running")
            or stage in ("stalled", "failed", "idle")
            or ps == "stalled"
            or not compute_worker_alive(live)
        ):
            rel = release_stalled_state(operation_id=live.get("operation_id"))
            summary["released"] = summary.get("released") or rel.get("released", False)
            summary["released_operation_id"] = rel.get("operation_id") or live.get("operation_id")
    except Exception as exc:
        logger.warning("[RECOVERY] prepare_accept_path release failed: %s", exc)

    return summary


def reconcile_pipeline_state(*, persist: bool = True) -> dict[str, Any]:
    """Detect orphan/zombie pipelines and persist corrected state to Redis."""
    r = _redis()
    acquired = r.set(REDIS_WATCHDOG_LOCK_KEY, "1", nx=True, ex=_WATCHDOG_LOCK_TTL_S)
    if not acquired:
        logger.debug("[RECOVERY] reconcile skipped — watchdog lock held")
        return {"action": ReconcileAction.SKIPPED, "reason": "watchdog_locked"}

    try:
        raw = r.get(REDIS_STATUS_KEY)
        if not raw:
            return {"action": ReconcileAction.NONE, "reason": "no_active_status"}

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"action": ReconcileAction.NONE, "reason": "invalid_status_json"}

        if not isinstance(data, dict):
            return {"action": ReconcileAction.NONE, "reason": "invalid_status_shape"}

        if not data.get("running"):
            enriched, _ = evaluate_pipeline_health(data, r)
            return {"action": ReconcileAction.NONE, "operation_id": data.get("operation_id")}

        enriched, action = evaluate_pipeline_health(data, r)

        if action == ReconcileAction.STALLED and persist:
            _persist_status(r, enriched)
            apply_stall_cleanup(r, enriched)
            return {
                "action": action,
                "operation_id": enriched.get("operation_id"),
                "stall_diagnosis": enriched.get("stall_diagnosis"),
                "persisted": True,
            }

        if action in (ReconcileAction.SOFT_WARNING, ReconcileAction.ENRICHED) and persist:
            _persist_status(r, enriched)

        return {
            "action": action,
            "operation_id": enriched.get("operation_id"),
            "worker_alive": enriched.get("worker_alive"),
            "pipeline_status": enriched.get("pipeline_status"),
            "heartbeat_age_s": enriched.get("heartbeat_age_s"),
            "persisted": persist and action != ReconcileAction.NONE,
        }
    finally:
        try:
            r.delete(REDIS_WATCHDOG_LOCK_KEY)
        except Exception:
            pass


def enrich_live_status(data: dict[str, Any], r: Redis | None = None) -> dict[str, Any]:
    """Public entry: apply heartbeat/stall truth to status dict (used by GET /status)."""
    redis_client = r if r is not None else _redis()
    enriched, action = evaluate_pipeline_health(data, redis_client)

    if action == ReconcileAction.STALLED:
        try:
            if redis_client.set(REDIS_WATCHDOG_LOCK_KEY, "1", nx=True, ex=_WATCHDOG_LOCK_TTL_S):
                try:
                    _persist_status(redis_client, enriched)
                    apply_stall_cleanup(redis_client, enriched)
                finally:
                    redis_client.delete(REDIS_WATCHDOG_LOCK_KEY)
        except Exception as exc:
            logger.warning("[RECOVERY] persist on read failed: %s", exc)

    return enriched
