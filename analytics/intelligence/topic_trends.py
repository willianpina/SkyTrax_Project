from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from database.models import Airline, NLPResult, Review


class TopicTrendService:
    """Detect emerging and deteriorating topic signals from NLP snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def trends(self, airline_slug: str | None = None, days: int = 90) -> list[dict]:
        since = date.today() - timedelta(days=days)
        query = self.session.query(Review, NLPResult).join(NLPResult).filter(Review.review_date >= since)
        if airline_slug:
            query = query.join(Airline).filter(Airline.slug == airline_slug)
        current: Counter[str] = Counter()
        previous: Counter[str] = Counter()
        midpoint = date.today() - timedelta(days=days // 2)
        for review, nlp in query.all():
            target = current if review.review_date and review.review_date >= midpoint else previous
            target.update(nlp.topics)
        labels = set(current) | set(previous)
        rows = []
        for label in labels:
            old = previous.get(label, 0)
            new = current.get(label, 0)
            growth = (new - old) / max(old, 1)
            if new or old:
                rows.append(
                    {"topic": label, "current": new, "previous": old, "growth_rate": round(growth, 4)}
                )
        return sorted(rows, key=lambda row: row["growth_rate"], reverse=True)[:25]
