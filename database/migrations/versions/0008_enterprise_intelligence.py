"""enterprise intelligence wave — forecast quality, anomalies, spider ops

Revision ID: 0008_enterprise_intelligence
Revises: 0007_forecasting_anomaly
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "0008_enterprise_intelligence"
down_revision = "0007_forecasting_anomaly"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    fs_cols = _column_names("forecast_snapshots")
    if "confidence_score" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("confidence_score", sa.Float(), nullable=True))
    if "sample_size" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("sample_size", sa.Integer(), nullable=True))
    if "window_size" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("window_size", sa.Integer(), nullable=True))
    if "insufficient_data" not in fs_cols:
        op.add_column(
            "forecast_snapshots",
            sa.Column("insufficient_data", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
    if "generated_from_reviews" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("generated_from_reviews", sa.Integer(), nullable=True))
    if "explanation" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("explanation", sa.Text(), nullable=True))
    if "forecast_method" not in fs_cols:
        op.add_column("forecast_snapshots", sa.Column("forecast_method", sa.String(48), nullable=True))

    # Allow NULL forecast values when insufficient data
    op.alter_column("forecast_snapshots", "current_value", existing_type=sa.Float(), nullable=True)
    op.alter_column("forecast_snapshots", "forecast_value", existing_type=sa.Float(), nullable=True)

    ae_cols = _column_names("anomaly_events")
    if "anomaly_confidence" not in ae_cols:
        op.add_column("anomaly_events", sa.Column("anomaly_confidence", sa.Float(), nullable=True))
    if "anomaly_score" not in ae_cols:
        op.add_column("anomaly_events", sa.Column("anomaly_score", sa.Float(), nullable=True))
    if "explanation" not in ae_cols:
        op.add_column("anomaly_events", sa.Column("explanation", sa.Text(), nullable=True))

    sr_cols = _column_names("spider_runs")
    if "crawl_duration_ms" not in sr_cols:
        op.add_column("spider_runs", sa.Column("crawl_duration_ms", sa.Integer(), nullable=True))
    if "retry_count" not in sr_cols:
        op.add_column(
            "spider_runs", sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False)
        )
    if "anti_ban_triggers" not in sr_cols:
        op.add_column(
            "spider_runs",
            sa.Column("anti_ban_triggers", sa.Integer(), server_default=sa.text("0"), nullable=False),
        )
    if "quality_score" not in sr_cols:
        op.add_column("spider_runs", sa.Column("quality_score", sa.Float(), nullable=True))
    if "airline_slug" not in sr_cols:
        op.add_column("spider_runs", sa.Column("airline_slug", sa.String(180), nullable=True))
    if "run_metadata" not in sr_cols:
        op.add_column(
            "spider_runs",
            sa.Column("run_metadata", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        )


def downgrade() -> None:
    for col in (
        "run_metadata",
        "airline_slug",
        "quality_score",
        "anti_ban_triggers",
        "retry_count",
        "crawl_duration_ms",
    ):
        op.drop_column("spider_runs", col)
    for col in ("explanation", "anomaly_score", "anomaly_confidence"):
        op.drop_column("anomaly_events", col)
    for col in (
        "forecast_method",
        "explanation",
        "generated_from_reviews",
        "insufficient_data",
        "window_size",
        "sample_size",
        "confidence_score",
    ):
        op.drop_column("forecast_snapshots", col)
