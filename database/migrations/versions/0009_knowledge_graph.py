"""knowledge graph + fusion intelligence tables

Revision ID: 0009_knowledge_graph
Revises: 0008_enterprise_intelligence
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "0009_knowledge_graph"
down_revision = "0008_enterprise_intelligence"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _table_exists("graph_nodes"):
        op.create_table(
            "graph_nodes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("node_type", sa.String(40), nullable=False),
            sa.Column("entity_id", sa.String(180), nullable=False),
            sa.Column("label", sa.String(300), nullable=False),
            sa.Column("properties", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("mention_count", sa.Integer, server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("node_type", "entity_id", name="uq_graph_node_type_entity"),
        )
        op.create_index("ix_graph_nodes_type", "graph_nodes", ["node_type"])

    if not _table_exists("graph_edges"):
        op.create_table(
            "graph_edges",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source_node_id", sa.String(36), nullable=False),
            sa.Column("target_node_id", sa.String(36), nullable=False),
            sa.Column("edge_type", sa.String(60), nullable=False),
            sa.Column("weight", sa.Float, nullable=False),
            sa.Column("properties", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("source_node_id", "target_node_id", "edge_type", name="uq_graph_edge"),
        )
        op.create_index("ix_graph_edges_type", "graph_edges", ["edge_type"])
        op.create_index("ix_graph_edges_source", "graph_edges", ["source_node_id"])
        op.create_index("ix_graph_edges_target", "graph_edges", ["target_node_id"])

    if not _table_exists("fusion_signals"):
        op.create_table(
            "fusion_signals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category", sa.String(60), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("entities", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("evidence", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("confidence", sa.Float, nullable=False),
            sa.Column("detected_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_fusion_signals_category", "fusion_signals", ["category"])
        op.create_index("ix_fusion_signals_severity", "fusion_signals", ["severity"])

    if not _table_exists("review_intelligence"):
        op.create_table(
            "review_intelligence",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("review_id", sa.String(36), unique=True, nullable=False),
            sa.Column("disruptions", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("quality_scores", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("aircraft_mentions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("route_mentions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("airport_mentions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("operational_severity", sa.String(20), nullable=False),
            sa.Column("intelligence_data", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_review_intel_review", "review_intelligence", ["review_id"])
        op.create_index("ix_review_intel_severity", "review_intelligence", ["operational_severity"])


def downgrade() -> None:
    for table in ("review_intelligence", "fusion_signals", "graph_edges", "graph_nodes"):
        if _table_exists(table):
            op.drop_table(table)
