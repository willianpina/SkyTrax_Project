from __future__ import annotations

from sqlalchemy import Integer, desc, func
from sqlalchemy.orm import Session

from database.models import Airline, NLPResult, Review, TopicSnapshot


class AnalyticsService:
    """Read-optimized analytics queries for executive dashboards."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def executive_summary(self, airline_slug: str | None = None) -> dict:
        review_query = self.session.query(Review).join(Airline)
        sentiment_query = self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id)).join(Review).join(Airline)

        if airline_slug:
            review_query = review_query.filter(Airline.slug == airline_slug)
            sentiment_query = sentiment_query.filter(Airline.slug == airline_slug)

        avg_rating = review_query.with_entities(func.avg(Review.rating)).scalar()
        review_count = review_query.with_entities(func.count(Review.id)).scalar() or 0
        recommendation_rate = review_query.with_entities(
            func.avg(func.cast(Review.recommended, Integer))
        ).scalar()

        sentiment = {
            label: count
            for label, count in sentiment_query.group_by(NLPResult.sentiment_label).all()
        }

        return {
            "average_rating": round(float(avg_rating or 0), 2),
            "review_count": int(review_count),
            "recommendation_rate": round(float(recommendation_rate or 0), 3),
            "sentiment_distribution": sentiment,
            "timeline": self.rating_timeline(airline_slug),
            "top_positive_topics": self.top_topics("positive", airline_slug),
            "top_negative_topics": self.top_topics("negative", airline_slug),
        }

    def sentiment_summary(self, airline_slug: str | None = None) -> dict:
        query = self.session.query(NLPResult.sentiment_label, func.count(NLPResult.id)).join(Review).join(Airline)
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        distribution = {label: count for label, count in query.group_by(NLPResult.sentiment_label).all()}
        total = sum(distribution.values()) or 1
        return {
            "distribution": distribution,
            "positive_share": round(distribution.get("positive", 0) / total, 4),
            "negative_share": round(distribution.get("negative", 0) / total, 4),
        }

    def airline_rankings(self) -> list[dict]:
        rows = (
            self.session.query(
                Airline.name,
                Airline.slug,
                func.avg(Review.rating).label("average_rating"),
                func.count(Review.id).label("review_count"),
                func.avg(func.cast(Review.recommended, Integer)).label("recommendation_rate"),
            )
            .join(Review)
            .group_by(Airline.id)
            .order_by(desc("average_rating"))
            .all()
        )
        return [
            {
                "name": name,
                "slug": slug,
                "average_rating": round(float(avg or 0), 2),
                "review_count": int(count or 0),
                "recommendation_rate": round(float(recommendation or 0), 3),
            }
            for name, slug, avg, count, recommendation in rows
        ]

    def rating_timeline(self, airline_slug: str | None = None) -> list[dict]:
        query = (
            self.session.query(
                func.date_trunc("month", Review.review_date).label("month"),
                func.avg(Review.rating),
                func.count(Review.id),
            )
            .join(Airline)
            .filter(Review.review_date.isnot(None))
        )
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        return [
            {"month": str(month.date()), "average_rating": round(float(avg or 0), 2), "count": int(count)}
            for month, avg, count in query.group_by("month").order_by("month").all()
        ]

    def top_topics(self, polarity: str, airline_slug: str | None = None) -> list[dict]:
        query = self.session.query(TopicSnapshot).filter(TopicSnapshot.polarity == polarity)
        if airline_slug:
            query = query.join(Airline, TopicSnapshot.airline_id == Airline.id).filter(Airline.slug == airline_slug)
        return [
            {"label": row.label, "weight": row.weight, "sample_size": row.sample_size}
            for row in query.order_by(TopicSnapshot.weight.desc()).limit(8).all()
        ]
