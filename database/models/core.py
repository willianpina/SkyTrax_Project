from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database.session import Base
from database.models.base import TimestampMixin


class Airline(TimestampMixin, Base):
    """Airline tracked by the intelligence platform."""

    __tablename__ = "airlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(120))
    review_url: Mapped[str | None] = mapped_column(String(700))
    source: Mapped[str] = mapped_column(
        String(80),
        default="airlinequality",
        server_default=sql_text("'airlinequality'"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sql_text("true"), nullable=False)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime)

    reviews: Mapped[list["Review"]] = relationship(back_populates="airline", cascade="all, delete-orphan")


class Review(TimestampMixin, Base):
    """Canonical airline review fact persisted from Scrapy items."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_reviews_fingerprint"),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 10)", name="ck_reviews_rating_range"),
        Index("ix_reviews_airline_date", "airline_id", "review_date"),
        Index("ix_reviews_source_external", "source", "external_id"),
        Index("ix_reviews_metrics_gin", "metrics", postgresql_using="gin"),
        Index("ix_reviews_rating", "rating"),
        Index("ix_reviews_recommended", "recommended"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str] = mapped_column(ForeignKey("airlines.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(80),
        default="airlinequality",
        server_default=sql_text("'airlinequality'"),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(String(700))
    title: Mapped[str | None] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    recommended: Mapped[bool | None] = mapped_column()
    seat_type: Mapped[str | None] = mapped_column(String(120))
    route: Mapped[str | None] = mapped_column(String(255))
    aircraft: Mapped[str | None] = mapped_column(String(160))
    travel_type: Mapped[str | None] = mapped_column(String(160))
    review_date: Mapped[date | None] = mapped_column(Date)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )

    airline: Mapped[Airline] = relationship(back_populates="reviews")
    nlp_result: Mapped["NLPResult"] = relationship(
        back_populates="review", uselist=False, cascade="all, delete-orphan"
    )


class NLPResult(TimestampMixin, Base):
    """NLP enrichment, including pgvector-ready embedding storage."""

    __tablename__ = "nlp_results"
    __table_args__ = (
        Index("ix_nlp_results_topics_gin", "topics", postgresql_using="gin"),
        Index("ix_nlp_results_entities_gin", "entities", postgresql_using="gin"),
        Index("ix_nlp_results_sentiment_label", "sentiment_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), unique=True, nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(32), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    topics: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    entities: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    model_versions: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)

    review: Mapped[Review] = relationship(back_populates="nlp_result")


Index(
    "ix_nlp_results_embedding_hnsw",
    NLPResult.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
    postgresql_where=NLPResult.embedding.isnot(None),
)


class SpiderRun(TimestampMixin, Base):
    """Operational monitoring record for Scrapy runs."""

    __tablename__ = "spider_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    spider_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    items_scraped: Mapped[int] = mapped_column(
        Integer, default=0, server_default=sql_text("0"), nullable=False
    )
    pages_crawled: Mapped[int] = mapped_column(
        Integer, default=0, server_default=sql_text("0"), nullable=False
    )
    crawl_duration_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"), nullable=False)
    anti_ban_triggers: Mapped[int] = mapped_column(
        Integer, default=0, server_default=sql_text("0"), nullable=False
    )
    quality_score: Mapped[float | None] = mapped_column(Float)
    airline_slug: Mapped[str | None] = mapped_column(String(180))
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
