from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analytics.anomaly import AnomalyDetectionService
from api.schemas import AnomalyEventResponse, OperationalAlertResponse
from database.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("/alerts", response_model=list[OperationalAlertResponse])
def anomaly_alerts(
    limit: int = Query(default=20, le=50),
    session: Session = Depends(get_session),
) -> list[OperationalAlertResponse]:
    try:
        return AnomalyDetectionService(session).operational_alerts(limit=limit)
    except SQLAlchemyError as exc:
        logger.exception("anomaly_alerts_failed")
        return []


@router.post("/refresh", response_model=dict)
def refresh_anomalies(session: Session = Depends(get_session)) -> dict:
    try:
        return AnomalyDetectionService(session).detect_and_persist()
    except SQLAlchemyError as exc:
        logger.exception("anomaly_refresh_failed")
        raise HTTPException(status_code=503, detail="Anomaly storage unavailable.") from exc


@router.get("", response_model=list[AnomalyEventResponse])
def list_anomalies(
    airline: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
) -> list[AnomalyEventResponse]:
    try:
        return AnomalyDetectionService(session).list_recent(limit=limit, airline_slug=airline)
    except SQLAlchemyError as exc:
        logger.exception("anomaly_list_failed")
        return []
