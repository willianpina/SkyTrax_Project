"""forecasting and anomaly detection tables

Revision ID: 0007_forecasting_anomaly
Revises: 0006_strategic_intelligence
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "0007_forecasting_anomaly"
down_revision = "0006_strategic_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()

    if "anomaly_events" not in tables:
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

    if "forecast_snapshots" not in tables:
        op.create_table(
            "forecast_snapshots",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("airline_id", sa.String(length=36), nullable=True),
            sa.Column("metric", sa.String(length=64), nullable=False),
            sa.Column("horizon", sa.String(length=32), nullable=False),
            sa.Column("method", sa.String(length=32), nullable=False),
            sa.Column("current_value", sa.Float(), nullable=False),
            sa.Column("forecast_value", sa.Float(), nullable=False),
            sa.Column("trend_direction", sa.String(length=32), nullable=False),
            sa.Column("payload", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_forecast_snapshots_lookup", "forecast_snapshots", ["airline_id", "metric", "horizon"]
        )


def downgrade() -> None:
    op.drop_index("ix_forecast_snapshots_lookup", table_name="forecast_snapshots")
    op.drop_table("forecast_snapshots")
