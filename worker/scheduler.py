from __future__ import annotations

import os
import time
from logging import getLogger

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from redis import Redis
from rq import Queue, Retry

from app.config import get_settings
from app.logging_config import configure_logging
from worker.jobs import (
    enrich_pending_reviews,
    generate_executive_insights,
    generate_metric_snapshots,
    operational_cleanup,
    persist_reputation_scores,
    refresh_semantic_clusters,
    run_anomaly_detection_job,
    run_aviation_bootstrap,
    run_aviation_coverage_audit,
    run_data_quality_scan,
    run_forecasting_job,
    run_pipeline_watchdog,
    schedule_priority_crawls,
)

logger = getLogger(__name__)


def _safe_log(level: str, event: str, **fields) -> None:
    """Emit a structured log that never raises."""
    try:
        getattr(logger, level)(event, extra=fields)
    except Exception as exc:
        print(f"[SCHEDULER_LOG_ERROR] {event} | {fields} | {exc}")


def enqueue(job_fn, *args, **kwargs) -> None:
    job_name = getattr(job_fn, "__name__", str(job_fn))
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue("default", connection=connection)

    _safe_log("info", "scheduler_enqueuing", job_name=job_name, job_args=str(args), queue_name=queue.name)

    t0 = time.monotonic()
    try:
        queue.enqueue(
            job_fn,
            *args,
            **kwargs,
            job_timeout=3600,
            result_ttl=86400,
            retry=Retry(max=settings.job_retry_attempts),
        )
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        _safe_log(
            "info",
            "scheduler_enqueued",
            job_name=job_name,
            job_args=str(args),
            queue_name=queue.name,
            enqueue_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        _safe_log(
            "error",
            "scheduler_enqueue_failed",
            job_name=job_name,
            job_args=str(args),
            error_type=type(exc).__name__,
            error_detail=str(exc)[:300],
            enqueue_ms=elapsed_ms,
        )
        raise


def _on_job_missed(event) -> None:
    _safe_log(
        "warning",
        "scheduler_job_missed",
        job_id=event.job_id,
        scheduled_run_time=str(getattr(event, "scheduled_run_time", "")),
    )


def _on_job_error(event) -> None:
    _safe_log(
        "error",
        "scheduler_job_error",
        job_id=event.job_id,
        error_detail=str(getattr(event, "exception", ""))[:300],
    )


def _on_job_executed(event) -> None:
    _safe_log(
        "info",
        "scheduler_job_executed",
        job_id=event.job_id,
        scheduled_run_time=str(getattr(event, "scheduled_run_time", "")),
    )


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(
        timezone=settings.scheduler_timezone,
        job_defaults={
            "misfire_grace_time": 300,
            "max_instances": 1,
            "coalesce": True,
        },
    )

    from apscheduler.events import EVENT_JOB_MISSED, EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)

    scheduler.add_job(
        lambda: enqueue(schedule_priority_crawls),
        IntervalTrigger(hours=settings.crawl_interval_hours),
        id="priority_crawls",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(enrich_pending_reviews, 300),
        IntervalTrigger(minutes=settings.nlp_interval_minutes),
        id="nlp_enrichment",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(generate_metric_snapshots, "hourly"),
        IntervalTrigger(minutes=settings.snapshot_hourly_minutes),
        id="snapshot_hourly",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(generate_metric_snapshots, "daily"),
        CronTrigger(hour=settings.snapshot_daily_hour, minute=0),
        id="snapshot_daily",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(generate_metric_snapshots, "weekly"),
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="snapshot_weekly",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(generate_executive_insights),
        IntervalTrigger(hours=settings.insights_interval_hours),
        id="executive_insights",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(persist_reputation_scores),
        IntervalTrigger(hours=1),
        id="reputation_scores",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(refresh_semantic_clusters),
        IntervalTrigger(hours=12),
        id="semantic_clusters",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_data_quality_scan),
        IntervalTrigger(hours=6),
        id="data_quality",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(operational_cleanup, 90),
        IntervalTrigger(hours=settings.cleanup_interval_hours),
        id="operational_cleanup",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_forecasting_job),
        IntervalTrigger(hours=settings.forecast_interval_hours),
        id="forecasting",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_anomaly_detection_job),
        IntervalTrigger(hours=settings.anomaly_interval_hours),
        id="anomaly_detection",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_aviation_bootstrap),
        CronTrigger(day_of_week="mon", hour=4, minute=0),
        id="aviation_bootstrap",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_aviation_coverage_audit),
        IntervalTrigger(hours=12),
        id="aviation_coverage_audit",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: enqueue(run_pipeline_watchdog),
        IntervalTrigger(seconds=int(os.getenv("PIPELINE_WATCHDOG_INTERVAL_S", "60"))),
        id="pipeline_watchdog",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.scheduler_enabled:
        _safe_log("warning", "scheduler_disabled")
        return
    scheduler = build_scheduler()
    job_ids = [j.id for j in scheduler.get_jobs()]
    _safe_log(
        "info",
        "scheduler_started",
        timezone=settings.scheduler_timezone,
        jobs_registered=len(job_ids),
        job_ids=str(job_ids),
    )
    scheduler.start()


if __name__ == "__main__":
    main()
