"""hardening schema defaults and JSONB

Revision ID: 0002_hardening_schema
Revises: 0001_initial_schema
Create Date: 2026-05-21
"""

from alembic import op


revision = "0002_hardening_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


TABLES_WITH_TIMESTAMPS = (
    "airlines",
    "reviews",
    "nlp_results",
    "topic_snapshots",
    "spider_runs",
)


def upgrade() -> None:
    op.drop_index("ix_airlines_name", table_name="airlines")
    op.drop_index("ix_airlines_slug", table_name="airlines")

    for table_name in TABLES_WITH_TIMESTAMPS:
        op.execute(f"ALTER TABLE {table_name} ALTER COLUMN created_at SET DEFAULT now()")
        op.execute(f"ALTER TABLE {table_name} ALTER COLUMN updated_at SET DEFAULT now()")

    op.execute("ALTER TABLE airlines ALTER COLUMN source SET DEFAULT 'airlinequality'")
    op.execute("ALTER TABLE airlines ALTER COLUMN is_active SET DEFAULT true")
    op.execute("ALTER TABLE reviews ALTER COLUMN source SET DEFAULT 'airlinequality'")
    op.execute("ALTER TABLE reviews ALTER COLUMN scraped_at SET DEFAULT now()")
    op.execute("ALTER TABLE topic_snapshots ALTER COLUMN sample_size SET DEFAULT 0")
    op.execute("ALTER TABLE topic_snapshots ALTER COLUMN weight SET DEFAULT 0")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN items_scraped SET DEFAULT 0")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN pages_crawled SET DEFAULT 0")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN started_at SET DEFAULT now()")

    op.execute("ALTER TABLE reviews ALTER COLUMN metrics TYPE jsonb USING metrics::jsonb")
    op.execute("ALTER TABLE reviews ALTER COLUMN metrics SET DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN topics TYPE jsonb USING topics::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN topics SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN entities TYPE jsonb USING entities::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN entities SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN model_versions TYPE jsonb USING model_versions::jsonb")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN model_versions SET DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN errors TYPE jsonb USING errors::jsonb")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN errors SET DEFAULT '[]'::jsonb")

    op.create_check_constraint(
        "ck_reviews_rating_range",
        "reviews",
        "rating IS NULL OR (rating >= 0 AND rating <= 10)",
    )
    op.create_check_constraint(
        "ck_topic_snapshots_weight_non_negative",
        "topic_snapshots",
        "weight >= 0",
    )
    op.create_check_constraint(
        "ck_topic_snapshots_sample_size_non_negative",
        "topic_snapshots",
        "sample_size >= 0",
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_reviews_metrics_gin ON reviews USING gin (metrics)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_nlp_results_topics_gin ON nlp_results USING gin (topics)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_nlp_results_entities_gin ON nlp_results USING gin (entities)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_nlp_results_entities_gin")
    op.execute("DROP INDEX IF EXISTS ix_nlp_results_topics_gin")
    op.execute("DROP INDEX IF EXISTS ix_reviews_metrics_gin")

    op.drop_constraint("ck_topic_snapshots_sample_size_non_negative", "topic_snapshots", type_="check")
    op.drop_constraint("ck_topic_snapshots_weight_non_negative", "topic_snapshots", type_="check")
    op.drop_constraint("ck_reviews_rating_range", "reviews", type_="check")

    op.execute("ALTER TABLE spider_runs ALTER COLUMN errors TYPE json USING errors::json")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN errors DROP DEFAULT")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN model_versions TYPE json USING model_versions::json")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN model_versions DROP DEFAULT")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN entities TYPE json USING entities::json")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN entities DROP DEFAULT")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN topics TYPE json USING topics::json")
    op.execute("ALTER TABLE nlp_results ALTER COLUMN topics DROP DEFAULT")
    op.execute("ALTER TABLE reviews ALTER COLUMN metrics TYPE json USING metrics::json")
    op.execute("ALTER TABLE reviews ALTER COLUMN metrics DROP DEFAULT")

    op.execute("ALTER TABLE spider_runs ALTER COLUMN started_at DROP DEFAULT")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN pages_crawled DROP DEFAULT")
    op.execute("ALTER TABLE spider_runs ALTER COLUMN items_scraped DROP DEFAULT")
    op.execute("ALTER TABLE topic_snapshots ALTER COLUMN weight DROP DEFAULT")
    op.execute("ALTER TABLE topic_snapshots ALTER COLUMN sample_size DROP DEFAULT")
    op.execute("ALTER TABLE reviews ALTER COLUMN scraped_at DROP DEFAULT")
    op.execute("ALTER TABLE reviews ALTER COLUMN source DROP DEFAULT")
    op.execute("ALTER TABLE airlines ALTER COLUMN is_active DROP DEFAULT")
    op.execute("ALTER TABLE airlines ALTER COLUMN source DROP DEFAULT")

    for table_name in TABLES_WITH_TIMESTAMPS:
        op.execute(f"ALTER TABLE {table_name} ALTER COLUMN updated_at DROP DEFAULT")
        op.execute(f"ALTER TABLE {table_name} ALTER COLUMN created_at DROP DEFAULT")

    op.create_index("ix_airlines_slug", "airlines", ["slug"])
    op.create_index("ix_airlines_name", "airlines", ["name"])
