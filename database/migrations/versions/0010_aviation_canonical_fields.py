"""Add canonical aviation fields to airline_metadata (idempotent).

Revision ID: 0010_aviation_canonical_fields
Revises: 0009_knowledge_graph
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010_aviation_canonical_fields"
down_revision = "0009_knowledge_graph"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _index_names(table: str) -> set[str]:
    return {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _table_exists("airline_metadata"):
        return

    cols = _column_names("airline_metadata")
    additions = [
        ("iata_code", sa.String(8)),
        ("icao_code", sa.String(8)),
        ("callsign", sa.String(120)),
        ("region", sa.String(80)),
        ("primary_hub", sa.String(8)),
        ("canonical_country", sa.String(120)),
        ("normalized_name", sa.String(220)),
        ("alliance_code", sa.String(24)),
    ]
    for name, col_type in additions:
        if name not in cols:
            op.add_column("airline_metadata", sa.Column(name, col_type, nullable=True))

    indexes = _index_names("airline_metadata")
    if "ix_airline_metadata_iata_code" not in indexes:
        op.create_index("ix_airline_metadata_iata_code", "airline_metadata", ["iata_code"])
    if "ix_airline_metadata_icao_code" not in indexes:
        op.create_index("ix_airline_metadata_icao_code", "airline_metadata", ["icao_code"])
    if "ix_airline_metadata_region" not in indexes:
        op.create_index("ix_airline_metadata_region", "airline_metadata", ["region"])
    if "ix_airline_metadata_normalized_name" not in indexes:
        op.create_index("ix_airline_metadata_normalized_name", "airline_metadata", ["normalized_name"])
    if "ix_airline_metadata_canonical_country" not in indexes:
        op.create_index("ix_airline_metadata_canonical_country", "airline_metadata", ["canonical_country"])
    if "ix_airline_metadata_alliance_code" not in indexes:
        op.create_index("ix_airline_metadata_alliance_code", "airline_metadata", ["alliance_code"])


def downgrade() -> None:
    if not _table_exists("airline_metadata"):
        return
    indexes = _index_names("airline_metadata")
    for idx in (
        "ix_airline_metadata_alliance_code",
        "ix_airline_metadata_canonical_country",
        "ix_airline_metadata_normalized_name",
        "ix_airline_metadata_region",
        "ix_airline_metadata_icao_code",
        "ix_airline_metadata_iata_code",
    ):
        if idx in indexes:
            op.drop_index(idx, table_name="airline_metadata")
    cols = _column_names("airline_metadata")
    for col in (
        "alliance_code",
        "normalized_name",
        "canonical_country",
        "primary_hub",
        "region",
        "callsign",
        "icao_code",
        "iata_code",
    ):
        if col in cols:
            op.drop_column("airline_metadata", col)
