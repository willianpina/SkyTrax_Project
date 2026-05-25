from __future__ import annotations

import subprocess
import time
from datetime import datetime, timedelta, timezone
from logging import getLogger

from redis import Redis
from rq import Queue, Retry

from analytics.anomaly import AnomalyDetectionService
from analytics.data_quality import DataQualityMonitor
from analytics.forecasting import TrendForecastingService
from analytics.insights_engine import ExecutiveInsightEngine
from analytics.intelligence import ReputationService
from analytics.semantic_ops import SemanticClusterService
from analytics.snapshots import SnapshotService
from app.config import get_settings
from app.observability import record_worker_metric
from database.models import NLPResult, Review, SpiderRun
from database.session import SessionLocal
from nlp.pipeline import ReviewNLPPipeline
from nlp.topics import TopicModelingService
from app.alerting import emit_alert
from worker.job_lock import acquire_job_lock, release_job_lock

logger = getLogger(__name__)


def _with_lock(job_name: str, fn, *args, **kwargs):
    settings = get_settings()
    if not acquire_job_lock(job_name, settings.job_overlap_lock_minutes):
        return {"skipped": True, "reason": "overlap"}
    try:
        result = fn(*args, **kwargs)
        release_job_lock(job_name, success=True)
        return result
    except Exception as exc:
        release_job_lock(job_name, success=False, error=str(exc))
        emit_alert("job_failed", {"job_name": job_name, "error": str(exc)}, severity="critical")
        logger.exception("job_failed", extra={"job_name": job_name})
        raise


def run_scrapy_airlinequality(airline_slug: str | None = None, max_pages: int = 3, use_playwright: bool = False) -> dict:
    """RQ job: execute Scrapy spider for one or all configured airlines."""
    job_name = f"crawl:{airline_slug or 'all'}"
    return _with_lock(job_name, _run_scrapy, airline_slug, max_pages, use_playwright)


def _run_scrapy(airline_slug: str | None, max_pages: int, use_playwright: bool) -> dict:
    started_at = time.perf_counter()
    command = [
        "scrapy",
        "crawl",
        "airlinequality_reviews",
        "-a",
        f"max_pages={max_pages}",
        "-a",
        f"use_playwright={str(use_playwright).lower()}",
    ]
    if airline_slug:
        command.extend(["-a", f"airline={airline_slug}"])
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    duration = time.perf_counter() - started_at
    record_worker_metric("skytrax_worker_last_scrapy_duration_seconds", duration)
    success = result.returncode == 0
    record_worker_metric("skytrax_worker_last_scrapy_success", 1.0 if success else 0.0)
    record_worker_metric("skytrax_spider_runs_total", 1.0)
    if not success:
        emit_alert("crawl_failure", {"airline": airline_slug, "returncode": result.returncode}, severity="critical")
    logger.info(
        "scrapy_job_finished",
        extra={"returncode": result.returncode, "airline": airline_slug, "stderr": result.stderr[-2000:]},
    )
    return {"returncode": result.returncode, "stdout_tail": result.stdout[-2000:], "stderr_tail": result.stderr[-2000:]}


def schedule_priority_crawls() -> dict:
    """Enqueue crawls for priority airlines with configurable max_pages."""
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue("default", connection=connection)
    slugs = [slug.strip() for slug in settings.priority_airlines.split(",") if slug.strip()]
    enqueued = []
    for index, slug in enumerate(slugs):
        job = queue.enqueue(
            run_scrapy_airlinequality,
            airline_slug=slug,
            max_pages=settings.crawl_max_pages,
            job_timeout=3600,
            result_ttl=86400,
            retry=Retry(max=settings.job_retry_attempts),
            meta={"priority": index, "airline_slug": slug},
        )
        enqueued.append({"slug": slug, "job_id": job.id, "priority": index})
    record_worker_metric("skytrax_crawl_jobs_enqueued", float(len(enqueued)))
    return {"enqueued": enqueued}


def enrich_pending_reviews(limit: int = 250) -> dict:
    """RQ job: run NLP enrichment for reviews without NLP results."""
    return _with_lock("nlp:enrich", _enrich_pending, limit)


