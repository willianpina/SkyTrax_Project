from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from api.schemas import (
    AirlineResponse,
    PaginatedReviewsResponse,
    TopicResponse,
)
from database.models import Airline, Review, TopicSnapshot
from database.session import get_session

router = APIRouter(tags=["reviews"])


@router.get("/airlines", response_model=list[AirlineResponse])
def airlines(session: Session = Depends(get_session)) -> list[AirlineResponse]:
    rows = session.query(Airline).order_by(Airline.name.asc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "country": row.country,
            "source": row.source,
            "review_url": row.review_url,
            "is_active": row.is_active,
            "last_scraped_at": row.last_scraped_at,
        }
        for row in rows
    ]


@router.get("/reviews", response_model=PaginatedReviewsResponse)
def reviews(
    airline: str | None = None,
    limit: int = Query(default=50, le=250),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> PaginatedReviewsResponse:
    query = (
        session.query(Review)
        .options(selectinload(Review.airline), selectinload(Review.nlp_result))
        .join(Airline)
        .order_by(Review.review_date.desc().nullslast(), Review.created_at.desc())
    )
    if airline:
        query = query.filter(Airline.slug == airline)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {
        "items": [_review_payload(row) for row in rows],
        "limit": limit,
        "offset": offset,
        "total": total,
        "has_next": offset + limit < total,
    }


@router.get("/topics", response_model=list[TopicResponse])
def topics(
    polarity: str | None = None,
    limit: int = Query(default=50, le=100),
    session: Session = Depends(get_session),
) -> list[TopicResponse]:
    query = session.query(TopicSnapshot).order_by(TopicSnapshot.weight.desc())
    if polarity:
        query = query.filter(TopicSnapshot.polarity == polarity)
    return [
        {
            "id": row.id,
            "airline_id": row.airline_id,
            "label": row.label,
            "polarity": row.polarity,
            "weight": row.weight,
            "sample_size": row.sample_size,
        }
        for row in query.limit(limit).all()
    ]


def _review_payload(review: Review) -> dict:
    return {
        "id": review.id,
        "airline": review.airline.name,
        "source": review.source,
        "source_url": review.source_url,
        "title": review.title,
        "text": review.text,
        "rating": review.rating,
        "recommended": review.recommended,
        "seat_type": review.seat_type,
        "route": review.route,
        "aircraft": review.aircraft,
        "travel_type": review.travel_type,
        "review_date": review.review_date,
        "sentiment": review.nlp_result.sentiment_label if review.nlp_result else None,
        "sentiment_score": review.nlp_result.sentiment_score if review.nlp_result else None,
    }
