from __future__ import annotations

import logging
import re
from datetime import date

from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from database.models import Airline, NLPResult, ReputationScoreHistory, Review, TopicSnapshot
from database.models.aviation import AirlineMetadata

logger = logging.getLogger(__name__)


SEVERITY_TERMS = {
    "cancelled": 1.0,
    "refund": 0.9,
    "lost": 0.9,
    "rude": 0.7,
    "delayed": 0.6,
    "dirty": 0.5,
    "uncomfortable": 0.45,
}


class ReputationService:
    """Composite reputation scoring for executive airline benchmarking."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def airline_scores(self, min_reviews: int = 1) -> list[dict]:
        """Return scores only for airlines with at least min_reviews reviews."""
        total_airlines = self.session.query(Airline).count()
        slugs_with_reviews = (
            self.session.query(Airline.slug)
            .join(Review, Review.airline_id == Airline.id)
            .group_by(Airline.slug)
            .having(func.count(Review.id) >= min_reviews)
            .all()
        )
        logger.info(
            "[OPS][REPUTATION] airline_scores total_airlines=%d with_reviews=%d min_reviews=%d",
            total_airlines, len(slugs_with_reviews), min_reviews,
        )
        scored = [self.score_airline(slug) for (slug,) in slugs_with_reviews]
        return sorted(scored, key=lambda r: r["score"], reverse=True)

    def _get_metadata(self, airline_slug: str) -> dict:
        """Fetch enrichment metadata (country, alliance, star_rating) from AirlineMetadata."""
        meta = self.session.query(AirlineMetadata).filter(AirlineMetadata.slug == airline_slug).first()
        if not meta:
            airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
            country = airline.country if airline else None
            return {"country": country, "alliance": None, "star_rating": None, "airline_type": None}
        alliance_name = None
        if meta.alliance_rel:
            alliance_name = meta.alliance_rel.name
        return {
            "country": meta.country,
            "alliance": alliance_name,
            "star_rating": meta.star_rating,
            "airline_type": meta.airline_type,
        }

    def score_airline(self, airline_slug: str) -> dict:
        rows = (
            self.session.query(Review, NLPResult)
            .join(Airline)
            .outerjoin(NLPResult, NLPResult.review_id == Review.id)
            .filter(Airline.slug == airline_slug)
            .all()
        )
        airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
        metadata = self._get_metadata(airline_slug)
        if not rows:
            return {
                "airline": airline.name if airline else airline_slug,
                "slug": airline_slug,
                "score": 0.0,
                "rating_component": 0.0,
                "sentiment_component": 0.0,
                "recommendation_component": 0.0,
                "complaint_severity": 0.0,
                "topic_negativity": 0.0,
                "recency_component": 0.0,
                "complaint_density": 0.0,
                "review_count": 0,
                "timeline": [],
                "categories": {},
                "history": [],
                **metadata,
            }

        ratings = [review.rating for review, _ in rows if review.rating is not None]
        rating_component = (sum(ratings) / len(ratings) / 10) if ratings else 0
        recommendation_values = [1 if review.recommended else 0 for review, _ in rows if review.recommended is not None]
        recommendation_component = sum(recommendation_values) / len(recommendation_values) if recommendation_values else 0
        sentiment_component = self._sentiment_component([nlp.sentiment_label for _, nlp in rows if nlp])
        complaint_severity = self._complaint_severity([review.text for review, _ in rows])
        topic_negativity = self._topic_negativity(airline.id if airline else None)
        recency_component = self._recency_component([review for review, _ in rows])
        complaint_density = self._complaint_density(rows)
        score = (
            0.30 * rating_component
            + 0.22 * sentiment_component
            + 0.18 * recommendation_component
            + 0.10 * (1 - complaint_severity)
            + 0.08 * (1 - topic_negativity)
            + 0.07 * recency_component
            + 0.05 * (1 - complaint_density)
        )

        negative_reviews = sum(1 for _, nlp in rows if nlp and nlp.sentiment_label == "negative")
        complaint_count = sum(1 for review, _ in rows if review.recommended is False)
        nlp_coverage = sum(1 for _, nlp in rows if nlp)

        logger.debug(
            "[OPS][SCORE_ENGINE] airline=%s reviews=%d complaints=%d negative=%d "
            "nlp_coverage=%d ars=%.1f country=%s",
            airline_slug, len(rows), complaint_count, negative_reviews,
            nlp_coverage, round(score * 100, 2), metadata.get("country"),
        )

        return {
            "airline": airline.name if airline else airline_slug,
            "slug": airline_slug,
            "score": round(score * 100, 2),
            "rating_component": round(rating_component * 100, 2),
            "sentiment_component": round(sentiment_component * 100, 2),
            "recommendation_component": round(recommendation_component * 100, 2),
            "complaint_severity": round(complaint_severity * 100, 2),
            "topic_negativity": round(topic_negativity * 100, 2),
            "recency_component": round(recency_component * 100, 2),
            "complaint_density": round(complaint_density * 100, 2),
            "review_count": len(rows),
            "complaint_count": complaint_count,
            "negative_count": negative_reviews,
            "timeline": self.temporal_score(airline_slug),
            "categories": self.category_scores(airline_slug),
            "history": self.score_history(airline_slug, limit=24),
            **metadata,
        }

    def persist_scores(self) -> int:
        """Persist current ARS for all active airlines."""
        airlines = self.session.query(Airline).filter(Airline.is_active.is_(True)).all()
        count = 0
        for airline in airlines:
            score = self.score_airline(airline.slug)
            if score["review_count"] == 0:
                continue
            self.session.add(
                ReputationScoreHistory(
                    airline_id=airline.id,
                    score=score["score"],
                    components={
                        "rating_component": score["rating_component"],
                        "sentiment_component": score["sentiment_component"],
                        "recommendation_component": score["recommendation_component"],
                        "complaint_severity": score["complaint_severity"],
                        "topic_negativity": score["topic_negativity"],
                        "recency_component": score["recency_component"],
                        "complaint_density": score["complaint_density"],
                    },
                )
            )
            for category, value in score.get("categories", {}).items():
                self.session.add(
                    ReputationScoreHistory(
                        airline_id=airline.id,
                        score=float(value),
                        category=category,
                        components={"source": "seat_type"},
                    )
                )
            count += 1
        self.session.commit()
        return count

    def score_history(self, airline_slug: str, limit: int = 30) -> list[dict]:
        airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
        if not airline:
            return []
        rows = (
            self.session.query(ReputationScoreHistory)
            .filter(ReputationScoreHistory.airline_id == airline.id, ReputationScoreHistory.category.is_(None))
            .order_by(ReputationScoreHistory.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "score": row.score,
                "recorded_at": row.recorded_at.isoformat(),
                "components": row.components,
            }
            for row in reversed(rows)
        ]

    def temporal_score(self, airline_slug: str) -> list[dict]:
        rows = (
            self.session.query(
                func.date_trunc("month", Review.review_date).label("month"),
                func.avg(Review.rating).label("avg_rating"),
                func.avg(func.cast(Review.recommended, Integer)).label("recommendation_rate"),
                func.count(Review.id).label("review_count"),
            )
            .join(Airline)
            .filter(Airline.slug == airline_slug, Review.review_date.isnot(None))
            .group_by("month")
            .order_by("month")
            .all()
        )
        return [
            {
                "period": str(month.date()),
                "score": round((((avg_rating or 0) / 10) * 0.7 + float(recommendation_rate or 0) * 0.3) * 100, 2),
                "review_count": int(review_count),
            }
            for month, avg_rating, recommendation_rate, review_count in rows
        ]

    def category_scores(self, airline_slug: str) -> dict[str, float]:
        rows = (
            self.session.query(Review.seat_type, func.avg(Review.rating), func.count(Review.id))
            .join(Airline)
            .filter(Airline.slug == airline_slug, Review.seat_type.isnot(None))
            .group_by(Review.seat_type)
            .all()
        )
        return {seat_type: round(float(avg or 0) * 10, 2) for seat_type, avg, _ in rows}

    @staticmethod
    def _sentiment_component(labels: list[str]) -> float:
        if not labels:
            return 0.5
        weights = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}
        return sum(weights.get(label, 0.5) for label in labels) / len(labels)

    @staticmethod
    def _complaint_severity(texts: list[str]) -> float:
        if not texts:
            return 0
        total = 0.0
        for text in texts:
            tokens = set(re.findall(r"[a-z']+", text.lower()))
            total += min(sum(SEVERITY_TERMS[token] for token in tokens if token in SEVERITY_TERMS), 2.5) / 2.5
        return total / len(texts)

    @staticmethod
    def _recency_component(reviews: list[Review]) -> float:
        if not reviews:
            return 0.5
        today = date.today()
        weights = []
        for review in reviews:
            if not review.review_date:
                weights.append(0.5)
                continue
            age_days = max((today - review.review_date).days, 0)
            weights.append(max(0.2, 1 - min(age_days / 365, 1)))
        return sum(weights) / len(weights)

    @staticmethod
    def _complaint_density(rows: list[tuple[Review, NLPResult | None]]) -> float:
        if not rows:
            return 0.0
        complaints = sum(1 for review, _ in rows if review.recommended is False)
        negative_nlp = sum(1 for _, nlp in rows if nlp and nlp.sentiment_label == "negative")
        return min((complaints + negative_nlp * 0.5) / len(rows), 1.0)

    def _topic_negativity(self, airline_id: str | None) -> float:
        if not airline_id:
            return 0
        negative_weight = (
            self.session.query(func.sum(TopicSnapshot.weight))
            .filter(TopicSnapshot.airline_id == airline_id, TopicSnapshot.polarity == "negative")
            .scalar()
            or 0
        )
        total_weight = (
            self.session.query(func.sum(TopicSnapshot.weight)).filter(TopicSnapshot.airline_id == airline_id).scalar() or 0
        )
        return float(negative_weight) / float(total_weight) if total_weight else 0


class ExecutiveInsightService:
    """Facade over persisted executive insights with on-demand fallback."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def generate(self) -> list[dict]:
        from analytics.insights_engine import ExecutiveInsightEngine

        persisted = ExecutiveInsightEngine(self.session).list_recent(limit=30)
        if persisted:
            return persisted
        return self._fallback_generate()

    def _fallback_generate(self) -> list[dict]:
        insights: list[dict] = []
        for score in ReputationService(self.session).airline_scores():
            if score["review_count"] == 0:
                continue
            if score["score"] < 55:
                insights.append(
                    {
                        "severity": "high",
                        "airline": score["airline"],
                        "summary": f"{score['airline']} shows elevated reputation risk with a score of {score['score']}.",
                        "drivers": ["rating", "recommendation", "complaint severity"],
                    }
                )
            elif score["score"] >= 75:
                insights.append(
                    {
                        "severity": "positive",
                        "airline": score["airline"],
                        "summary": f"{score['airline']} is outperforming the tracked peer set with a score of {score['score']}.",
                        "drivers": ["rating", "recommendation"],
                    }
                )
        return insights[:20]
