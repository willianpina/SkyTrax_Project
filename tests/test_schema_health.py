"""Tests for database schema validation and bootstrap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from database.schema_health import (
    all_required_tables,
    check_migrations,
    check_tables,
    validate_schema,
)


class FakeInspector:
    def __init__(self, tables: set[str], indexes: dict | None = None, fks: dict | None = None):
        self._tables = tables
        self._indexes = indexes or {}
        self._fks = fks or {}

    def get_table_names(self):
        return list(self._tables)

    def get_indexes(self, table: str):
        return self._indexes.get(table, [])

    def get_foreign_keys(self, table: str):
        return self._fks.get(table, [])


def test_all_required_tables_includes_knowledge_graph():
    tables = all_required_tables()
    assert "review_intelligence" in tables
    assert "graph_nodes" in tables
    assert "graph_edges" in tables
    assert "forecast_snapshots" in tables
    assert "anomaly_events" in tables


def test_check_tables_missing():
    engine = MagicMock()
    with patch("database.schema_health.inspect") as mock_inspect:
        mock_inspect.return_value = FakeInspector({"airlines", "reviews"})
        result = check_tables(engine)
    assert "review_intelligence" in result["missing_tables"]
    assert "graph_nodes" in result["missing_tables"]
    assert result["complete"] is False


def test_check_tables_complete_subset():
    engine = MagicMock()
    all_tables = set(all_required_tables())
    with patch("database.schema_health.inspect") as mock_inspect:
        mock_inspect.return_value = FakeInspector(all_tables)
        result = check_tables(engine)
    assert result["missing_tables"] == []
    assert result["complete"] is True


def test_partial_schema():
    engine = MagicMock()
    partial = {"airlines", "reviews", "nlp_results", "graph_nodes"}
    with patch("database.schema_health.inspect") as mock_inspect:
        mock_inspect.return_value = FakeInspector(partial)
        report = validate_schema(engine, auto_migrate_dev=False)
    assert not report["healthy"]
    assert "graph_edges" in report["missing_tables"]
    assert report["tables_by_group"]["knowledge_graph"]["graph_edges"] is False
    assert "canonical_aviation_valid" in report
    assert "aviation_missing_columns" in report


def test_empty_database():
    engine = MagicMock()
    with patch("database.schema_health.inspect") as mock_inspect:
        mock_inspect.return_value = FakeInspector(set())
        report = validate_schema(engine, auto_migrate_dev=False)
    assert len(report["missing_tables"]) == len(all_required_tables())
    assert report["healthy"] is False


def test_migration_drift():
    engine = MagicMock()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("0007_forecasting_anomaly",)
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("database.schema_health.inspect") as mock_inspect:
        mock_inspect.return_value = FakeInspector({"alembic_version"})
        with patch(
            "database.schema_health._alembic_head_revision", return_value="0010_aviation_canonical_fields"
        ):
            result = check_migrations(engine)
    assert result["drift"] is True
    assert result["current_revision"] == "0007_forecasting_anomaly"
    assert result["head_revision"] == "0010_aviation_canonical_fields"
