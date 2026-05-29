from __future__ import annotations

from unittest.mock import MagicMock, patch

from database.aviation_schema import audit_aviation_schema


def test_audit_aviation_schema_detects_missing_columns():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["airline_metadata"]
    inspector.get_columns.return_value = [
        {"name": "id"},
        {"name": "slug"},
        {"name": "airline_name"},
        {"name": "iata"},
    ]
    with (
        patch("database.aviation_schema.inspect", return_value=inspector),
        patch("database.runtime_schema.sa_inspect", return_value=inspector),
    ):
        report = audit_aviation_schema(engine)
    assert report["canonical_aviation_valid"] is False
    assert "iata_code" in report["aviation_missing_columns"]
    assert report["aviation_aliases_detected"].get("iata_code") == "iata"


def test_audit_aviation_schema_ok_when_canonical_present():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["airline_metadata"]
    inspector.get_columns.return_value = [
        {"name": "id"},
        {"name": "slug"},
        {"name": "airline_name"},
        {"name": "iata_code"},
        {"name": "icao_code"},
        {"name": "primary_hub"},
        {"name": "canonical_country"},
        {"name": "normalized_name"},
        {"name": "alliance_code"},
    ]
    with (
        patch("database.aviation_schema.inspect", return_value=inspector),
        patch("database.runtime_schema.sa_inspect", return_value=inspector),
    ):
        report = audit_aviation_schema(engine)
    assert report["canonical_aviation_valid"] is True
    assert report["aviation_missing_columns"] == []
