"""Safe forecasting — pure Python, no numpy/scipy. Used when native stack is unstable."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.constants import BENCHMARK_AIRLINES
from database.models import Airline, ForecastSnapshot, NLPResult, ReputationScoreHistory, Review

logger = logging.getLogger(__name__)

METRICS = ("reputation_score", "sentiment", "complaint_density")
MAX_LOOKBACK_DAYS = 365


class SafeTrendForecastingService:
    """Minimal EWMA + rolling average using only stdlib math."""

    def __init__(self, session: Session, alpha: float = 0.35, rolling_window: int = 7) -> None:
        self.session = session
        self.alpha = alpha
        self.rolling_window = rolling_window

    def generate_and_persist(
        self,
        airline_slugs: list[str] | None = None,
        heartbeat_fn: Callable | None = None,
    ) -> dict:
        slugs = airline_slugs or BENCHMARK_AIRLINES
        created = 0
        skipped = 0
        errors: list[str] = []
        t0 = time.monotonic()

        logger.warning("[FORECAST_NATIVE] Safe mode starting airlines=%d", len(slugs))

        for i, slug in enumerate(slugs):
            if heartbeat_fn:
                heartbeat_fn(f"safe forecast {i + 1}/{len(slugs)} {slug}")

            try:
                airline = self.session.query(Airline).filter(Airline.slug == slug).first()
                if not airline:
                    skipped += 1
                    continue
                for metric in METRICS:
                    for horizon in ("weekly", "monthly"):
                        payload = self._build_forecast(airline, metric, horizon)
                        if not payload:
                            continue
                        self.session.add(
                            ForecastSnapshot(
                                airline_id=airline.id,
                                metric=metric,
                                horizon=horizon,
                                method="safe_rolling+linear",
                                current_value=payload["current"],
                                forecast_value=payload["forecast_value"],
                                trend_direction=payload["trend"],
                                payload=payload,
                            )
                        )
                        created += 1
            except Exception as exc:
                logger.warning("[FORECAST_NATIVE] Error %s: %s", slug, exc)
                errors.append(f"{slug}: {exc}")
                try:
                    self.session.rollback()
                except Exception:
                    pass

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            errors.append(f"commit: {exc}")

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "[FORECAST_NATIVE] Safe mode done created=%d skipped=%d errors=%d ms=%d",
            created,
            skipped,
            len(errors),
            elapsed_ms,
        )
        return {
            "forecasts_persisted": created,
            "airlines_processed": len(slugs) - skipped,
            "airlines_skipped": skipped,
            "errors": errors[:10],
            "elapsed_ms": elapsed_ms,
            "mode": "safe",
        }

    def _build_forecast(self, airline: Airline, metric: str, horizon: str) -> dict | None:
        days = 7 if horizon == "weekly" else 30
        series = self._metric_series(airline, metric, days=days * 4)
        if not series:
            return None

        values = [float(p["value"]) for p in series]
        window = values[-self.rolling_window :]
        rolling = sum(window) / len(window) if window else values[-1]
        ewma = self._ewma(values)
        projected = round(0.55 * ewma + 0.45 * rolling, 2)
        current = values[-1]
        trend = self._trend_direction(current, projected)
        linear = self._linear_trend(values[-min(14, len(values)) :])

        return {
            "current": round(current, 2),
            "forecast_value": projected,
            "trend": trend,
            "history": series[-12:],
            "rolling_average": round(rolling, 2),
            "ewma": round(ewma, 2),
            "linear_slope": linear,
            "forecast_points": [{"period": "+7d", "value": projected}],
        }

    def _metric_series(self, airline: Airline, metric: str, days: int = 90) -> list[dict]:
        if metric == "reputation_score":
            return self._reputation_series(airline.id, days)
        if metric == "sentiment":
            return self._sentiment_series(airline.id, days)
        return self._complaint_series(airline.id, days)

    def _reputation_series(self, airline_id: str, days: int) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=min(days, MAX_LOOKBACK_DAYS))
        rows = (
            self.session.query(ReputationScoreHistory)
            .filter(
                ReputationScoreHistory.airline_id == airline_id,
                ReputationScoreHistory.category.is_(None),
                ReputationScoreHistory.recorded_at >= since,
            )
            .order_by(ReputationScoreHistory.recorded_at.asc())
            .all()
        )
        if rows:
            return [{"period": row.recorded_at.date().isoformat(), "value": row.score} for row in rows]
        return [{"period": date.today().isoformat(), "value": 50.0}]

    def _sentiment_series(self, airline_id: str, days: int) -> list[dict]:
        since = date.today() - timedelta(days=min(days, MAX_LOOKBACK_DAYS))
        rows = (
            self.session.query(Review.review_date, NLPResult.sentiment_score)
            .join(NLPResult)
            .filter(
                Review.airline_id == airline_id, Review.review_date.isnot(None), Review.review_date >= since
            )
            .all()
        )
        buckets: dict[date, list[float]] = {}
        for review_date, score in rows:
            buckets.setdefault(review_date, []).append(float(score))
        return [
            {"period": bucket.isoformat(), "value": round(sum(vals) / len(vals) * 50 + 50, 2)}
            for bucket, vals in sorted(buckets.items())
        ]

    def _complaint_series(self, airline_id: str, days: int) -> list[dict]:
        since = date.today() - timedelta(days=min(days, MAX_LOOKBACK_DAYS))
        rows = (
            self.session.query(Review.review_date, func.count(Review.id))
            .filter(Review.airline_id == airline_id, Review.review_date >= since)
            .group_by(Review.review_date)
            .order_by(Review.review_date)
            .all()
        )
        complaints = (
            self.session.query(Review.review_date, func.count(Review.id))
            .filter(
                Review.airline_id == airline_id,
                Review.review_date >= since,
                Review.recommended.is_(False),
            )
            .group_by(Review.review_date)
            .all()
        )
        complaint_map = {d: c for d, c in complaints}
        series = []
        for review_date, total in rows:
            complaints_count = complaint_map.get(review_date, 0)
            density = round(complaints_count / max(total, 1) * 100, 2)
            series.append({"period": review_date.isoformat(), "value": density})
        return series

    def _ewma(self, values: list[float]) -> float:
        if not values:
            return 0.0
        result = values[0]
        for value in values[1:]:
            result = self.alpha * value + (1 - self.alpha) * result
        return result

    @staticmethod
    def _linear_trend(values: list[float]) -> float:
        """Simple least-squares slope (stdlib only)."""
        n = len(values)
        if n < 2:
            return 0.0
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        den = sum((x - mean_x) ** 2 for x in xs) or 1.0
        return round(num / den, 4)

    @staticmethod
    def _trend_direction(current: float, projected: float) -> str:
        if projected > current + 1.5:
            return "improving"
        if projected < current - 1.5:
            return "declining"
        return "stable"
