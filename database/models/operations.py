"""Operational refresh run tracking model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base
from database.models.base import TimestampMixin


class OperationalRefreshRun(TimestampMixin, Base):
    """Point-in-time record of an operational refresh pipeline execution."""

    __tablename__ = "operational_refresh_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    operation_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    reviews_processed: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    airlines_updated: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    airports_updated: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    anomalies_generated: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    forecasts_generated: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    semantic_updates: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    triggered_by: Mapped[str] = mapped_column(
        String(60), default="manual", server_default=sql_text("'manual'")
    )
    stage_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
