from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analytics.data_quality import DataQualityMonitor
from api.schemas import (
    DataQualityReportResponse,
    SchedulerStatusResponse,
)
from database.models import ScheduledJob
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
