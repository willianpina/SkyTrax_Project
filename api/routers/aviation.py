"""Aviation Metadata Intelligence API endpoints."""
from __future__ import annotations


from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_session
from aviation.coverage.engine import CoverageAuditEngine
from aviation.intelligence.service import AviationIntelligenceService
from aviation.graph.context import AviationGraphContext
from aviation.validation.engine import AviationValidator
from analytics.hub_intelligence import HubIntelligenceService
from database.models.aviation import AirlineMetadata, AirportMetadata, AviationCoverageReport

router = APIRouter(prefix="/aviation", tags=["aviation"])

_bootstrap_status = {"running": False, "last_result": None}


def _intel(session: Session = Depends(get_session)) -> AviationIntelligenceService:
    return AviationIntelligenceService(session)


def _hub_intel(session: Session = Depends(get_session)) -> HubIntelligenceService:
    return HubIntelligenceService(session)


def _graph(session: Session = Depends(get_session)) -> AviationGraphContext:
    return AviationGraphContext(session)


def _coverage(session: Session = Depends(get_session)) -> CoverageAuditEngine:
    return CoverageAuditEngine(session)


def _validator(session: Session = Depends(get_session)) -> AviationValidator:
    return AviationValidator(session)


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


@router.get("/coverage")
def coverage_summary(cov: CoverageAuditEngine = Depends(_coverage)):
    return cov.generate_report()


@router.get("/coverage/report")
def coverage_report_history(
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    rows = session.query(AviationCoverageReport).order_by(
        AviationCoverageReport.created_at.desc()
    ).limit(limit).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "total_airlines": r.total_airlines,
            "total_airports": r.total_airports,
            "coverage_score": r.coverage_score,
            "metadata_completeness": r.metadata_completeness,
            "enrichment_score": r.enrichment_score,
            "graph_readiness": r.graph_readiness,
            "duplicate_entities": r.duplicate_entities,
            "orphan_airports": r.orphan_airports,
            "orphan_airlines": r.orphan_airlines,
        }
        for r in rows
    ]


@router.get("/coverage/missing")
def coverage_missing(cov: CoverageAuditEngine = Depends(_coverage)):
    return cov.missing_fields()


@router.get("/coverage/duplicates")
def coverage_duplicates(cov: CoverageAuditEngine = Depends(_coverage)):
    return cov.detect_duplicates()


@router.get("/coverage/orphans")
def coverage_orphans(cov: CoverageAuditEngine = Depends(_coverage)):
    return cov.detect_orphans()


@router.get("/coverage/quality")
def coverage_quality(cov: CoverageAuditEngine = Depends(_coverage)):
    report = cov.generate_report()
    return {
        "coverage_score": report["coverage_score"],
        "metadata_completeness": report["metadata_completeness"],
        "enrichment_score": report["enrichment_score"],
        "graph_readiness": report["graph_readiness"],
    }


@router.get("/bootstrap/status")
def bootstrap_status():
    return _bootstrap_status


@router.post("/bootstrap/run")
def bootstrap_run(background_tasks: BackgroundTasks):
    if _bootstrap_status["running"]:
        return {"status": "already_running"}

    def _run():
        _bootstrap_status["running"] = True
        try:
            from scripts.bootstrap_aviation import run_spiders, run_enrichment_pass, run_coverage_validation
            spiders = run_spiders()
            enrichment = run_enrichment_pass()
            coverage = run_coverage_validation()
            _bootstrap_status["last_result"] = {
                "spiders": spiders, "enrichment": enrichment, "coverage": coverage,
            }
        except Exception as e:
            _bootstrap_status["last_result"] = {"error": str(e)}
        finally:
            _bootstrap_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/validation")
def validation_report(validator: AviationValidator = Depends(_validator)):
    return validator.validate_all()


@router.get("/normalization")
def normalization_report(validator: AviationValidator = Depends(_validator)):
    return validator.normalization_report()


# ═══ Hub Intelligence ═══

@router.get("/hub-intelligence/dashboard")
def hub_intel_dashboard(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.hub_dashboard()


@router.get("/hub-intelligence/rankings")
def hub_intel_rankings(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.hub_rankings()


@router.get("/hub-intelligence/risk")
def hub_intel_risk(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.hub_risk_matrix()


@router.get("/hub-intelligence/alliances")
def hub_intel_alliances(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.alliance_hub_network()


@router.get("/hub-intelligence/incidents")
def hub_intel_incidents(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.airport_incidents()


@router.get("/hub-intelligence/concentration")
def hub_intel_concentration(svc: HubIntelligenceService = Depends(_hub_intel)):
    return svc.hub_concentration()
