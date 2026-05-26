from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.constants import SEMANTIC_CLUSTER_LABELS
from analytics.intelligence import ReputationService, TopicTrendService
from database.models import Airline, NLPResult, Review, SemanticCluster


class ExplainableIntelligenceService:
    """Human-readable explanations for scores, clusters and trend shifts."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.reputation = ReputationService(session)
        self.trends = TopicTrendService(session)

    def explain_reputation_score(self, airline_slug: str, lookback_days: int = 14) -> dict:
        score = self.reputation.score_airline(airline_slug)
        airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
        since = date.today() - timedelta(days=lookback_days)
        drivers = self._top_negative_drivers(airline.id if airline else None, since)
        trend_rows = self.trends.trends(airline_slug, days=lookback_days)[:3]
        direction = "declining" if score["score"] < 55 else "improving" if score["score"] >= 70 else "stable"
        topic_phrase = ", ".join(d["topic"] for d in drivers[:2]) or "mixed operational themes"
        delta_complaint = self._complaint_delta(airline.id if airline else None, lookback_days)
        narrative = (
            f"Airline Reputation Score is {score['score']} ({direction}). "
            f"Primary drivers: {topic_phrase}. "
        )
        if delta_complaint >= 10:
            narrative += (
                f"Complaints increased approximately {round(delta_complaint)}% in the last {lookback_days} days, "
                f"notably around {topic_phrase}."
            )
        else:
            narrative += f"Sentiment component at {score['sentiment_component']} with complaint density {score.get('complaint_density', 0)}."
        return {
            "airline_slug": airline_slug,
            "score": score["score"],
            "direction": direction,
            "narrative": narrative,
            "components": {
                "rating": score["rating_component"],
                "sentiment": score["sentiment_component"],
                "recommendation": score["recommendation_component"],
                "complaint_severity": score["complaint_severity"],
                "topic_negativity": score["topic_negativity"],
                "recency": score.get("recency_component", 0),
                "complaint_density": score.get("complaint_density", 0),
            },
            "top_negative_topics": drivers,
            "trend_correlation": trend_rows,
            "supporting_evidence_count": score["review_count"],
        }

    def explain_cluster(self, cluster_id: str) -> dict:
        cluster = self.session.get(SemanticCluster, cluster_id)
        if not cluster:
            return {"detail": "Cluster not found"}
        keywords = SEMANTIC_CLUSTER_LABELS.get(cluster.cluster_label, set())
        return {
            "cluster_id": cluster.id,
            "cluster_label": cluster.cluster_label,
            "narrative": (
                f"Cluster '{cluster.cluster_label}' groups {cluster.review_count} reviews "
                f"with centroid terms {', '.join(cluster.centroid_terms[:5])}."
            ),
            "matched_keywords": sorted(keywords)[:10],
            "confidence": cluster.confidence,
            "relevance_score": cluster.relevance_score,
            "sample_review_ids": cluster.sample_review_ids,
        }

    def explain_trend_change(self, airline_slug: str, topic: str, days: int = 30) -> dict:
        rows = self.trends.trends(airline_slug, days=days)
        match = next((row for row in rows if row["topic"] == topic), None)
        if not match:
            return {"topic": topic, "narrative": f"No significant trend detected for '{topic}'."}
        direction = "rising" if match["growth_rate"] > 0 else "falling"
        return {
            "topic": topic,
            "direction": direction,
            "growth_rate": match["growth_rate"],
            "narrative": (
                f"Topic '{topic}' is {direction} with growth rate {round(match['growth_rate'] * 100, 1)}% "
                f"(current={match['current']}, previous={match['previous']})."
            ),
        }

    def explain_anomaly(self, anomaly_payload: dict) -> str:
        return (
            f"Anomaly '{anomaly_payload.get('anomaly_type')}' on {anomaly_payload.get('metric')}: "
            f"observed {anomaly_payload.get('observed_value')} vs expected "
            f"{anomaly_payload.get('expected_value')} ({anomaly_payload.get('severity')} severity)."
        )

    def _top_negative_drivers(self, airline_id: str | None, since: date) -> list[dict]:
        if not airline_id:
            return []
        rows = (
            self.session.query(NLPResult.topics, Review.text)
            .join(Review)
            .filter(Review.airline_id == airline_id, Review.review_date >= since, NLPResult.sentiment_label == "negative")
            .limit(200)
            .all()
        )
        counts: dict[str, int] = {}
        for topics, _ in rows:
            for topic in topics or []:
                counts[topic] = counts.get(topic, 0) + 1
        return [{"topic": topic, "count": count} for topic, count in sorted(counts.items(), key=lambda x: -x[1])[:5]]

    def _complaint_delta(self, airline_id: str | None, lookback_days: int) -> float:
        if not airline_id:
            return 0.0
        since = date.today() - timedelta(days=lookback_days)
        mid = date.today() - timedelta(days=lookback_days // 2)

        def rate(start: date, end: date | None = None) -> float:
            q = self.session.query(func.count(Review.id)).filter(
                Review.airline_id == airline_id, Review.review_date >= start, Review.recommended.is_(False)
            )
            if end:
                q = q.filter(Review.review_date < end)
            complaints = q.scalar() or 0
            total_q = self.session.query(func.count(Review.id)).filter(Review.airline_id == airline_id, Review.review_date >= start)
            if end:
                total_q = total_q.filter(Review.review_date < end)
            total = total_q.scalar() or 1
            return complaints / total * 100

        current = rate(mid)
        previous = rate(since, mid)
        if previous <= 0:
            return 0.0
        return (current - previous) / previous * 100
