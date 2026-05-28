from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base
from database.models.base import TimestampMixin


class Region(TimestampMixin, Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Airport(TimestampMixin, Base):
    __tablename__ = "airports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    iata_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    region_id: Mapped[str | None] = mapped_column(ForeignKey("regions.id"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_hub: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"), nullable=False)


class Route(TimestampMixin, Base):
    __tablename__ = "routes"
    __table_args__ = (UniqueConstraint("airline_id", "route_label", name="uq_routes_airline_label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    airline_id: Mapped[str] = mapped_column(ForeignKey("airlines.id"), nullable=False, index=True)
    origin_airport_id: Mapped[str | None] = mapped_column(ForeignKey("airports.id"))
    dest_airport_id: Mapped[str | None] = mapped_column(ForeignKey("airports.id"))
    route_label: Mapped[str] = mapped_column(String(64), nullable=False)
    review_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=sql_text("0"), nullable=False
    )
    complaint_density: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=sql_text("0"), nullable=False
    )
    avg_sentiment_score: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=sql_text("0"), nullable=False
    )
