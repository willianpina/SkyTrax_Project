from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.constants import BENCHMARK_AIRLINES
from analytics.intelligence import ReputationService
from database.models import Airline, ForecastSnapshot, NLPResult, ReputationScoreHistory, Review


METRICS = ("reputation_score", "sentiment", "complaint_density")


class TrendForecastingService:
    """Lightweight EWMA + rolling-average forecasting with persistence."""

    def __init__(self, session: Session, alpha: float = 0.35, rolling_window: int = 7) -> None:
        self.session = session
        self.alpha = alpha
        self.rolling_window = rolling_window
        self.reputation = ReputationService(session)

    def generate_and_persist(self, airline_slugs: list[str] | None = None) -> dict:
        slugs = airline_slugs or BENCHMARK_AIRLINES
        created = 0
        for slug in slugs:
            airline = self.session.query(Airline).filter(Airline.slug == slug).first()
            if not airline:
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
                            method="ewma+rolling",
                            current_value=payload["current"],
                            forecast_value=payload["forecast_value"],
                            trend_direction=payload["trend"],
                            payload=payload,
                        )
                    )
                    created += 1
        self.session.commit()
        return {"forecasts_persisted": created}

    def list_forecasts(
        self,
        *,
        airline_slug: str | None = None,
        metric: str | None = None,
        horizon: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = self.session.query(ForecastSnapshot, Airline).outerjoin(
            Airline, ForecastSnapshot.airline_id == Airline.id
        )
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        if metric:
            query = query.filter(ForecastSnapshot.metric == metric)
        if horizon:
            query = query.filter(ForecastSnapshot.horizon == horizon)
        rows = query.order_by(ForecastSnapshot.generated_at.desc()).limit(limit).all()
        return [self._serialize(row, airline) for row, airline in rows]

    def portfolio_summary(self) -> dict:
        forecasts = self.list_forecasts(limit=100)
        by_metric: dict[str, list] = {m: [] for m in METRICS}
        for row in forecasts:
            if row["horizon"] == "weekly":
                by_metric.setdefault(row["metric"], []).append(row)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": by_metric,
            "airlines": sorted({row["airline_slug"] for row in forecasts if row.get("airline_slug")}),
        }

    def _build_forecast(self, airline: Airline, metric: str, horizon: str) -> dict | None:
        days = 7 if horizon == "weekly" else 30
        series = self._metric_series(airline, metric, days=days * 4)
        if not series:
            current = self._current_value(airline.slug, metric)
            return {
                "current": current,
                "forecast_value": current,
                "trend": "stable",
                "history": [],
                "rolling_average": current,
                "ewma": current,
                "forecast_points": [{"period": "+7d", "value": current}],
            }
        values = [point["value"] for point in series]
        rolling = sum(values[-self.rolling_window :]) / min(len(values), self.rolling_window)
        ewma = self._ewma(values)
        projected = round(0.55 * ewma + 0.45 * rolling, 2)
        current = values[-1]
        trend = self._trend_direction(current, projected)
        step_days = 7 if horizon == "weekly" else 30
        forecast_points = []
        cursor = projected
        for step in range(1, 4):
            cursor = round(self.alpha * cursor + (1 - self.alpha) * current, 2)
            forecast_points.append({"period": f"+{step * step_days}d", "value": cursor})
        return {
            "current": round(current, 2),
            "forecast_value": projected,
            "trend": trend,
            "history": series[-12:],
            "rolling_average": round(rolling, 2),
            "ewma": round(ewma, 2),
            "forecast_points": forecast_points,
        }

    def _metric_series(self, airline: Airline, metric: str, days: int = 90) -> list[dict]:
        if metric == "reputation_score":
            return self._reputation_series(airline.id, days)
        if metric == "sentiment":
            return self._sentiment_series(airline.id, days)
        return self._complaint_series(airline.id, days)

    def _reputation_series(self, airline_id: str, days: int) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
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
        airline = self.session.get(Airline, airline_id)
        if not airline:
            return []
        score = self.reputation.score_airline(airline.slug)
        return [{"period": date.today().isoformat(), "value": score["score"]}]

    def _sentiment_series(self, airline_id: str, days: int) -> list[dict]:
        since = date.today() - timedelta(days=days)
        rows = (
            self.session.query(Review.review_date, NLPResult.sentiment_score)
            .join(NLPResult)
            .filter(Review.airline_id == airline_id, Review.review_date.isnot(None), Review.review_date >= since)
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
        since = date.today() - timedelta(days=days)
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

    def _current_value(self, airline_slug: str, metric: str) -> float:
        score = self.reputation.score_airline(airline_slug)
        mapping = {
            "reputation_score": "score",
            "sentiment": "sentiment_component",
            "complaint_density": "complaint_density",
        }
        return float(score.get(mapping[metric], 0))

    def _ewma(self, values: list[float]) -> float:
        if not values:
            return 0.0
        result = values[0]
        for value in values[1:]:
            result = self.alpha * value + (1 - self.alpha) * result
        return result

    @staticmethod
    def _trend_direction(current: float, projected: float) -> str:
        if projected > current + 1.5:
            return "improving"
        if projected < current - 1.5:
            return "declining"
        return "stable"

    @staticmethod
    def _serialize(row: ForecastSnapshot, airline: Airline | None) -> dict:
        return {
            "id": row.id,
            "airline": airline.name if airline else "Portfolio",
            "airline_slug": airline.slug if airline else None,
            "metric": row.metric,
            "horizon": row.horizon,
            "method": row.method,
            "current_value": row.current_value,
            "forecast_value": row.forecast_value,
            "trend_direction": row.trend_direction,
            "generated_at": row.generated_at.isoformat(),
            "payload": row.payload,
        }
