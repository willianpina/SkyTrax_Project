from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.constants import BENCHMARK_AIRLINES
from analytics.intelligence import ReputationService, TopicTrendService
from database.models import Airline, ExecutiveInsight, NLPResult, Review


class ExecutiveInsightEngine:
    """Detect and persist executive intelligence signals."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.reputation = ReputationService(session)
        self.trends = TopicTrendService(session)

    def generate_and_persist(self, lookback_days: int = 14) -> dict:
        self.session.query(ExecutiveInsight).delete()
        since = date.today() - timedelta(days=lookback_days)
        previous_since = date.today() - timedelta(days=lookback_days * 2)
        created = 0
        airlines = (
            self.session.query(Airline)
            .filter(Airline.slug.in_(BENCHMARK_AIRLINES))
            .order_by(Airline.name.asc())
            .all()
        )
        for airline in airlines:
            created += self._airline_insights(airline, since, previous_since, lookback_days)
        created += self._portfolio_insights(airlines, lookback_days)
        self.session.commit()
        return {"insights_created": created}

    def list_recent(self, limit: int = 30) -> list[dict]:
        rows = (
            self.session.query(ExecutiveInsight, Airline)
            .outerjoin(Airline, ExecutiveInsight.airline_id == Airline.id)
            .order_by(ExecutiveInsight.generated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": insight.id,
                "airline": airline.name if airline else "Portfolio",
                "airline_slug": airline.slug if airline else None,
                "category": insight.category,
                "severity": insight.severity,
                "confidence": insight.confidence,
                "confidence_score": insight.confidence,
                "generated_at": insight.generated_at.isoformat(),
                "summary": insight.insight_text,
                "insight_text": insight.insight_text,
                "trend_direction": insight.trend_direction,
                "supporting_reviews": insight.supporting_reviews,
                "supporting_topics": insight.supporting_topics,
                "drivers": list((insight.supporting_metrics or {}).get("drivers", [])),
                "supporting_metrics": insight.supporting_metrics,
            }
            for insight, airline in rows
        ]

    def _airline_insights(self, airline: Airline, since: date, previous_since: date, lookback_days: int) -> int:
        created = 0
        score = self.reputation.score_airline(airline.slug)
        if score["review_count"] == 0:
            return 0

        current_negative = self._negative_share(airline.id, since)
        previous_negative = self._negative_share(airline.id, previous_since, since)
        if previous_negative > 0:
            delta = (current_negative - previous_negative) / previous_negative
            if delta >= 0.15:
                created += self._add(
                    airline,
                    category="sentiment_shift",
                    severity="high" if delta >= 0.25 else "medium",
                    confidence=min(0.95, 0.6 + delta),
                    text=f"Negative sentiment share increased {round(delta * 100)}% in the last {lookback_days} days for {airline.name}.",
                    metrics={"delta_pct": round(delta * 100, 2), "drivers": ["sentiment"]},
                )

        complaint_delta = self._complaint_density_delta(airline.id, since, previous_since)
        if complaint_delta >= 0.18:
            created += self._add(
                airline,
                category="complaint_spike",
                severity="high",
                confidence=0.82,
                text=f"Complaint density increased {round(complaint_delta * 100)}% in the last {lookback_days} days for {airline.name}.",
                metrics={"delta_pct": round(complaint_delta * 100, 2), "drivers": ["complaint density"]},
            )

        if score["score"] < 55:
            created += self._add(
                airline,
                category="reputation_risk",
                severity="high",
                confidence=0.88,
                text=f"{airline.name} shows elevated reputation risk with an ARS of {score['score']}.",
                metrics={"ars": score["score"], "drivers": ["rating", "recommendation", "complaint severity"]},
            )
        elif score["score"] >= 75:
            created += self._add(
                airline,
                category="performance_improvement",
                severity="positive",
                confidence=0.8,
                text=f"{airline.name} is outperforming the tracked peer set with an ARS of {score['score']}.",
                metrics={"ars": score["score"], "drivers": ["rating", "recommendation"]},
            )

        emerging = [row for row in self.trends.trends(airline.slug, days=lookback_days) if row["growth_rate"] >= 0.5][:2]
        for row in emerging:
            created += self._add(
                airline,
                category="emerging_topic",
                severity="medium",
                confidence=0.72,
                text=f"'{row['topic']}' became an emerging complaint cluster for {airline.name} (+{round(row['growth_rate'] * 100)}%).",
                metrics={"topic": row["topic"], "growth_rate": row["growth_rate"], "drivers": ["topics"]},
            )
        return created

    def _portfolio_insights(self, airlines: list[Airline], lookback_days: int) -> int:
        created = 0
        scores = {airline.slug: self.reputation.score_airline(airline.slug) for airline in airlines}
        premium_slugs = {"emirates", "qatar-airways", "british-airways", "lufthansa"}
        premium_scores = [scores[s]["sentiment_component"] for s in premium_slugs if s in scores and scores[s]["review_count"]]
        if premium_scores and sum(premium_scores) / len(premium_scores) < 55:
            created += self._add(
                None,
                category="segment_deterioration",
                severity="medium",
                confidence=0.7,
                text="Premium cabin sentiment deteriorated among European and Gulf carriers in the tracked set.",
                metrics={"segment": "premium", "drivers": ["sentiment", "segment"]},
            )
        topic_rows = self.trends.trends(days=lookback_days)
        if topic_rows and topic_rows[0]["growth_rate"] >= 0.4:
            top = topic_rows[0]["topic"]
            created += self._add(
                None,
                category="operational_risk",
                severity="high",
                confidence=0.78,
                text=f"'{top}' became the dominant complaint cluster across the portfolio.",
                metrics={"topic": top, "growth_rate": topic_rows[0]["growth_rate"], "drivers": ["topics"]},
            )
        return created

    def _negative_share(self, airline_id: str, since: date, until: date | None = None) -> float:
        query = (
            self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id))
            .join(Review)
            .filter(Review.airline_id == airline_id, Review.review_date >= since)
        )
        if until:
            query = query.filter(Review.review_date < until)
        dist = {label: count for label, count in query.group_by(NLPResult.sentiment_label).all()}
        total = sum(dist.values()) or 1
        return dist.get("negative", 0) / total

    def _complaint_density_delta(self, airline_id: str, since: date, previous_since: date) -> float:
        def density(start: date, end: date | None = None) -> float:
            q = self.session.query(func.count(Review.id)).filter(
                Review.airline_id == airline_id,
                Review.review_date >= start,
                Review.recommended.is_(False),
            )
            if end:
                q = q.filter(Review.review_date < end)
            complaints = q.scalar() or 0
            total_q = self.session.query(func.count(Review.id)).filter(Review.airline_id == airline_id, Review.review_date >= start)
            if end:
                total_q = total_q.filter(Review.review_date < end)
            total = total_q.scalar() or 1
            return complaints / total

        current = density(since)
        previous = density(previous_since, since)
        if previous <= 0:
            return 0.0
        return (current - previous) / previous

    def _add(
        self,
        airline: Airline | None,
        *,
        category: str,
        severity: str,
        confidence: float,
        text: str,
        metrics: dict,
    ) -> int:
        self.session.add(
            ExecutiveInsight(
                airline_id=airline.id if airline else None,
                category=category,
                severity=severity,
                confidence=confidence,
                insight_text=text,
                supporting_metrics=metrics,
            )
        )
        return 1
