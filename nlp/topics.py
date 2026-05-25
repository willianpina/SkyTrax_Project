from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from database.models import Airline, NLPResult, Review, TopicSnapshot


class TopicModelingService:
    """Topic snapshot generation with a lightweight fallback before BERTopic training."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def refresh_snapshots(self) -> int:
        self.session.query(TopicSnapshot).delete()
        inserted = 0
        airlines = self.session.query(Airline).all()
        for airline in airlines:
            for polarity in ("positive", "negative"):
                rows = (
                    self.session.query(NLPResult)
                    .join(Review)
                    .filter(Review.airline_id == airline.id, NLPResult.sentiment_label == polarity)
                    .all()
                )
                counter: Counter[str] = Counter()
                for row in rows:
                    counter.update(row.topics)
                for label, count in counter.most_common(10):
                    self.session.add(
                        TopicSnapshot(
                            airline_id=airline.id,
                            label=label,
                            polarity=polarity,
                            weight=float(count),
                            sample_size=len(rows),
                        )
                    )
                    inserted += 1
        self.session.commit()
        return inserted
