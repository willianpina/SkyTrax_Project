"""Repair airline_metadata semantic drift — create aviation tables, backfill IATA.

Revision ID: 0011_airline_metadata_schema_repair
Revises: 0010_aviation_canonical_fields
"""

from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger("alembic.runtime.migration")

revision = "0011_airline_metadata_schema_repair"
down_revision = "0010_aviation_canonical_fields"
branch_labels = None
depends_on = None


def _ensure_alembic_version_capacity(min_length: int = 128) -> None:
    """Widen version_num before Alembic records this revision id (>32 chars)."""
    bind = op.get_bind()
    if "alembic_version" not in inspect(bind).get_table_names():
        return
    row = bind.execute(
        text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'alembic_version' AND column_name = 'version_num'"
        )
    ).fetchone()
    current_len = int(row[0]) if row and row[0] is not None else 32
    if current_len < min_length:
        op.execute(text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({min_length})"))


def _table_exists(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _ensure_airline_metadata_columns() -> None:
    if not _table_exists("airline_metadata"):
        return
    cols = _column_names("airline_metadata")
    for name, col_type in (
        ("iata_code", sa.String(8)),
        ("icao_code", sa.String(8)),
        ("callsign", sa.String(120)),
        ("region", sa.String(80)),
        ("primary_hub", sa.String(8)),
        ("canonical_country", sa.String(120)),
        ("normalized_name", sa.String(220)),
        ("alliance_code", sa.String(24)),
    ):
        if name not in cols:
            op.add_column("airline_metadata", sa.Column(name, col_type, nullable=True))


def _create_aviation_tables_if_missing() -> None:
    """Create aviation intelligence tables when absent (never in early migrations)."""
    if not _table_exists("alliances"):
        op.create_table(
            "alliances",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False, unique=True),
            sa.Column("slug", sa.String(120), nullable=False, unique=True),
            sa.Column("founded_year", sa.Integer(), nullable=True),
            sa.Column("member_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("headquarters", sa.String(160), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )

    if not _table_exists("airline_metadata"):
        op.create_table(
            "airline_metadata",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("airline_id", sa.String(36), sa.ForeignKey("airlines.id"), nullable=True),
            sa.Column("airline_name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(200), nullable=False, unique=True),
            sa.Column("iata_code", sa.String(8), nullable=True),
            sa.Column("icao_code", sa.String(8), nullable=True),
            sa.Column("callsign", sa.String(120), nullable=True),
            sa.Column("country", sa.String(120), nullable=True),
            sa.Column("canonical_country", sa.String(120), nullable=True),
            sa.Column("region", sa.String(80), nullable=True),
            sa.Column("normalized_name", sa.String(220), nullable=True),
            sa.Column("alliance_id", sa.String(36), sa.ForeignKey("alliances.id"), nullable=True),
            sa.Column("alliance_code", sa.String(24), nullable=True),
            sa.Column("airline_type", sa.String(60), nullable=True),
            sa.Column("star_rating", sa.Integer(), nullable=True),
            sa.Column("is_low_cost", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("is_premium", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("fleet_size", sa.Integer(), nullable=True),
            sa.Column("primary_hub", sa.String(8), nullable=True),
            sa.Column("certifications", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("hub_airports", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("operational_labels", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("skytrax_url", sa.String(500), nullable=True),
            sa.Column("enrichment_confidence", sa.Float(), server_default=sa.text("0"), nullable=False),
            sa.Column("normalization_confidence", sa.Float(), server_default=sa.text("0"), nullable=False),
            sa.Column("metadata_quality_score", sa.Float(), server_default=sa.text("0"), nullable=False),
            sa.Column(
                "enrichment_status", sa.String(32), server_default=sa.text("'pending'"), nullable=False
            ),
            sa.Column("coverage_status", sa.String(32), server_default=sa.text("'partial'"), nullable=False),
            sa.Column("source_confidence", sa.Float(), server_default=sa.text("0.5"), nullable=False),
            sa.Column("raw_metadata", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("last_enriched_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_airline_metadata_slug", "airline_metadata", ["slug"])
        op.create_index("ix_airline_metadata_iata_code", "airline_metadata", ["iata_code"])
        op.create_index("ix_airline_metadata_icao_code", "airline_metadata", ["icao_code"])
        op.create_index("ix_airline_metadata_region", "airline_metadata", ["region"])
        op.create_index("ix_airline_metadata_normalized_name", "airline_metadata", ["normalized_name"])
        op.create_index("ix_airline_metadata_canonical_country", "airline_metadata", ["canonical_country"])
        op.create_index("ix_airline_metadata_alliance_code", "airline_metadata", ["alliance_code"])
        return

    _ensure_airline_metadata_columns()


def _backfill_canonical_codes() -> None:
    if not _table_exists("airline_metadata"):
        return
    conn = op.get_bind()
    cols = _column_names("airline_metadata")
    if "iata_code" not in cols:
        return

    if "iata" in cols:
        conn.execute(
            text(
                "UPDATE airline_metadata SET iata_code = UPPER(TRIM(iata)) "
                "WHERE iata_code IS NULL AND iata IS NOT NULL AND TRIM(iata) <> ''"
            )
        )
        logger.info("[MIGRATION] Backfilled iata_code from legacy iata column")
    for alias in ("iata_airline", "airline_iata", "code_iata"):
        if alias in cols:
            conn.execute(
                text(
                    f"UPDATE airline_metadata SET iata_code = UPPER(TRIM({alias})) "
                    f"WHERE iata_code IS NULL AND {alias} IS NOT NULL AND TRIM({alias}) <> ''"
                )
            )

    if "icao" in cols and "icao_code" in cols:
        conn.execute(
            text(
                "UPDATE airline_metadata SET icao_code = UPPER(TRIM(icao)) "
                "WHERE icao_code IS NULL AND icao IS NOT NULL AND TRIM(icao) <> ''"
            )
        )
    for alias in ("icao_airline", "airline_icao"):
        if alias in cols and "icao_code" in cols:
            conn.execute(
                text(
                    f"UPDATE airline_metadata SET icao_code = UPPER(TRIM({alias})) "
                    f"WHERE icao_code IS NULL AND {alias} IS NOT NULL AND TRIM({alias}) <> ''"
                )
            )

    if "raw_metadata" in cols:
        conn.execute(
            text(
                "UPDATE airline_metadata SET iata_code = UPPER(TRIM(raw_metadata->>'iata')) "
                "WHERE iata_code IS NULL AND raw_metadata->>'iata' IS NOT NULL "
                "AND TRIM(raw_metadata->>'iata') <> ''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET iata_code = UPPER(TRIM(raw_metadata->>'iata_code')) "
                "WHERE iata_code IS NULL AND raw_metadata->>'iata_code' IS NOT NULL "
                "AND TRIM(raw_metadata->>'iata_code') <> ''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET icao_code = UPPER(TRIM(raw_metadata->>'icao')) "
                "WHERE icao_code IS NULL AND raw_metadata->>'icao' IS NOT NULL "
                "AND TRIM(raw_metadata->>'icao') <> ''"
            )
        )
        conn.execute(
            text(
                "UPDATE airline_metadata SET icao_code = UPPER(TRIM(raw_metadata->>'icao_code')) "
                "WHERE icao_code IS NULL AND raw_metadata->>'icao_code' IS NOT NULL "
                "AND TRIM(raw_metadata->>'icao_code') <> ''"
            )
        )
        if "alliance_code" in cols:
            conn.execute(
                text(
                    "UPDATE airline_metadata SET alliance_code = UPPER(TRIM(raw_metadata->>'alliance_code')) "
                    "WHERE alliance_code IS NULL AND raw_metadata->>'alliance_code' IS NOT NULL "
                    "AND TRIM(raw_metadata->>'alliance_code') <> ''"
                )
            )
        if "canonical_country" in cols:
            conn.execute(
                text(
                    "UPDATE airline_metadata SET canonical_country = NULLIF(TRIM(raw_metadata->>'canonical_country'), '') "
                    "WHERE canonical_country IS NULL AND raw_metadata->>'canonical_country' IS NOT NULL"
                )
            )


def upgrade() -> None:
    _ensure_alembic_version_capacity()
    _create_aviation_tables_if_missing()
    _ensure_airline_metadata_columns()
    _backfill_canonical_codes()


def downgrade() -> None:
    pass
