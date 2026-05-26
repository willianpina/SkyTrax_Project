from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.data_quality import DataQualityMonitor
from api.schemas import (
    DataQualityReportResponse,
    SchedulerStatusResponse,
)
from database.models import Airline, NLPResult, Review, ScheduledJob
from database.models.aviation import AirlineMetadata
from database.session import get_session

router = APIRouter(tags=["admin"])


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
def scheduler_status(session: Session = Depends(get_session)) -> SchedulerStatusResponse:
    rows = session.query(ScheduledJob).order_by(ScheduledJob.job_name.asc()).all()
    return {
        "jobs": [
            {
                "job_name": row.job_name,
                "status": row.status,
                "last_started_at": row.last_started_at.isoformat() if row.last_started_at else None,
                "last_finished_at": row.last_finished_at.isoformat() if row.last_finished_at else None,
                "last_error": row.last_error,
                "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
                "run_count": row.run_count,
            }
            for row in rows
        ]
    }


@router.get("/data-quality", response_model=list[DataQualityReportResponse])
def data_quality(
    limit: int = Query(default=20, le=100),
    session: Session = Depends(get_session),
) -> list[DataQualityReportResponse]:
    return DataQualityMonitor(session).list_reports(limit=limit)


@router.get("/reputation/diagnostics")
def reputation_diagnostics(session: Session = Depends(get_session)) -> dict:
    """Pipeline diagnostics for reputation intelligence system."""
    total_airlines = session.query(Airline).count()
    total_reviews = session.query(Review).count()
    total_nlp = session.query(NLPResult).count()

    airlines_with_reviews = (
        session.query(Airline.slug, func.count(Review.id).label("cnt"))
        .join(Review, Review.airline_id == Airline.id)
        .group_by(Airline.slug)
        .all()
    )
    review_distribution = {slug: cnt for slug, cnt in airlines_with_reviews}

    orphan_airlines = total_airlines - len(review_distribution)

    reviews_without_nlp = (
        session.query(func.count(Review.id))
        .outerjoin(NLPResult, NLPResult.review_id == Review.id)
        .filter(NLPResult.id.is_(None))
        .scalar()
    ) or 0

    metadata_count = session.query(AirlineMetadata).count()
    metadata_with_airline = (
        session.query(AirlineMetadata)
        .filter(AirlineMetadata.airline_id.isnot(None))
        .count()
    )

    top_airlines = sorted(review_distribution.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "summary": {
            "total_airlines": total_airlines,
            "total_reviews": total_reviews,
            "total_nlp_results": total_nlp,
            "airlines_with_reviews": len(review_distribution),
            "orphan_airlines_no_reviews": orphan_airlines,
            "reviews_without_nlp": reviews_without_nlp,
            "nlp_coverage_pct": round((total_nlp / total_reviews * 100) if total_reviews else 0, 1),
            "metadata_records": metadata_count,
            "metadata_linked": metadata_with_airline,
        },
        "top_airlines_by_reviews": [
            {"slug": slug, "review_count": cnt} for slug, cnt in top_airlines
        ],
    }
