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
from aviation.enrichment.pipeline import ReviewEnrichmentPipeline
from aviation.normalization.engine import NormalizationEngine
from database.models.aviation import AirportMetadata
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


@router.get("/semantic-search/enriched")
def semantic_search_enriched(
    q: str = Query(min_length=2, max_length=240),
    limit: int = Query(default=10, ge=1, le=50),
    airline: str | None = None,
    session: Session = Depends(get_session),
):
    """Semantic search with aviation metadata enrichment overlay."""
    settings = get_settings()
    results = SemanticSearchService(session).search(
        q,
        limit=limit,
        airline_slug=airline,
        threshold=settings.semantic_similarity_threshold,
    )

    enricher = ReviewEnrichmentPipeline(session)
    normalizer = NormalizationEngine(session)
    enriched = []

    airport_context = None
    tokens = q.split()
    for token in tokens:
        norm = normalizer.normalize_airport(token)
        if norm.entity_id:
            ap = session.query(AirportMetadata).get(norm.entity_id)
            if ap:
                airport_context = {
                    "name": ap.airport_name,
                    "iata": ap.iata,
                    "country": ap.country,
                    "region": ap.region,
                    "hub_level": ap.hub_level,
                    "airport_rating": ap.airport_rating,
                }
                break

    for r in results:
        data = r if isinstance(r, dict) else r.model_dump() if hasattr(r, "model_dump") else r.__dict__
        airline_slug = data.get("airline_slug") or data.get("airline", "")
        enrichment = enricher.enrich(
            airline_slug,
            route=data.get("route"),
            text=data.get("text", data.get("snippet", "")),
        )
        data["aviation_context"] = {
            "airline_canonical": enrichment.airline_canonical,
            "alliance": enrichment.alliance,
            "airline_type": enrichment.airline_type,
            "star_rating": enrichment.star_rating,
            "airports_detected": enrichment.airports_detected[:3],
            "region": enrichment.region,
            "enrichment_confidence": enrichment.enrichment_confidence,
        }
        enriched.append(data)

    return {
        "results": enriched,
        "query_airport_context": airport_context,
        "total": len(enriched),
    }
