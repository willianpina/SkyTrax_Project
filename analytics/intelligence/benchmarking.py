from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from analytics.constants import BENCHMARK_AIRLINES
from analytics.intelligence.reputation import ReputationService
from database.models import Airline, TopicSnapshot


class BenchmarkingService:
    """Competitive comparison across airlines."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def compare(self, slugs: list[str] | None = None) -> dict:
        target_slugs = slugs or BENCHMARK_AIRLINES
        reputation_service = ReputationService(self.session)
        reputation = [reputation_service.score_airline(slug) for slug in target_slugs]
        topics = (
            self.session.query(
                Airline.slug, TopicSnapshot.label, TopicSnapshot.polarity, TopicSnapshot.weight
            )
            .join(Airline, TopicSnapshot.airline_id == Airline.id)
            .filter(Airline.slug.in_(target_slugs))
            .order_by(TopicSnapshot.weight.desc())
            .all()
        )
        topic_map: defaultdict[str, list[dict]] = defaultdict(list)
        for slug, label, polarity, weight in topics:
            if len(topic_map[slug]) < 8:
                topic_map[slug].append({"label": label, "polarity": polarity, "weight": weight})
        radar = [
            {
                "airline": row["airline"],
                "slug": row["slug"],
                "dimensions": {
                    "rating": row["rating_component"],
                    "sentiment": row["sentiment_component"],
                    "recommendation": row["recommendation_component"],
                    "low_severity": 100 - row["complaint_severity"],
                    "low_negativity": 100 - row["topic_negativity"],
                    "recency": row.get("recency_component", 50),
                },
            }
            for row in reputation
        ]
        return {
            "airlines": reputation,
            "topic_heatmap": dict(topic_map),
            "leaders": sorted(reputation, key=lambda row: row["score"], reverse=True)[:5],
            "radar_analytics": radar,
            "comparative_trends": [row.get("timeline", [])[-6:] for row in reputation],
            "category_comparison": {row["slug"]: row.get("categories", {}) for row in reputation},
            "complaint_density": {row["slug"]: row.get("complaint_density", 0) for row in reputation},
            "operational_risk": {
                row["slug"]: round(
                    0.4 * row.get("complaint_density", 0)
                    + 0.35 * row.get("complaint_severity", 0)
                    + 0.25 * row.get("topic_negativity", 0),
                    2,
                )
                for row in reputation
            },
        }


@dataclass(frozen=True)
class RetrievalResult:
    review_id: str
    airline: str
    score: float
    title: str | None
    text: str
    source_url: str | None


class SemanticSearchService:
    """Delegates to enhanced hybrid semantic search."""

    def __init__(self, session: Session) -> None:
        from analytics.semantic_ops import EnhancedSemanticSearchService

        self._service = EnhancedSemanticSearchService(session)

    def search(
        self,
        query: str,
        limit: int = 10,
        *,
        airline_slug: str | None = None,
        category: str | None = None,
        since: date | None = None,
        until: date | None = None,
        threshold: float | None = None,
    ) -> list[dict]:
        return self._service.search(
            query,
            limit=limit,
            airline_slug=airline_slug,
            category=category,
            since=since,
            until=until,
            threshold=threshold,
        )

    def context(self, query: str, limit: int = 5, airline_slug: str | None = None, days: int = 90) -> dict:
        from analytics.constants import BENCHMARK_AIRLINES

        return self._service.context(
            query,
            limit=limit,
            airline_slug=airline_slug,
            compare_slugs=BENCHMARK_AIRLINES,
            days=days,
        )
