from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base
from database.models.base import TimestampMixin


class ExecutiveInsight(TimestampMixin, Base):
    """Persisted executive intelligence signals."""

    __tablename__ = "executive_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(
        Float, default=0.5, server_default=sql_text("0.5"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    trend_direction: Mapped[str | None] = mapped_column(String(32))
    supporting_reviews: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    supporting_topics: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    supporting_metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )


class SemanticCluster(TimestampMixin, Base):
    """Lightweight semantic grouping of reviews by operational theme."""

    __tablename__ = "semantic_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    cluster_label: Mapped[str] = mapped_column(String(120), nullable=False)
    review_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=sql_text("0"), nullable=False
    )
    centroid_terms: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    sample_review_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    relevance_score: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=sql_text("0"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=sql_text("0"), nullable=False
    )


class DataQualityReport(TimestampMixin, Base):
    """Automated data quality findings."""

    __tablename__ = "data_quality_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    sample_size: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )


class DataLineage(TimestampMixin, Base):
    __tablename__ = "data_lineage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(120))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
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


class ScheduledJob(TimestampMixin, Base):
    """Operational scheduler job state and overlap control."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (UniqueConstraint("job_name", name="uq_scheduled_jobs_job_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="idle", server_default=sql_text("'idle'"), nullable=False
    )
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    overlap_lock_until: Mapped[datetime | None] = mapped_column(DateTime)
    run_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
