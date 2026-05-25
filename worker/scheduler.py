from __future__ import annotations

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
    run_data_quality_scan,
    run_forecasting_job,
    schedule_priority_crawls,
)

logger = getLogger(__name__)


def enqueue(job_fn, *args, **kwargs) -> None:
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue("default", connection=connection)
    queue.enqueue(
        job_fn,
        *args,
        **kwargs,
        job_timeout=3600,
        result_ttl=86400,
        retry=Retry(max=settings.job_retry_attempts),
    )
    logger.info("scheduler_enqueued", extra={"job": getattr(job_fn, "__name__", str(job_fn)), "args": args})


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)

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
    return scheduler


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.scheduler_enabled:
        logger.warning("scheduler_disabled")
        return
    scheduler = build_scheduler()
    logger.info("scheduler_started", extra={"timezone": settings.scheduler_timezone})
    scheduler.start()


if __name__ == "__main__":
    main()
