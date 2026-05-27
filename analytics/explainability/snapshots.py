from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.intelligence import ReputationService
from app.heartbeat import TimedHeartbeat, heartbeat_guard
from database.models import Airline, MetricSnapshot, NLPResult, Review, TopicSnapshot

logger = logging.getLogger(__name__)


class SnapshotService:
    """Generate hourly, daily and weekly metric snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.reputation = ReputationService(session)

    @heartbeat_guard(interval_s=25)
    def generate(
        self,
        snapshot_type: str,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        period_map = {
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(days=7),
        }
        delta = period_map.get(snapshot_type, timedelta(days=1))
        period_start = now - delta
        created = 0
        airlines = self.session.query(Airline).filter(Airline.is_active.is_(True)).all()
        total = len(airlines)
        timer = TimedHeartbeat(heartbeat_fn, stage="snapshots", substage="snapshot_generate", interval_s=25)
        timer.pulse_if_needed(detail=f"snapshot: building {total} airline metrics", processed=0, total=total, force=True)
        logger.info("[SNAPSHOT] generate type=%s airlines=%d", snapshot_type, total)

        for idx, airline in enumerate(airlines):
            timer.pulse_if_needed(
                detail=f"snapshot: airline {idx}/{total} {airline.slug}",
                processed=idx,
                total=total,
                current_substage="airline_metrics",
            )
            metrics = self._airline_metrics(airline.id, period_start, now)
            if metrics["review_volume"] == 0 and snapshot_type == "hourly":
                continue
            self.session.add(
                MetricSnapshot(
                    airline_id=airline.id,
                    snapshot_type=snapshot_type,
                    period_start=period_start,
                    period_end=now,
                    metrics=metrics,
                )
            )
            created += 1

        timer.pulse_if_needed(
            detail="snapshot: portfolio aggregate",
            processed=total,
            total=total,
            current_substage="portfolio_aggregate",
            force=True,
        )
        portfolio = self._portfolio_metrics(period_start, now)
        self.session.add(
            MetricSnapshot(
                airline_id=None,
                snapshot_type=snapshot_type,
                period_start=period_start,
                period_end=now,
                metrics=portfolio,
            )
        )
        timer.pulse_if_needed(
            detail="snapshot: committing",
            processed=total,
            total=total,
            current_substage="committing",
            force=True,
        )
        try:
            self.session.commit()
        except Exception as exc:
            logger.exception("[SNAPSHOT] commit failed type=%s: %s", snapshot_type, exc)
            self.session.rollback()
            return {"error": str(exc), "snapshot_type": snapshot_type, "created": 0}
        logger.info("[SNAPSHOT] persisted type=%s created=%d", snapshot_type, created + 1)
        return {"snapshot_type": snapshot_type, "created": created + 1}

    def _airline_metrics(self, airline_id: str, period_start: datetime, period_end: datetime) -> dict:
        airline = self.session.get(Airline, airline_id)
        slug = airline.slug if airline else ""
        score = self.reputation.score_airline(slug) if slug else {}
        rows = (
            self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id))
            .join(Review)
            .filter(
                Review.airline_id == airline_id,
                Review.review_date >= period_start.date(),
            )
            .group_by(NLPResult.sentiment_label)
            .all()
        )
        sentiment = {label: int(count) for label, count in rows}
        topics = (
            self.session.query(TopicSnapshot.label, TopicSnapshot.weight, TopicSnapshot.polarity)
            .filter(TopicSnapshot.airline_id == airline_id)
            .order_by(TopicSnapshot.weight.desc())
            .limit(10)
            .all()
        )
        volume = (
            self.session.query(func.count(Review.id))
            .filter(Review.airline_id == airline_id, Review.created_at >= period_start)
            .scalar()
            or 0
        )
        return {
            "reputation_score": score.get("score", 0),
            "sentiment_distribution": sentiment,
            "top_topics": [{"label": label, "weight": weight, "polarity": polarity} for label, weight, polarity in topics],
            "review_volume": int(volume),
            "trends": score.get("timeline", [])[-6:],
            "categories": score.get("categories", {}),
        }

    def _portfolio_metrics(self, period_start: datetime, period_end: datetime) -> dict:
        sentiment_rows = (
            self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id)).group_by(NLPResult.sentiment_label).all()
        )
        volume = (
            self.session.query(func.count(Review.id)).filter(Review.created_at >= period_start).scalar() or 0
        )
        avg_rating = self.session.query(func.avg(Review.rating)).scalar()
        return {
            "reputation_score": 0,
            "sentiment_distribution": {label: int(count) for label, count in sentiment_rows},
            "review_volume": int(volume),
            "average_rating": round(float(avg_rating or 0), 2),
            "top_topics": [],
            "trends": [],
        }

    def list_snapshots(
        self,
        *,
        airline_slug: str | None = None,
        snapshot_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = self.session.query(MetricSnapshot).order_by(MetricSnapshot.period_end.desc())
        if snapshot_type:
            query = query.filter(MetricSnapshot.snapshot_type == snapshot_type)
        if airline_slug:
            query = query.join(Airline).filter(Airline.slug == airline_slug)
        return [
            {
                "id": row.id,
                "airline_id": row.airline_id,
                "snapshot_type": row.snapshot_type,
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "metrics": row.metrics,
            }
            for row in query.limit(limit).all()
        ]
