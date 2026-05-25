"""remove invalid historical reviews

Revision ID: 0003_review_quality_cleanup
Revises: 0002_hardening_schema
Create Date: 2026-05-21
"""

from alembic import op


revision = "0003_review_quality_cleanup"
down_revision = "0002_hardening_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM reviews
        WHERE title IS NULL
           OR btrim(title) = ''
           OR rating IS NULL
           OR review_date IS NULL
           OR length(btrim(text)) < 40
        """
    )


def downgrade() -> None:
    pass
