"""Semantic schema drift detection — airline_metadata column mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from database.schema_semantic import (
    COLUMN_ALIASES,
    check_table_semantic_drift,
    resolve_physical_column,
    stages_blocked_by_semantic_drift,
)


def test_resolve_physical_column_prefers_canonical():
    db = {"iata_code", "slug", "airline_name"}
    assert resolve_physical_column("airline_metadata", "iata_code", db) == "iata_code"


def test_resolve_physical_column_finds_legacy_iata():
    db = {"iata", "slug", "airline_name"}
    assert resolve_physical_column("airline_metadata", "iata_code", db) == "iata"


def test_semantic_drift_detects_missing_iata_code():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["airline_metadata"]
    inspector.get_columns.return_value = [
        {"name": "id"},
        {"name": "slug"},
        {"name": "airline_name"},
    ]
    with (
        patch("database.schema_semantic.inspect", return_value=inspector),
        patch("database.runtime_schema.sa_inspect", return_value=inspector),
    ):
        result = check_table_semantic_drift(engine, "airline_metadata", required=["iata_code"])
    assert result["drift"] is True
    assert "iata_code" in result["missing_columns"]


def test_semantic_drift_ok_with_legacy_mapping_only():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["airline_metadata"]
    inspector.get_columns.return_value = [
        {"name": "id"},
        {"name": "slug"},
        {"name": "iata"},
        {"name": "icao"},
    ]
    with (
        patch("database.schema_semantic.inspect", return_value=inspector),
        patch("database.runtime_schema.sa_inspect", return_value=inspector),
    ):
        result = check_table_semantic_drift(
            engine,
            "airline_metadata",
            required=["iata_code", "icao_code"],
        )
    assert result["drift"] is False
    assert result["legacy_mappings"]["iata_code"] == "iata"
    assert result["legacy_mappings"]["icao_code"] == "icao"


def test_stages_blocked_when_iata_code_missing():
    report = {
        "tables": [
            {
                "table": "airline_metadata",
                "drift": True,
                "missing_columns": ["iata_code"],
            }
        ],
    }
    blocked = stages_blocked_by_semantic_drift(report)
    assert "aviation_master" in blocked
    assert "knowledge_graph" in blocked
    assert "fusion" in blocked


def test_column_aliases_include_iata():
    assert "iata" in COLUMN_ALIASES["airline_metadata"]["iata_code"]
