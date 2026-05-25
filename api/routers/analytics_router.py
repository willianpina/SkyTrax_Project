from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics.intelligence import TopicTrendService
from analytics.service import AnalyticsService
from api.schemas import (
    AnalyticsSummaryResponse,
    RankingResponse,
    SentimentSummaryResponse,
    TopicTrendResponse,
)
from database.session import get_session

router = APIRouter(tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsSummaryResponse)
def analytics(airline: str | None = None, session: Session = Depends(get_session)) -> AnalyticsSummaryResponse:
    return AnalyticsService(session).executive_summary(airline_slug=airline)


@router.get("/rankings", response_model=list[RankingResponse])
def rankings(session: Session = Depends(get_session)) -> list[RankingResponse]:
    return AnalyticsService(session).airline_rankings()


@router.get("/sentiment", response_model=SentimentSummaryResponse)
def sentiment(airline: str | None = None, session: Session = Depends(get_session)) -> SentimentSummaryResponse:
    return AnalyticsService(session).sentiment_summary(airline_slug=airline)


@router.get("/topic-trends", response_model=list[TopicTrendResponse])
def topic_trends(
    airline: str | None = None,
    days: int = Query(default=90, ge=14, le=365),
    session: Session = Depends(get_session),
) -> list[TopicTrendResponse]:
    return TopicTrendService(session).trends(airline_slug=airline, days=days)
