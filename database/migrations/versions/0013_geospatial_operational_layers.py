"""geospatial operational layers

Revision ID: 0013_geospatial_operational_layers
Revises: 0012_alembic_ver_expand
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from database.postgis_support import try_create_postgis_extension

revision = "0013_geospatial_operational_layers"
down_revision = "0012_alembic_ver_expand"
branch_labels = None
depends_on = None


def _column_exists(bind, table: str, column: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table, "column_name": column},
    ).scalar()
    return bool(row)


def upgrade() -> None:
    bind = op.get_bind()
    postgis_active = try_create_postgis_extension(bind)

    if not _column_exists(bind, "airports", "icao"):
        op.add_column("airports", sa.Column("icao", sa.String(length=8), nullable=True))
    if not _column_exists(bind, "airports", "hub_score"):
        op.add_column("airports", sa.Column("hub_score", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "airports", "risk_score"):
        op.add_column("airports", sa.Column("risk_score", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "airports", "reputation_score"):
        op.add_column("airports", sa.Column("reputation_score", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "airports", "movimentacao"):
        op.add_column("airports", sa.Column("movimentacao", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "airports", "alliance"):
        op.add_column("airports", sa.Column("alliance", sa.Text(), nullable=True))

    if not _column_exists(bind, "routes", "source_icao"):
        op.add_column("routes", sa.Column("source_icao", sa.String(length=8), nullable=True))
    if not _column_exists(bind, "routes", "destination_icao"):
        op.add_column("routes", sa.Column("destination_icao", sa.String(length=8), nullable=True))
    if not _column_exists(bind, "routes", "frequency"):
        op.add_column("routes", sa.Column("frequency", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "routes", "risk_score"):
        op.add_column("routes", sa.Column("risk_score", sa.Numeric(), nullable=True))
    if not _column_exists(bind, "routes", "reputation_score"):
        op.add_column("routes", sa.Column("reputation_score", sa.Numeric(), nullable=True))

    op.create_table(
        "geo_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("companhia", sa.Text(), nullable=True),
        sa.Column("tipo_evento", sa.Text(), nullable=True),
        sa.Column("prioridade", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_geo_events_created_at", "geo_events", ["created_at"])
    op.create_index("ix_geo_events_priority", "geo_events", ["prioridade"])

    if postgis_active:
        bind.execute(sa.text("ALTER TABLE airports ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)"))
        bind.execute(sa.text("ALTER TABLE routes ADD COLUMN IF NOT EXISTS geom geography(LineString, 4326)"))
        bind.execute(sa.text("ALTER TABLE geo_events ADD COLUMN IF NOT EXISTS geom geography(Point, 4326)"))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "geo_events", "geom"):
        bind.execute(sa.text("ALTER TABLE geo_events DROP COLUMN IF EXISTS geom"))
    op.drop_index("ix_geo_events_priority", table_name="geo_events")
    op.drop_index("ix_geo_events_created_at", table_name="geo_events")
    op.drop_table("geo_events")
