from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analytics.forecasting import TrendForecastingService
from api.schemas import ForecastingSummaryResponse, ForecastSnapshotResponse
from database.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecasting", tags=["forecasting"])


@router.get("", response_model=ForecastingSummaryResponse)
def list_forecasting(
    airline: str | None = None,
    metric: str | None = None,
    horizon: str | None = Query(default=None, pattern="^(weekly|monthly)$"),
    session: Session = Depends(get_session),
) -> ForecastingSummaryResponse:
    try:
        service = TrendForecastingService(session)
        if airline or metric or horizon:
            rows = service.list_forecasts(airline_slug=airline, metric=metric, horizon=horizon, limit=60)
            grouped: dict[str, list] = {}
            for row in rows:
                grouped.setdefault(row["metric"], []).append(row)
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "metrics": grouped,
                "airlines": sorted({row["airline_slug"] for row in rows if row.get("airline_slug")}),
            }
        return service.portfolio_summary()
    except SQLAlchemyError as exc:
        logger.exception("forecasting_list_failed")
        raise HTTPException(status_code=503, detail="Forecasting storage unavailable.") from exc


@router.post("/refresh", response_model=dict)
def refresh_forecasting(session: Session = Depends(get_session)) -> dict:
    try:
        return TrendForecastingService(session).generate_and_persist()
    except SQLAlchemyError as exc:
        logger.exception("forecasting_refresh_failed")
        raise HTTPException(status_code=503, detail="Forecasting storage unavailable.") from exc


@router.get("/{airline_slug}", response_model=list[ForecastSnapshotResponse])
def airline_forecasting(
    airline_slug: str,
    metric: str | None = None,
    horizon: str | None = None,
    session: Session = Depends(get_session),
) -> list[ForecastSnapshotResponse]:
    if airline_slug == "refresh":
        raise HTTPException(status_code=404, detail="Use POST /api/forecasting/refresh")
    try:
        return TrendForecastingService(session).list_forecasts(
            airline_slug=airline_slug,
            metric=metric,
            horizon=horizon,
            limit=30,
        )
    except SQLAlchemyError as exc:
        logger.exception("forecasting_airline_failed", extra={"airline_slug": airline_slug})
        raise HTTPException(status_code=503, detail="Forecasting storage unavailable.") from exc
