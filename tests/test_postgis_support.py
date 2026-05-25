from __future__ import annotations

import os
from unittest.mock import MagicMock

from database.postgis_support import (
    airports_location_column_exists,
    postgis_requested,
    try_create_postgis_extension,
)


def test_postgis_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_POSTGIS", raising=False)
    assert postgis_requested() is False


def test_postgis_enabled_when_flag_set(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_POSTGIS", "true")
    assert postgis_requested() is True


def test_try_create_postgis_skips_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_POSTGIS", "false")
    connection = MagicMock()
    assert try_create_postgis_extension(connection) is False
    connection.execute.assert_not_called()


def test_try_create_postgis_succeeds_when_available(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_POSTGIS", "true")
    connection = MagicMock()
    assert try_create_postgis_extension(connection) is True


def test_try_create_postgis_handles_missing_extension(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_POSTGIS", "true")
    connection = MagicMock()
    connection.execute.side_effect = Exception('extension "postgis" is not available')
    assert try_create_postgis_extension(connection) is False


def test_airports_location_column_probe() -> None:
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = 1
    assert airports_location_column_exists(connection) is True
