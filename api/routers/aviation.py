"""Aviation Metadata Intelligence API endpoints."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_session
from aviation.coverage.engine import CoverageAuditEngine
from aviation.intelligence.service import AviationIntelligenceService
from aviation.graph.context import AviationGraphContext
from aviation.validation.engine import AviationValidator
from analytics.hub_intelligence import HubIntelligenceService
from aviation.domain_audit import log_domain
from database.models.aviation import AirportMetadata, AviationCoverageReport

router = APIRouter(prefix="/aviation", tags=["aviation"])

_bootstrap_status = {"running": False, "last_result": None}


def _record_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        if "airlines" in payload:
            return sum(
                len(payload[k]) if isinstance(payload.get(k), list) else 0
                for k in ("airlines", "airports", "alliances", "hubs")
            )
        for key in ("active_hubs", "total_airlines", "airports_monitored", "total_airports"):
            if key in payload and isinstance(payload[key], int):
                return int(payload[key])
        return len(payload)
    return 0


def _audit_response(domain: str, endpoint: str, payload: Any, started: float) -> Any:
    body = json.dumps(payload, default=str)
    log_domain(
        domain,
        endpoint=endpoint,
        records_returned=_record_count(payload),
        query_time_ms=round((time.perf_counter() - started) * 1000, 1),
        response_size=len(body.encode("utf-8")),
    )
    return payload


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


def _airport_rows(session: Session, limit: int) -> list[dict]:
    rows = (
        session.query(AirportMetadata)
        .order_by(AirportMetadata.airport_rating.desc().nullslast())
        .limit(limit)
        .all()
    )
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


@router.get("/catalog")
def aviation_catalog(
    airline_limit: int = Query(100, ge=1, le=200),
    airport_limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
    intel: AviationIntelligenceService = Depends(_intel),
):
    """Single round-trip bundle for Aviation workspace (avoids DB pool exhaustion)."""
    started = time.perf_counter()
    meta = intel.metadata_summary()
    airlines = intel._operational_airline_rows(limit=airline_limit)
    airports = _airport_rows(session, airport_limit)
    alliances = intel.alliance_intelligence()
    hubs = intel.hub_intelligence()

    payload = {
        "metadata": meta,
        "airlines": airlines,
        "airports": airports,
        "alliances": alliances,
        "hubs": hubs,
    }
    log_domain(
        "AVIATION",
        endpoint="/aviation/catalog",
        records_found=meta.get("airlines_total", 0) + meta.get("airports_total", 0),
        records_returned=len(airlines) + len(airports) + len(alliances) + len(hubs),
        query_time_ms=round((time.perf_counter() - started) * 1000, 1),
        response_size=len(json.dumps(payload, default=str).encode("utf-8")),
        extra={
            "airlines": len(airlines),
            "airports": len(airports),
            "alliances": len(alliances),
            "hubs": len(hubs),
            **{k: meta.get(k) for k in ("airlines_total", "airports_total", "alliances_total", "hubs_total")},
        },
    )
    return payload


@router.get("/airlines")
def list_airlines(
    limit: int = Query(50, ge=1, le=200),
    intel: AviationIntelligenceService = Depends(_intel),
):
    rows = intel._operational_airline_rows(limit=limit)
    log_domain("AVIATION", endpoint="/aviation/airlines", records_returned=len(rows))
    return rows


@router.get("/airports")
def list_airports(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    rows = _airport_rows(session, limit)
    log_domain("AVIATION", endpoint="/aviation/airports", records_returned=len(rows))
    return rows


@router.get("/alliances")
def list_alliances(intel: AviationIntelligenceService = Depends(_intel)):
    started = time.perf_counter()
    rows = intel.alliance_intelligence()
    return _audit_response("ALLIANCES", "/aviation/alliances", rows, started)


@router.get("/hubs")
def list_hubs(intel: AviationIntelligenceService = Depends(_intel)):
    started = time.perf_counter()
    rows = intel.hub_intelligence()
    return _audit_response("HUBS", "/aviation/hubs", rows, started)


@router.get("/regions")
def list_regions(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.regional_intelligence()


@router.get("/premium")
def list_premium(intel: AviationIntelligenceService = Depends(_intel)):
    return intel.premium_intelligence()


@router.get("/metadata")
def metadata_summary(intel: AviationIntelligenceService = Depends(_intel)):
    meta = intel.metadata_summary()
    log_domain(
        "AVIATION",
        endpoint="/aviation/metadata",
        records_returned=meta.get("airlines_total", 0),
        extra=meta,
    )
    return meta


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
    started = time.perf_counter()
    report = cov.generate_report()
    return _audit_response("COVERAGE", "/aviation/coverage", report, started)


@router.get("/coverage/report")
def coverage_report_history(
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
):
    rows = (
        session.query(AviationCoverageReport)
        .order_by(AviationCoverageReport.created_at.desc())
        .limit(limit)
        .all()
    )
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


@router.post("/propagate")
def propagate_domains(session: Session = Depends(get_session)):
    """Sync core airlines into aviation metadata, hubs, alliances (idempotent)."""
    from aviation.operational_propagation import propagate_operational_domains

    return propagate_operational_domains(session, commit=True)


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
                "spiders": spiders,
                "enrichment": enrichment,
                "coverage": coverage,
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


@router.get("/hubs/metrics")
def hubs_metrics(
    session: Session = Depends(get_session),
    svc: HubIntelligenceService = Depends(_hub_intel),
):
    """Hub classification coverage for dashboards."""
    from sqlalchemy import func

    dash = svc.hub_dashboard()
    by_class = dict(
        session.query(AirportMetadata.hub_level, func.count(AirportMetadata.id))
        .filter(AirportMetadata.hub_level.isnot(None))
        .group_by(AirportMetadata.hub_level)
        .all()
    )
    return {
        "total_airports": dash.get("airports_monitored", 0),
        "classified_hubs": dash.get("classified_hubs", 0),
        "coverage_percent": dash.get("coverage_percent", 0.0),
        "active_hubs": dash.get("active_hubs", 0),
        "by_class": by_class,
    }


@router.post("/hubs/enrich")
def hubs_enrich(session: Session = Depends(get_session)):
    """Run automatic hub classification (reviews + airline links + alliances)."""
    from aviation.hub_enrichment import enrich_hub_classifications

    return enrich_hub_classifications(session, commit=True)


@router.get("/hub-intelligence/dashboard")
def hub_intel_dashboard(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    payload = svc.hub_dashboard()
    return _audit_response("HUBS", "/aviation/hub-intelligence/dashboard", payload, started)


@router.get("/hub-intelligence/rankings")
def hub_intel_rankings(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    return _audit_response("HUBS", "/aviation/hub-intelligence/rankings", svc.hub_rankings(), started)


@router.get("/hub-intelligence/risk")
def hub_intel_risk(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    return _audit_response("HUBS", "/aviation/hub-intelligence/risk", svc.hub_risk_matrix(), started)


@router.get("/hub-intelligence/alliances")
def hub_intel_alliances(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    return _audit_response("HUBS", "/aviation/hub-intelligence/alliances", svc.alliance_hub_network(), started)


@router.get("/hub-intelligence/incidents")
def hub_intel_incidents(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    return _audit_response("HUBS", "/aviation/hub-intelligence/incidents", svc.airport_incidents(), started)


@router.get("/hub-intelligence/concentration")
def hub_intel_concentration(svc: HubIntelligenceService = Depends(_hub_intel)):
    started = time.perf_counter()
    return _audit_response("HUBS", "/aviation/hub-intelligence/concentration", svc.hub_concentration(), started)
