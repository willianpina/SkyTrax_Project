from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics.intelligence import SemanticSearchService
from analytics.semantic_ops import SemanticClusterService
from api.schemas import (
    RAGContextResponse,
    SemanticClusterResponse,
    SemanticSearchResultResponse,
)
from app.config import get_settings
from database.session import get_session

router = APIRouter(tags=["search"])


@router.get("/semantic-search", response_model=list[SemanticSearchResultResponse])
def semantic_search(
    q: str = Query(min_length=2, max_length=240),
    limit: int = Query(default=10, ge=1, le=50),
    airline: str | None = None,
    category: str | None = None,
    since: date | None = None,
    until: date | None = None,
    threshold: float | None = Query(default=None, ge=0, le=1),
    session: Session = Depends(get_session),
) -> list[SemanticSearchResultResponse]:
    settings = get_settings()
    return SemanticSearchService(session).search(
        q,
        limit=limit,
        airline_slug=airline,
        category=category,
        since=since,
        until=until,
        threshold=threshold if threshold is not None else settings.semantic_similarity_threshold,
    )


@router.get("/semantic-clusters", response_model=list[SemanticClusterResponse])
def semantic_clusters(
    airline: str | None = None,
    session: Session = Depends(get_session),
) -> list[SemanticClusterResponse]:
    return SemanticClusterService(session).list_clusters(airline_slug=airline)


@router.get("/rag/context", response_model=RAGContextResponse)
def rag_context(
    q: str = Query(min_length=2, max_length=240),
    limit: int = Query(default=5, ge=1, le=20),
    airline: str | None = None,
    days: int = Query(default=90, ge=7, le=365),
    session: Session = Depends(get_session),
) -> RAGContextResponse:
    return SemanticSearchService(session).context(q, limit=limit, airline_slug=airline, days=days)
