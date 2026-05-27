from __future__ import annotations

import logging
import statistics
import time
from datetime import date, timedelta
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.alerting import emit_alert
from database.models import Airline, AnomalyEvent, NLPResult, Review, TopicSnapshot

logger = logging.getLogger(__name__)

ANOMALY_TIMEOUT_S = 300


class AnomalyDetectionService:
    """Statistical anomaly detection for reputation and operational signals."""

    def __init__(self, session: Session, z_threshold: float = 2.0) -> None:
        self.session = session
        self.z_threshold = z_threshold

    def detect_and_persist(
        self,
        lookback_days: int = 30,
        heartbeat_fn: Callable | None = None,
    ) -> dict:
        since = date.today() - timedelta(days=lookback_days)
        created = 0
        errors: list[str] = []
        t0 = time.monotonic()
        airlines = self.session.query(Airline).filter(Airline.is_active.is_(True)).all()
        logger.info("[ANOMALY] Starting: airlines=%d lookback=%dd", len(airlines), lookback_days)

        for i, airline in enumerate(airlines):
            if time.monotonic() - t0 > ANOMALY_TIMEOUT_S:
                logger.warning("[ANOMALY] Timeout after %ds, processed %d/%d", ANOMALY_TIMEOUT_S, i, len(airlines))
                break
            if heartbeat_fn and i % 5 == 0:
                heartbeat_fn(f"anomaly {i+1}/{len(airlines)} {airline.slug}")
            try:
                created += self._detect_airline_anomalies(airline, since)
            except Exception as exc:
                logger.warning("[ANOMALY] Error processing %s: %s", airline.slug, exc)
                errors.append(f"{airline.slug}: {exc}")
                try:
                    self.session.rollback()
                except Exception:
                    pass

        try:
            self.session.commit()
        except Exception as exc:
            logger.warning("[ANOMALY] Commit failed: %s", exc)
            self.session.rollback()
            errors.append(f"commit: {exc}")

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info("[ANOMALY] Done: created=%d errors=%d elapsed=%dms", created, len(errors), elapsed_ms)
        return {"anomalies_created": created, "airlines_scanned": len(airlines), "errors": errors[:10], "elapsed_ms": elapsed_ms}

    def list_recent(self, limit: int = 50, airline_slug: str | None = None) -> list[dict]:
        query = (
            self.session.query(AnomalyEvent, Airline)
            .outerjoin(Airline, AnomalyEvent.airline_id == Airline.id)
            .order_by(AnomalyEvent.detected_at.desc())
        )
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        return [
            {
                "id": event.id,
                "airline_id": event.airline_id,
                "airline": airline.name if airline else "Portfolio",
                "airline_slug": airline.slug if airline else None,
                "anomaly_type": event.anomaly_type,
                "severity": event.severity,
                "metric": event.metric,
                "expected_value": event.expected_value,
                "observed_value": event.observed_value,
                "context": event.context,
                "detected_at": event.detected_at.isoformat(),
            }
            for event, airline in query.limit(limit).all()
        ]

    def operational_alerts(self, limit: int = 20) -> list[dict]:
        """High-severity anomalies formatted for executive alert panels."""
        rows = self.list_recent(limit=limit * 2)
        alerts = []
        for row in rows:
            if row["severity"] not in {"high", "medium"}:
                continue
            alerts.append(
                {
                    "id": row["id"],
                    "title": self._alert_title(row),
                    "airline": row["airline"],
                    "severity": row["severity"],
                    "anomaly_type": row["anomaly_type"],
                    "detected_at": row["detected_at"],
                    "detail": (
                        f"Observed {row['observed_value']} vs expected "
                        f"{row['expected_value']} on {row['metric']}."
                    ),
                }
            )
            if len(alerts) >= limit:
                break
        return alerts

    def _detect_airline_anomalies(self, airline: Airline, since: date) -> int:
        created = 0
        daily_counts = self._daily_complaint_counts(airline.id, since)
        if len(daily_counts) >= 5:
            mean = statistics.mean(daily_counts)
            stdev = statistics.pstdev(daily_counts) or 1
            latest = daily_counts[-1]
            z = (latest - mean) / stdev
            if z >= self.z_threshold:
                created += self._add(
                    airline,
                    anomaly_type="complaint_spike",
                    metric="daily_complaints",
                    expected=mean,
                    observed=latest,
                    severity="high" if z >= 3 else "medium",
                    context={"z_score": round(z, 2)},
                )

        neg_current, neg_previous = self._sentiment_windows(airline.id)
        if neg_previous > 0 and (neg_current - neg_previous) / neg_previous >= 0.25:
            created += self._add(
                airline,
                anomaly_type="sentiment_drop",
                metric="negative_sentiment_share",
                expected=neg_previous,
                observed=neg_current,
                severity="high",
                context={"delta_pct": round((neg_current - neg_previous) / neg_previous * 100, 1)},
            )

        reputation_drop = self._reputation_abrupt_drop(airline)
        if reputation_drop:
            created += self._add(
                airline,
                anomaly_type="reputation_deterioration",
                metric="reputation_score",
                expected=reputation_drop["expected"],
                observed=reputation_drop["observed"],
                severity="high",
                context=reputation_drop,
            )

        for topic_row in self._exploding_topics(airline.id):
            created += self._add(
                airline,
                anomaly_type="topic_explosion",
                metric=f"topic:{topic_row['label']}",
                expected=topic_row["baseline"],
                observed=topic_row["current"],
                severity="medium",
                context=topic_row,
            )
        return created

    def _add(
        self,
        airline: Airline | None,
        *,
        anomaly_type: str,
        metric: str,
        expected: float,
        observed: float,
        severity: str,
        context: dict,
    ) -> int:
        self.session.add(
            AnomalyEvent(
                airline_id=airline.id if airline else None,
                anomaly_type=anomaly_type,
                severity=severity,
                metric=metric,
                expected_value=round(expected, 4),
                observed_value=round(observed, 4),
                context=context,
            )
        )
        emit_alert(
            anomaly_type,
            {
                "airline": airline.name if airline else "Portfolio",
                "metric": metric,
                "observed": observed,
                "expected": expected,
                "slack": {"text": f"[SkyTrax] {anomaly_type}: {airline.name if airline else 'Portfolio'}"},
            },
            severity=severity,
        )
        return 1

    def _reputation_abrupt_drop(self, airline: Airline) -> dict | None:
        from analytics.intelligence import ReputationService

        score = ReputationService(self.session).score_airline(airline.slug)
        current = float(score.get("score", 0))
        if current >= 55:
            return None
        baseline = 70.0
        if baseline - current >= 12:
            return {
                "expected": baseline,
                "observed": current,
                "delta": round(baseline - current, 2),
                "drivers": ["complaint_density", "sentiment"],
            }
        return None

    @staticmethod
    def _alert_title(row: dict) -> str:
        titles = {
            "complaint_spike": "Complaint volume spike",
            "sentiment_drop": "Sentiment deterioration",
            "reputation_deterioration": "Reputational risk alert",
            "topic_explosion": "Negative topic explosion",
        }
        return titles.get(row["anomaly_type"], row["anomaly_type"].replace("_", " ").title())

    def _daily_complaint_counts(self, airline_id: str, since: date) -> list[float]:
        rows = (
            self.session.query(Review.review_date, func.count(Review.id))
            .filter(Review.airline_id == airline_id, Review.review_date >= since, Review.recommended.is_(False))
            .group_by(Review.review_date)
            .order_by(Review.review_date)
            .all()
        )
        return [float(count) for _, count in rows]

    def _sentiment_windows(self, airline_id: str) -> tuple[float, float]:
        midpoint = date.today() - timedelta(days=14)

        def share(start: date, end: date | None = None) -> float:
            q = (
                self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id))
                .join(Review)
                .filter(Review.airline_id == airline_id, Review.review_date >= start)
            )
            if end:
                q = q.filter(Review.review_date < end)
            dist = {label: count for label, count in q.group_by(NLPResult.sentiment_label).all()}
            total = sum(dist.values()) or 1
            return dist.get("negative", 0) / total

        return share(midpoint), share(date.today() - timedelta(days=28), midpoint)

    def _exploding_topics(self, airline_id: str) -> list[dict]:
        rows = (
            self.session.query(TopicSnapshot.label, TopicSnapshot.weight)
            .filter(TopicSnapshot.airline_id == airline_id, TopicSnapshot.polarity == "negative")
            .order_by(TopicSnapshot.weight.desc())
            .limit(5)
            .all()
        )
        if not rows:
            return []
        weights = [weight for _, weight in rows]
        mean = statistics.mean(weights)
        return [
            {"label": label, "current": weight, "baseline": mean}
            for label, weight in rows
            if weight > mean * 2
        ][:2]
