"""strategic intelligence: anomalies, geospatial, lineage, insight quality

Revision ID: 0006_strategic_intelligence
Revises: 0005_operational_intelligence
Create Date: 2026-05-21
"""

from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from database.postgis_support import (
    try_add_airports_location_column,
    try_create_postgis_extension,
)

revision = "0006_strategic_intelligence"
down_revision = "0005_operational_intelligence"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    postgis_active = try_create_postgis_extension(bind)

    op.create_table(
        "regions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "airports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("iata_code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("region_id", sa.String(length=36), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_hub", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iata_code"),
    )

    if postgis_active:
        try_add_airports_location_column(bind)
    else:
        logger.warning(
            "PostGIS unavailable - using latitude/longitude only (lightweight geospatial mode)",
            extra={"migration": revision},
        )

    op.create_index("ix_airports_iata", "airports", ["iata_code"])

    op.create_table(
        "routes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=False),
        sa.Column("origin_airport_id", sa.String(length=36), nullable=True),
        sa.Column("dest_airport_id", sa.String(length=36), nullable=True),
        sa.Column("route_label", sa.String(length=64), nullable=False),
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("complaint_density", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_sentiment_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.ForeignKeyConstraint(["origin_airport_id"], ["airports.id"]),
        sa.ForeignKeyConstraint(["dest_airport_id"], ["airports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("airline_id", "route_label", name="uq_routes_airline_label"),
    )

    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=True),
        sa.Column("anomaly_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("context", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomaly_events_airline", "anomaly_events", ["airline_id", "detected_at"])
    op.create_index("ix_anomaly_events_type", "anomaly_events", ["anomaly_type", "severity"])

    op.create_table(
        "data_lineage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("pipeline_stage", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_lineage_entity", "data_lineage", ["entity_type", "entity_id"])

    op.add_column("executive_insights", sa.Column("trend_direction", sa.String(length=32), nullable=True))
    op.add_column(
        "executive_insights",
        sa.Column("supporting_reviews", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        "executive_insights",
        sa.Column("supporting_topics", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        "semantic_clusters",
        sa.Column("relevance_score", sa.Float(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "semantic_clusters",
        sa.Column("confidence", sa.Float(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("semantic_clusters", "confidence")
    op.drop_column("semantic_clusters", "relevance_score")
    op.drop_column("executive_insights", "supporting_topics")
    op.drop_column("executive_insights", "supporting_reviews")
    op.drop_column("executive_insights", "trend_direction")
    op.drop_index("ix_data_lineage_entity", table_name="data_lineage")
    op.drop_table("data_lineage")
    op.drop_index("ix_anomaly_events_type", table_name="anomaly_events")
    op.drop_index("ix_anomaly_events_airline", table_name="anomaly_events")
    op.drop_table("anomaly_events")
    op.drop_table("routes")
    op.drop_index("ix_airports_iata", table_name="airports")
    op.execute("ALTER TABLE airports DROP COLUMN IF EXISTS location")
    op.drop_table("airports")
    op.drop_table("regions")
