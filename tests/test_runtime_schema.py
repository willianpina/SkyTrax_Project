"""Tests for runtime schema consistency and self-healing behavior."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine, text

from database import runtime_schema


def _sqlite_engine_with_aviation():
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE airline_metadata (
                    id INTEGER PRIMARY KEY,
                    iata_code VARCHAR(16),
                    airline_name VARCHAR(128)
                )
                """
            )
        )
    return engine


def test_validate_runtime_schema_detects_stale_reflection():
    engine = _sqlite_engine_with_aviation()
    with patch("database.runtime_schema.reflected_table_columns", return_value={"id", "airline_name"}):
        report = runtime_schema.validate_runtime_schema_consistency(
            engine,
            "airline_metadata",
            required=["iata_code"],
        )
    assert report["runtime_schema_consistent"] is False
    assert report["stale_reflection_detected"] is True
    assert report["missing_physical_columns"] == []


def test_retry_once_invalidates_runtime_only_once():
    calls = {"fn": 0, "invalidate": 0}

    def flaky():
        calls["fn"] += 1
        if calls["fn"] == 1:
            raise RuntimeError('column "iata_code" does not exist')
        return {"ok": True}

    with patch("database.runtime_schema.invalidate_sqlalchemy_runtime") as mock_invalidate:
        mock_invalidate.side_effect = lambda **_: calls.__setitem__("invalidate", calls["invalidate"] + 1)
        wrapped = runtime_schema.runtime_schema_retry_once(flaky)
        result = wrapped()

    assert result == {"ok": True}
    assert calls["fn"] == 2
    assert calls["invalidate"] == 1


def test_refresh_runtime_after_migrations_delegates_invalidation():
    with patch("database.runtime_schema.invalidate_sqlalchemy_runtime") as mock_invalidate:
        mock_invalidate.return_value = {"engine_generation": 3, "reason": "bootstrap_migration"}
        result = runtime_schema.refresh_sqlalchemy_runtime_after_migrations(reason="bootstrap_migration")

    assert result["engine_generation"] == 3
    assert mock_invalidate.call_count == 1