def _enrich_pending(limit: int) -> dict:
    started_at = time.perf_counter()
    pipeline = ReviewNLPPipeline()
    session = SessionLocal()
    try:
        rows = (
            session.query(Review)
            .outerjoin(NLPResult)
            .filter(NLPResult.id.is_(None))
            .order_by(Review.created_at.asc())
            .limit(limit)
            .all()
        )
        for review in rows:
            analysis = pipeline.analyze(review.text)
            session.add(
                NLPResult(
                    review_id=review.id,
                    cleaned_text=analysis.cleaned_text,
                    sentiment_label=analysis.sentiment_label,
                    sentiment_score=analysis.sentiment_score,
                    topics=analysis.topics,
                    entities=analysis.entities,
                    embedding=analysis.embedding,
                    model_versions=analysis.model_versions,
                )
            )
        session.commit()
        snapshots = TopicModelingService(session).refresh_snapshots()
        duration = time.perf_counter() - started_at
        record_worker_metric("skytrax_worker_last_nlp_duration_seconds", duration)
        record_worker_metric("skytrax_worker_last_nlp_reviews_processed", float(len(rows)))
        record_worker_metric("skytrax_nlp_reviews_enriched_total", float(len(rows)))
        return {"enriched": len(rows), "topic_snapshots": snapshots}
    finally:
        session.close()


def generate_metric_snapshots(snapshot_type: str = "hourly") -> dict:
    return _with_lock(f"snapshot:{snapshot_type}", _generate_snapshots, snapshot_type)


def _generate_snapshots(snapshot_type: str) -> dict:
    session = SessionLocal()
    try:
        result = SnapshotService(session).generate(snapshot_type)
        record_worker_metric("skytrax_snapshots_created_total", float(result.get("created", 0)))
        return result
    finally:
        session.close()


def generate_executive_insights() -> dict:
    return _with_lock("insights:generate", _generate_insights)


def _generate_insights() -> dict:
    session = SessionLocal()
    try:
        result = ExecutiveInsightEngine(session).generate_and_persist()
        record_worker_metric("skytrax_insights_generated_total", float(result.get("insights_created", 0)))
        return result
    finally:
        session.close()


def persist_reputation_scores() -> dict:
    return _with_lock("reputation:persist", _persist_reputation)


def _persist_reputation() -> dict:
    session = SessionLocal()
    try:
        count = ReputationService(session).persist_scores()
        record_worker_metric("skytrax_reputation_scores_persisted", float(count))
        return {"airlines_persisted": count}
    finally:
        session.close()


def refresh_semantic_clusters() -> dict:
    return _with_lock("semantic:clusters", _refresh_clusters)


def _refresh_clusters() -> dict:
    session = SessionLocal()
    try:
        result = SemanticClusterService(session).refresh_clusters()
        record_worker_metric("skytrax_semantic_clusters_total", float(result.get("clusters_created", 0)))
        return result
    finally:
        session.close()


def run_data_quality_scan() -> dict:
    return _with_lock("quality:scan", _quality_scan)


def _quality_scan() -> dict:
    session = SessionLocal()
    try:
        return DataQualityMonitor(session).run_scan()
    finally:
        session.close()


def run_forecasting_job() -> dict:
    return _with_lock("forecast:generate", _run_forecasting)


def _run_forecasting() -> dict:
    session = SessionLocal()
    try:
        result = TrendForecastingService(session).generate_and_persist()
        record_worker_metric("skytrax_forecasting_jobs_total", 1.0)
        record_worker_metric("skytrax_forecasts_persisted", float(result.get("forecasts_persisted", 0)))
        return result
    finally:
        session.close()


def run_anomaly_detection_job() -> dict:
    return _with_lock("anomaly:detect", _run_anomaly_detection)


def _run_anomaly_detection() -> dict:
    session = SessionLocal()
    try:
        result = AnomalyDetectionService(session).detect_and_persist()
        record_worker_metric("skytrax_anomalies_total", float(result.get("anomalies_created", 0)))
        return result
    finally:
        session.close()


def operational_cleanup(retention_days: int = 90) -> dict:
    return _with_lock("ops:cleanup", _cleanup, retention_days)


def _cleanup(retention_days: int) -> dict:
    session = SessionLocal()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    try:
        old_runs = (
            session.query(SpiderRun)
            .filter(SpiderRun.started_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return {"spider_runs_deleted": old_runs}
    finally:
        session.close()
