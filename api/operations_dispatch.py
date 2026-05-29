"""Non-blocking operational refresh dispatch (RQ enqueue only — no inline pipeline)."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.observability import record_worker_metric

logger = logging.getLogger(__name__)

_REDIS_CONNECT_TIMEOUT_S = 2.0


def get_redis_and_queue():
    """Redis + RQ queue with bounded socket timeouts (fail fast on accept path)."""
    from redis import Redis
    from rq import Queue

    settings = get_settings()
    conn = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_S,
        socket_timeout=_REDIS_CONNECT_TIMEOUT_S,
    )
    conn.ping()
    return conn, Queue("default", connection=conn)


def queue_depth() -> int:
    try:
        _, queue = get_redis_and_queue()
        return int(queue.count)
    except Exception:
        return -1


def enqueue_operational_refresh(
    operation_id: str,
    airline_slug: str | None,
    triggered_by: str,
) -> dict[str, Any]:
    from rq import Retry
    from worker.jobs import run_operational_refresh

    started = time.perf_counter()
    conn, queue = get_redis_and_queue()
    logger.info(
        "[QUEUE_DISPATCH] enqueue op=%s queue=%s depth=%s",
        operation_id,
        queue.name,
        queue.count,
    )

    job = queue.enqueue(
        run_operational_refresh,
        kwargs={
            "operation_id": operation_id,
            "airline_slug": airline_slug,
            "triggered_by": triggered_by,
        },
        job_timeout=14400,
        result_ttl=86400,
        retry=Retry(max=3, interval=[10, 30, 60]),
        meta={"operation_id": operation_id},
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    record_worker_metric("skytrax_refresh_dispatch_latency", latency_ms)
    record_worker_metric("skytrax_refresh_queue_depth", float(queue.count))
    logger.info("[ASYNC_REFRESH] job_id=%s op=%s latency_ms=%.1f", job.id, operation_id, latency_ms)
    return {"job_id": job.id, "queue": queue.name, "queue_depth": queue.count}


def enqueue_aviation_sync(operation_id: str, triggered_by: str) -> dict[str, Any]:
    from rq import Retry
    from worker.jobs import run_aviation_sync

    conn, queue = get_redis_and_queue()
    job = queue.enqueue(
        run_aviation_sync,
        kwargs={"operation_id": operation_id, "triggered_by": triggered_by},
        job_timeout=3600,
        result_ttl=86400,
        retry=Retry(max=2, interval=[10, 30]),
        meta={"operation_id": operation_id},
    )
    record_worker_metric("skytrax_refresh_queue_depth", float(queue.count))
    return {
        "job_id": job.id,
        "queue": queue.name,
        "queue_depth": queue.count,
        "pipeline_type": "aviation",
    }


def accept_and_dispatch_refresh(
    *,
    airline_slug: str | None = None,
    triggered_by: str = "manual",
    pipeline_type: str = "full",
    force: bool = False,
) -> dict[str, Any]:
    """Synchronous accept+dispatch for use inside asyncio.to_thread (bounded, no pipeline)."""
    from worker.orchestration.operation_lifecycle import OperationLifecycleManager
    from worker.orchestration.pipeline_watchdog import prepare_accept_path, release_stalled_state
    from worker.orchestration.refresh_pipeline import get_live_status_fast, set_initial_status

    if force:
        live = get_live_status_fast()
        release_stalled_state(operation_id=live.get("operation_id"))
    else:
        prepare_accept_path()

    operation_id = str(uuid4())[:12]
    lifecycle = OperationLifecycleManager()

    accept = lifecycle.accept_refresh(
        operation_id=operation_id,
        triggered_by=triggered_by,
        pipeline_type=pipeline_type,
    )
    if not accept.get("accepted"):
        reason = accept.get("reason", "already_running")
        active = accept.get("active_operation") or {}
        record_worker_metric("skytrax_concurrent_refresh_prevented", 1.0)
        return {
            "http_status": 409,
            "body": {
                "status": "already_running",
                "reason": reason,
                "running": True,
                "operation_id": active.get("operation_id", ""),
                "lifecycle_state": active.get("lifecycle_state"),
                "queued": False,
            },
        }

    set_initial_status(operation_id, triggered_by)

    try:
        if pipeline_type == "aviation":
            rq_result = enqueue_aviation_sync(operation_id, triggered_by)
        else:
            rq_result = enqueue_operational_refresh(operation_id, airline_slug, triggered_by)
        logger.info("[PIPELINE_ACCEPTED] op=%s queued=true", operation_id)
        return {
            "http_status": 202,
            "body": {
                "status": "accepted",
                "running": True,
                "queued": True,
                "operation_id": operation_id,
                "lifecycle_state": "queued",
                **rq_result,
            },
        }
    except Exception as exc:
        logger.exception("[QUEUE_DISPATCH] enqueue failed op=%s: %s", operation_id, exc)
        lifecycle.mark_dispatch_failed(operation_id, str(exc))
        return {
            "http_status": 503,
            "body": {
                "status": "dispatch_failed",
                "queued": False,
                "operation_id": operation_id,
                "running": False,
                "detail": str(exc)[:300],
            },
        }
