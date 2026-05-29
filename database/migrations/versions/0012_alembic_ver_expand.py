"""Widen alembic_version.version_num for long semantic revision IDs.

Revision ID: 0012_alembic_ver_expand
Revises: 0011_airline_metadata_schema_repair
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision = "0012_alembic_ver_expand"
down_revision = "0011_airline_metadata_schema_repair"
branch_labels = None
depends_on = None

TARGET_LENGTH = 128


def _current_varchar_length() -> int | None:
    bind = op.get_bind()
    if "alembic_version" not in inspect(bind).get_table_names():
        return None
    row = bind.execute(
        text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'alembic_version' AND column_name = 'version_num'"
        )
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else None


def upgrade() -> None:
    length = _current_varchar_length()
    if length is not None and length >= TARGET_LENGTH:
        return
    op.execute(text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({TARGET_LENGTH})"))


def downgrade() -> None:
    # Intentionally no-op: shrinking version_num risks truncation after long revisions applied.
    pass
