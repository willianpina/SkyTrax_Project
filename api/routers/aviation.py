"""Aviation Metadata Intelligence API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_session
from aviation.intelligence.service import AviationIntelligenceService
from aviation.graph.context import AviationGraphContext
from database.models.aviation import AirlineMetadata, AirportMetadata

router = APIRouter(prefix="/aviation", tags=["aviation"])


def _intel(session: Session = Depends(get_session)) -> AviationIntelligenceService:
    return AviationIntelligenceService(session)


def _graph(session: Session = Depends(get_session)) -> AviationGraphContext:
    return AviationGraphContext(session)


@router.get("/airlines")
def list_airlines(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    rows = session.query(AirlineMetadata).order_by(
        AirlineMetadata.star_rating.desc().nullslast()
    ).limit(limit).all()
    return [
        {
            "slug": r.slug,
            "name": r.airline_name,
            "country": r.country,
            "airline_type": r.airline_type,
            "star_rating": r.star_rating,
            "is_premium": r.is_premium,
            "is_low_cost": r.is_low_cost,
            "alliance": r.alliance_rel.name if r.alliance_rel else None,
            "hub_airports": r.hub_airports,
            "enrichment_confidence": r.enrichment_confidence,
        }
        for r in rows
    ]


@router.get("/airports")
def list_airports(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    rows = session.query(AirportMetadata).order_by(
        AirportMetadata.airport_rating.desc().nullslast()
    ).limit(limit).all()
    return [
        {
            "iata": r.iata,
            "name": r.airport_name,
            "city": r.city,
            "country": r.country,
            "region": r.region,
            "airport_rating": r.airport_rating,
            "hub_level": r.hub_level,
            "latitude": r.latitude,
            "longitude": r.longitude,
        }
        for r in rows
    ]


@router.get("/alliances")
def list_alliances(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.alliance_intelligence()


@router.get("/hubs")
def list_hubs(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.hub_intelligence()


@router.get("/regions")
def list_regions(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.regional_intelligence()


@router.get("/premium")
def list_premium(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.premium_intelligence()


@router.get("/metadata")
def metadata_summary(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.metadata_summary()


@router.get("/airline/{slug}")
def airline_detail(slug: str, intel: AviationIntelligenceService = Depends(_intel)):
    result = intel.airline_detail(slug)
    if not result:
        return {"error": "airline_not_found", "slug": slug}
    return result


@router.get("/airport/{iata}")
def airport_detail(iata: str, intel: AviationIntelligenceService = Depends(_intel)):
    result = intel.airport_detail(iata)
    if not result:
        return {"error": "airport_not_found", "iata": iata}
    return result


@router.get("/graph/context")
def graph_context(
    airline: str | None = Query(None),
    airport: str | None = Query(None),
    graph: AviationGraphContext = Depends(_graph),
):
    if airline:
        return graph.airline_context(airline)
    if airport:
        return graph.airport_context(airport)
    return {"error": "provide airline slug or airport IATA code"}
