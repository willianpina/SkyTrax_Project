"""initial enterprise schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "airlines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("review_url", sa.String(length=700), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_airlines_name", "airlines", ["name"])
    op.create_index("ix_airlines_slug", "airlines", ["slug"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("source_url", sa.String(length=700), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("recommended", sa.Boolean(), nullable=True),
        sa.Column("seat_type", sa.String(length=120), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("aircraft", sa.String(length=160), nullable=True),
        sa.Column("travel_type", sa.String(length=160), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_reviews_fingerprint"),
    )
    op.create_index("ix_reviews_airline_date", "reviews", ["airline_id", "review_date"])
    op.create_index("ix_reviews_airline_id", "reviews", ["airline_id"])
    op.create_index("ix_reviews_source_external", "reviews", ["source", "external_id"])

    op.create_table(
        "nlp_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("sentiment_label", sa.String(length=32), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("cleaned_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )

    op.create_table(
        "topic_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("airline_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("polarity", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["airline_id"], ["airlines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_topic_snapshots_airline_id", "topic_snapshots", ["airline_id"])

    op.create_table(
        "spider_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("spider_name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("items_scraped", sa.Integer(), nullable=False),
        sa.Column("pages_crawled", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spider_runs_spider_name", "spider_runs", ["spider_name"])


def downgrade() -> None:
    op.drop_index("ix_spider_runs_spider_name", table_name="spider_runs")
    op.drop_table("spider_runs")
    op.drop_index("ix_topic_snapshots_airline_id", table_name="topic_snapshots")
    op.drop_table("topic_snapshots")
    op.drop_table("nlp_results")
    op.drop_index("ix_reviews_source_external", table_name="reviews")
    op.drop_index("ix_reviews_airline_id", table_name="reviews")
    op.drop_index("ix_reviews_airline_date", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_airlines_slug", table_name="airlines")
    op.drop_index("ix_airlines_name", table_name="airlines")
    op.drop_table("airlines")
