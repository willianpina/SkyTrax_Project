from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics.insights_engine import ExecutiveInsightEngine
from analytics.intelligence import (
    BenchmarkingService,
    ExecutiveInsightService,
    ReputationService,
)
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
