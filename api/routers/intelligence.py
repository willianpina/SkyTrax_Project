from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics.insights_engine import ExecutiveInsightEngine
from analytics.intelligence import (
    BenchmarkingService,
    ExecutiveInsightService,
    ReputationService,
)
from analytics.operational_intelligence import OperationalIntelligenceService
from analytics.snapshots import SnapshotService
from api.schemas import (
    BenchmarkingResponse,
    ExecutiveInsightResponse,
    MetricSnapshotResponse,
    ReputationScoreResponse,
)
from database.session import get_session

router = APIRouter(tags=["intelligence"])


@router.get("/reputation", response_model=list[ReputationScoreResponse])
def reputation(session: Session = Depends(get_session)) -> list[ReputationScoreResponse]:
    return ReputationService(session).airline_scores()


@router.get("/reputation/{airline_slug}", response_model=ReputationScoreResponse)
def airline_reputation(airline_slug: str, session: Session = Depends(get_session)) -> ReputationScoreResponse:
    return ReputationService(session).score_airline(airline_slug)


@router.get("/benchmarking", response_model=BenchmarkingResponse)
def benchmarking(session: Session = Depends(get_session)) -> BenchmarkingResponse:
    return BenchmarkingService(session).compare()


@router.get("/insights", response_model=list[ExecutiveInsightResponse])
def insights(session: Session = Depends(get_session)) -> list[ExecutiveInsightResponse]:
    return ExecutiveInsightService(session).generate()


@router.get("/snapshots", response_model=list[MetricSnapshotResponse])
def snapshots(
    airline: str | None = None,
    snapshot_type: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[MetricSnapshotResponse]:
    return SnapshotService(session).list_snapshots(
        airline_slug=airline,
        snapshot_type=snapshot_type,
        limit=limit,
    )


@router.post("/insights/refresh", response_model=dict)
def refresh_insights(session: Session = Depends(get_session)) -> dict:
    return ExecutiveInsightEngine(session).generate_and_persist()


# ── Operational Intelligence endpoints ──────────────────────────────────

@router.get("/operational/dashboard")
def operational_dashboard(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session).operational_dashboard()


@router.get("/operational/risk")
def operational_risk(session: Session = Depends(get_session)):
    svc = OperationalIntelligenceService(session)
    airlines = svc._airlines_with_reviews()
    slugs = [a["slug"] for a in airlines]
    return svc._operational_risk_ranking(slugs)


@router.get("/operational/complaints")
def complaint_heatmap(session: Session = Depends(get_session)):
    svc = OperationalIntelligenceService(session)
    airlines = svc._airlines_with_reviews()
    slugs = [a["slug"] for a in airlines[:20]]
    return svc._complaint_heatmap(slugs)


@router.get("/operational/routes")
def route_intelligence(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session)._route_intelligence()


@router.get("/operational/deterioration")
def deterioration_alerts(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session)._deterioration_alerts()


@router.get("/operational/premium")
def premium_dissatisfaction(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session)._premium_dissatisfaction()


@router.get("/operational/cabins")
def cabin_analysis(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session)._cabin_class_analysis()


@router.get("/operational/alliance-risk")
def alliance_risk(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session).alliance_risk()


@router.get("/operational/airport-friction")
def airport_friction(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session).airport_friction()


@router.get("/operational/transfer-bottlenecks")
def transfer_bottlenecks(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session).transfer_bottlenecks()


@router.get("/operational/signals")
def executive_signals(session: Session = Depends(get_session)):
    return OperationalIntelligenceService(session)._executive_signals()


@router.get("/operational/rankings")
def airline_rankings(
    limit: int = Query(default=30, le=100),
    session: Session = Depends(get_session),
):
    return OperationalIntelligenceService(session)._airline_rankings(limit=limit)


@router.get("/graph/stats")
def graph_stats(session: Session = Depends(get_session)):
    from analytics.knowledge_graph import AviationKnowledgeGraph
    return AviationKnowledgeGraph(session).get_stats()


@router.get("/fusion/signals")
def fusion_signals(
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
):
    from database.models.graph import FusionSignal
    rows = (
        session.query(FusionSignal)
        .filter(FusionSignal.is_active.is_(True))
        .order_by(FusionSignal.confidence.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "category": s.category,
            "severity": s.severity,
            "title": s.title,
            "description": s.description,
            "entities": s.entities,
            "evidence": s.evidence,
            "confidence": s.confidence,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        }
        for s in rows
    ]


@router.get("/fusion/disruptions")
def disruption_summary(session: Session = Depends(get_session)):
    from sqlalchemy import func
    from database.models.graph import ReviewIntelligence
    total = session.query(func.count(ReviewIntelligence.id)).scalar() or 0
    severities = dict(
        session.query(ReviewIntelligence.operational_severity, func.count(ReviewIntelligence.id))
        .group_by(ReviewIntelligence.operational_severity).all()
    )
    return {
        "total_analyzed": total,
        "severity_distribution": severities,
    }
