"""add analytics and semantic search indexes

Revision ID: 0004_ai_search_indexes
Revises: 0003_review_quality_cleanup
Create Date: 2026-05-21
"""

from alembic import op


revision = "0004_ai_search_indexes"
down_revision = "0003_review_quality_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_reviews_rating ON reviews (rating)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reviews_recommended ON reviews (recommended)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_nlp_results_sentiment_label ON nlp_results (sentiment_label)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_nlp_results_embedding_hnsw
        ON nlp_results
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_nlp_results_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_nlp_results_sentiment_label")
    op.execute("DROP INDEX IF EXISTS ix_reviews_recommended")
    op.execute("DROP INDEX IF EXISTS ix_reviews_rating")
