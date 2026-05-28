from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Iterable

from fastapi import Response
from redis import Redis
from sqlalchemy import event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from database.models import (
    Airline,
    AnomalyEvent,
    ExecutiveInsight,
    ForecastSnapshot,
    MetricSnapshot,
    NLPResult,
    Review,
    SpiderRun,
)
from database.models.aviation import AirlineMetadata, AirportMetadata, Alliance
from database.models.operations import OperationalRefreshRun


class MetricsRegistry:
    """Small in-process Prometheus registry without runtime dependency weight."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self.gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.histograms: defaultdict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)

    def inc(self, name: str, value: float = 1, **labels: object) -> None:
        with self._lock:
            self.counters[(name, self._labels(labels))] += value

    def set(self, name: str, value: float, **labels: object) -> None:
        with self._lock:
            self.gauges[(name, self._labels(labels))] = value

    def observe(self, name: str, value: float, **labels: object) -> None:
        with self._lock:
            samples = self.histograms[(name, self._labels(labels))]
            samples.append(value)
            if len(samples) > 5000:
                del samples[:1000]

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self.counters.items()):
                lines.append(f"{name}_total{self._format_labels(labels)} {value}")
            for (name, labels), value in sorted(self.gauges.items()):
                lines.append(f"{name}{self._format_labels(labels)} {value}")
            for (name, labels), samples in sorted(self.histograms.items()):
                count = len(samples)
                total = sum(samples)
                lines.append(f"{name}_count{self._format_labels(labels)} {count}")
                lines.append(f"{name}_sum{self._format_labels(labels)} {total}")
                if count:
                    lines.append(f"{name}_avg{self._format_labels(labels)} {total / count}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _labels(labels: dict[str, object]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((key, str(value)) for key, value in labels.items() if value is not None))

    @staticmethod
    def _format_labels(labels: Iterable[tuple[str, str]]) -> str:
        label_list = list(labels)
        if not label_list:
            return ""
        escaped = [f'{key}="{value.replace(chr(34), chr(92) + chr(34))}"' for key, value in label_list]
        return "{" + ",".join(escaped) + "}"


metrics = MetricsRegistry()
WORKER_METRICS_KEY = "skytrax:metrics:worker"


def instrument_sqlalchemy(engine: Engine) -> None:
    """Register SQLAlchemy query timing hooks once per process."""
    if getattr(engine, "_skytrax_metrics_registered", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._skytrax_query_started_at = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started_at = getattr(context, "_skytrax_query_started_at", None)
        if started_at is not None:
            metrics.observe("skytrax_db_query_duration_seconds", time.perf_counter() - started_at)
            metrics.inc("skytrax_db_queries")

    setattr(engine, "_skytrax_metrics_registered", True)


def collect_runtime_metrics(session: Session) -> None:
    """Refresh gauges that are better read from backing services at scrape time."""
    settings = get_settings()
    metrics.set("skytrax_reviews_total", float(session.query(func.count(Review.id)).scalar() or 0))
    metrics.set("skytrax_airlines_total", float(session.query(func.count(Airline.id)).scalar() or 0))
    metrics.set("skytrax_nlp_results_total", float(session.query(func.count(NLPResult.id)).scalar() or 0))
    metrics.set("skytrax_insights_total", float(session.query(func.count(ExecutiveInsight.id)).scalar() or 0))
    metrics.set("skytrax_snapshots_total", float(session.query(func.count(MetricSnapshot.id)).scalar() or 0))
    metrics.set("skytrax_anomalies_total", float(session.query(func.count(AnomalyEvent.id)).scalar() or 0))
    metrics.set(
        "skytrax_forecast_snapshots_total",
        float(session.query(func.count(ForecastSnapshot.id)).scalar() or 0),
    )

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_reviews = (
        session.query(func.count(Review.id)).filter(Review.created_at >= one_hour_ago).scalar() or 0
    )
    metrics.set("skytrax_reviews_per_hour", float(recent_reviews))

    airlines_total = float(session.query(func.count(AirlineMetadata.id)).scalar() or 0)
    airports_total = float(session.query(func.count(AirportMetadata.id)).scalar() or 0)
    alliances_total = float(session.query(func.count(Alliance.id)).scalar() or 0)
    hubs_total = float(
        session.query(func.count(AirportMetadata.id)).filter(AirportMetadata.hub_level.isnot(None)).scalar()
        or 0
    )

    metrics.set("skytrax_aviation_airlines_total", airlines_total)
    metrics.set("skytrax_aviation_airports_total", airports_total)
    metrics.set("skytrax_aviation_alliances_total", alliances_total)
    metrics.set("skytrax_aviation_hubs_total", hubs_total)
    metrics.set(
        "skytrax_aviation_premium_airlines",
        float(
            session.query(func.count(AirlineMetadata.id))
            .filter(AirlineMetadata.is_premium.is_(True))
            .scalar()
            or 0
        ),
    )

    missing_iata = float(
        session.query(func.count(AirportMetadata.id)).filter(AirportMetadata.iata.is_(None)).scalar() or 0
    )
    missing_icao = float(
        session.query(func.count(AirportMetadata.id)).filter(AirportMetadata.icao.is_(None)).scalar() or 0
    )
    metrics.set("skytrax_aviation_missing_iata", missing_iata)
    metrics.set("skytrax_aviation_missing_icao", missing_icao)

    avg_enrich = session.query(func.avg(AirlineMetadata.enrichment_confidence)).scalar()
    metrics.set("skytrax_aviation_enrichment_confidence", float(avg_enrich or 0))

    avg_norm = session.query(func.avg(AirlineMetadata.normalization_confidence)).scalar()
    metrics.set("skytrax_normalization_confidence", float(avg_norm or 0))

    total_entities = airlines_total + airports_total
    issues = missing_iata + missing_icao
    coverage = max(0.0, (1 - issues / max(total_entities * 2, 1)) * 100)
    metrics.set("skytrax_aviation_coverage_score", round(coverage, 1))

    ops_total = float(session.query(func.count(OperationalRefreshRun.id)).scalar() or 0)
    ops_avg_ms = session.query(func.avg(OperationalRefreshRun.duration_ms)).scalar()
    ops_reviews = session.query(func.sum(OperationalRefreshRun.reviews_processed)).scalar()
    ops_errors = session.query(func.sum(OperationalRefreshRun.error_count)).scalar()
    metrics.set("skytrax_operations_refresh_total", ops_total)
    metrics.set("skytrax_operations_avg_duration_ms", float(ops_avg_ms or 0))
    metrics.set("skytrax_operations_reviews_processed_total", float(ops_reviews or 0))
    metrics.set("skytrax_operations_failures_total", float(ops_errors or 0))

    latest_run = session.query(SpiderRun).order_by(SpiderRun.started_at.desc()).first()
    if latest_run:
        metrics.set(
            "skytrax_scrapy_last_items_scraped",
            float(latest_run.items_scraped),
            spider=latest_run.spider_name,
        )
        metrics.set(
            "skytrax_scrapy_last_pages_crawled",
            float(latest_run.pages_crawled),
            spider=latest_run.spider_name,
        )
        metrics.set(
            "skytrax_scrapy_last_error_count",
            float(len(latest_run.errors or [])),
            spider=latest_run.spider_name,
            status=latest_run.status,
        )
        if latest_run.finished_at:
            metrics.set(
                "skytrax_scrapy_last_duration_seconds",
                (latest_run.finished_at - latest_run.started_at).total_seconds(),
                spider=latest_run.spider_name,
            )

    try:
        redis = Redis.from_url(settings.redis_url)
        metrics.set("skytrax_redis_up", 1.0 if redis.ping() else 0.0)
        metrics.set("skytrax_rq_default_queue_size", float(redis.llen("rq:queue:default")))
        worker_metrics = redis.hgetall(WORKER_METRICS_KEY)
        for raw_name, raw_value in worker_metrics.items():
            name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)
            value = raw_value.decode("utf-8") if isinstance(raw_value, bytes) else str(raw_value)
            try:
                metrics.set(name, float(value))
            except ValueError:
                continue
    except Exception:
        metrics.set("skytrax_redis_up", 0.0)


def prometheus_response(session: Session) -> Response:
    collect_runtime_metrics(session)
    return Response(metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")


def record_worker_metric(name: str, value: float) -> None:
    settings = get_settings()
    try:
        Redis.from_url(settings.redis_url).hset(WORKER_METRICS_KEY, name, value)
    except Exception:
        return
