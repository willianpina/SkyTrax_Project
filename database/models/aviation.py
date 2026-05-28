"""Aviation metadata models -- airlines, airports, alliances, taxonomy."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base
from database.models.base import TimestampMixin


class Alliance(TimestampMixin, Base):
    __tablename__ = "alliances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    founded_year: Mapped[int | None] = mapped_column(Integer)
    member_count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    headquarters: Mapped[str | None] = mapped_column(String(160))

    members: Mapped[list["AirlineMetadata"]] = relationship(back_populates="alliance_rel")


class AirlineMetadata(TimestampMixin, Base):
    """Extended metadata beyond the core Airline record."""

    __tablename__ = "airline_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str | None] = mapped_column(ForeignKey("airlines.id"), index=True)
    airline_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    iata_code: Mapped[str | None] = mapped_column(String(8), index=True)
    icao_code: Mapped[str | None] = mapped_column(String(8), index=True)
    callsign: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120), index=True)
    canonical_country: Mapped[str | None] = mapped_column(String(120), index=True)
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    normalized_name: Mapped[str | None] = mapped_column(String(220), index=True)
    alliance_id: Mapped[str | None] = mapped_column(ForeignKey("alliances.id"), index=True)
    alliance_code: Mapped[str | None] = mapped_column(String(24), index=True)
    airline_type: Mapped[str | None] = mapped_column(String(60), index=True)
    star_rating: Mapped[int | None] = mapped_column(Integer)
    is_low_cost: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))
    fleet_size: Mapped[int | None] = mapped_column(Integer)
    primary_hub: Mapped[str | None] = mapped_column(String(8))
    certifications: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    hub_airports: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    operational_labels: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    skytrax_url: Mapped[str | None] = mapped_column(String(500))
    enrichment_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    normalization_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    metadata_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    enrichment_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        server_default=sql_text("'pending'"),
        nullable=False,
    )
    coverage_status: Mapped[str] = mapped_column(
        String(32),
        default="partial",
        server_default=sql_text("'partial'"),
        nullable=False,
    )
    source_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        server_default=sql_text("0.5"),
        nullable=False,
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    alliance_rel: Mapped[Alliance | None] = relationship(back_populates="members")


class AirportMetadata(TimestampMixin, Base):
    """Extended airport metadata from SkyTrax ratings."""

    __tablename__ = "airport_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airport_id: Mapped[str | None] = mapped_column(ForeignKey("airports.id"), index=True)
    airport_name: Mapped[str] = mapped_column(String(200), nullable=False)
    iata: Mapped[str | None] = mapped_column(String(8), unique=True)
    icao: Mapped[str | None] = mapped_column(String(8))
    city: Mapped[str | None] = mapped_column(String(160))
    country: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(80))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    passenger_volume: Mapped[str | None] = mapped_column(String(40))
    airport_rating: Mapped[int | None] = mapped_column(Integer)
    hub_level: Mapped[str | None] = mapped_column(String(40))
    operational_labels: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    skytrax_url: Mapped[str | None] = mapped_column(String(500))
    enrichment_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    normalization_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    metadata_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=sql_text("0"),
        nullable=False,
    )
    enrichment_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        server_default=sql_text("'pending'"),
        nullable=False,
    )
    coverage_status: Mapped[str] = mapped_column(
        String(32),
        default="partial",
        server_default=sql_text("'partial'"),
        nullable=False,
    )
    source_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        server_default=sql_text("0.5"),
        nullable=False,
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)


class AirlineAirport(TimestampMixin, Base):
    """Association between airlines and hub airports."""

    __tablename__ = "airline_airports"
    __table_args__ = (
        UniqueConstraint("airline_metadata_id", "airport_metadata_id", name="uq_airline_airport"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_metadata_id: Mapped[str] = mapped_column(
        ForeignKey("airline_metadata.id"), nullable=False, index=True
    )
    airport_metadata_id: Mapped[str] = mapped_column(
        ForeignKey("airport_metadata.id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(40), default="hub", server_default=sql_text("'hub'")
    )


class AviationTaxonomy(TimestampMixin, Base):
    """Hierarchical taxonomy for aviation classification."""

    __tablename__ = "aviation_taxonomy"
    __table_args__ = (UniqueConstraint("category", "label", name="uq_taxonomy_cat_label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_label: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    taxonomy_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )


class AviationCoverageReport(TimestampMixin, Base):
    """Point-in-time coverage audit snapshot."""

    __tablename__ = "aviation_coverage_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    total_airlines: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    total_airports: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    total_alliances: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    missing_iata: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    missing_icao: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    missing_country: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    missing_coordinates: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    duplicate_entities: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    orphan_airports: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    orphan_airlines: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    normalization_failures: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0, server_default=sql_text("0"))
    metadata_completeness: Mapped[float] = mapped_column(Float, default=0.0, server_default=sql_text("0"))
    enrichment_score: Mapped[float] = mapped_column(Float, default=0.0, server_default=sql_text("0"))
    graph_readiness: Mapped[float] = mapped_column(Float, default=0.0, server_default=sql_text("0"))
    report_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
