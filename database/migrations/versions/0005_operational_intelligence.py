"""operational intelligence tables

Revision ID: 0005_operational_intelligence
Revises: 0004_ai_search_indexes
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0005_operational_intelligence"
down_revision = "0004_ai_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=True),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metric_snapshots_airline_type", "metric_snapshots", ["airline_id", "snapshot_type"])
    op.create_index("ix_metric_snapshots_period", "metric_snapshots", ["period_start", "snapshot_type"])

    op.create_table(
        "executive_insights",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False),
        sa.Column("supporting_metrics", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_executive_insights_airline", "executive_insights", ["airline_id", "generated_at"])
    op.create_index("ix_executive_insights_severity", "executive_insights", ["severity", "generated_at"])

    op.create_table(
        "reputation_score_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("components", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reputation_history_airline", "reputation_score_history", ["airline_id", "recorded_at"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("overlap_lock_until", sa.DateTime(), nullable=True),
        sa.Column("run_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_name", name="uq_scheduled_jobs_job_name"),
    )

    op.create_table(
        "data_quality_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("findings", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sample_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_reports_type", "data_quality_reports", ["report_type", "generated_at"])

    op.create_table(
        "semantic_clusters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=True),
        sa.Column("cluster_label", sa.String(length=120), nullable=False),
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("centroid_terms", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sample_review_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_semantic_clusters_airline", "semantic_clusters", ["airline_id", "cluster_label"])


def downgrade() -> None:
    op.drop_index("ix_semantic_clusters_airline", table_name="semantic_clusters")
    op.drop_table("semantic_clusters")
    op.drop_index("ix_data_quality_reports_type", table_name="data_quality_reports")
    op.drop_table("data_quality_reports")
    op.drop_table("scheduled_jobs")
    op.drop_index("ix_reputation_history_airline", table_name="reputation_score_history")
    op.drop_table("reputation_score_history")
    op.drop_index("ix_executive_insights_severity", table_name="executive_insights")
    op.drop_index("ix_executive_insights_airline", table_name="executive_insights")
    op.drop_table("executive_insights")
    op.drop_index("ix_metric_snapshots_period", table_name="metric_snapshots")
    op.drop_index("ix_metric_snapshots_airline_type", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
