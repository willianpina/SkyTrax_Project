from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base
from database.models.base import TimestampMixin


class TopicSnapshot(TimestampMixin, Base):
    """Materialized topic aggregate for dashboard reads."""

    __tablename__ = "topic_snapshots"
    __table_args__ = (
        CheckConstraint("weight >= 0", name="ck_topic_snapshots_weight_non_negative"),
        CheckConstraint("sample_size >= 0", name="ck_topic_snapshots_sample_size_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    polarity: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default=sql_text("0"))
    sample_size: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"), nullable=False)


class MetricSnapshot(TimestampMixin, Base):
    """Temporal aggregates for sentiment, reputation, topics and volume trends."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (Index("ix_metric_snapshots_airline_type", "airline_id", "snapshot_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )


class ReputationScoreHistory(TimestampMixin, Base):
    """Historical Airline Reputation Score (ARS) records."""

    __tablename__ = "reputation_score_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str] = mapped_column(ForeignKey("airlines.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    components: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )


class ForecastSnapshot(TimestampMixin, Base):
    """Persisted lightweight forecasts (EWMA, rolling averages)."""

    __tablename__ = "forecast_snapshots"
    __table_args__ = (Index("ix_forecast_snapshots_lookup", "airline_id", "metric", "horizon"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    horizon: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    forecast_method: Mapped[str | None] = mapped_column(String(48))
    current_value: Mapped[float | None] = mapped_column(Float)
    forecast_value: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    window_size: Mapped[int | None] = mapped_column(Integer)
    insufficient_data: Mapped[bool] = mapped_column(
        default=False, server_default=sql_text("false"), nullable=False
    )
    generated_from_reviews: Mapped[int | None] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)
    trend_direction: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )


class AnomalyEvent(TimestampMixin, Base):
    __tablename__ = "anomaly_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_value: Mapped[float | None] = mapped_column(Float)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_confidence: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )
