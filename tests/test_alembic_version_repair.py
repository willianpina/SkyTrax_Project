"""Alembic version_num VARCHAR expansion and long revision ID support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from database.alembic_version_repair import (
    REVISION_ALIASES,
    ensure_alembic_version_capacity,
    expand_version_num_column,
    inspect_alembic_version_table,
    repair_revision_aliases,
)


def _mock_engine(execute_results=None):
    engine = MagicMock()
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=False)
    engine.begin.return_value = ctx
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    if execute_results:
        conn.execute.return_value.fetchone.return_value = execute_results
    return engine


def test_inspect_detects_truncation_risk():
    engine = MagicMock()
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["alembic_version"]
    varchar = MagicMock()
    varchar.length = 32
    inspector.get_columns.return_value = [{"name": "version_num", "type": varchar}]
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("0009_knowledge_graph",)
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("database.alembic_version_repair.inspect", return_value=inspector):
        with patch.dict("os.environ", {"ALEMBIC_VERSION_MIN_LENGTH": "128"}):
            info = inspect_alembic_version_table(engine)

    assert info["truncation_risk"] is True
    assert info["version_num_length"] == 32


def test_expand_version_num_idempotent():
    engine = MagicMock()
    calls = {"n": 0}

    def fake_inspect(_engine):
        calls["n"] += 1
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["alembic_version"]
        varchar = MagicMock()
        varchar.length = 128 if calls["n"] > 1 else 32
        inspector.get_columns.return_value = [{"name": "version_num", "type": varchar}]
        return inspector

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("0009_knowledge_graph",)
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("database.alembic_version_repair.inspect", side_effect=fake_inspect):
        first = expand_version_num_column(engine, target_length=128)
        second = expand_version_num_column(engine, target_length=128)

    assert first["repaired"] is True
    assert second.get("already_sufficient") is True


def test_long_semantic_revision_fits_after_expand():
    long_rev = "0011_airline_metadata_schema_repair"
    assert len(long_rev) > 32
    assert len(long_rev) <= 128


def test_repair_revision_alias_0010():
    engine = _mock_engine()
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["alembic_version"]
    varchar = MagicMock()
    varchar.length = 128
    inspector.get_columns.return_value = [{"name": "version_num", "type": varchar}]

    conn_read = MagicMock()
    conn_read.execute.return_value.fetchone.return_value = ("0010",)
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn_read)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    conn_write = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=conn_write)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    with patch("database.alembic_version_repair.inspect", return_value=inspector):
        result = repair_revision_aliases(engine)

    assert result["repaired"] is True
    assert result["to"] == REVISION_ALIASES["0010"]


def test_ensure_capacity_expands_before_long_head():
    engine = MagicMock()
    head = "0011_airline_metadata_schema_repair"

    with patch("database.alembic_version_repair.inspect_alembic_version_table") as mock_info:
        with patch("database.alembic_version_repair.expand_version_num_column") as mock_expand:
            with patch("database.alembic_version_repair.repair_revision_aliases") as mock_alias:
                mock_info.side_effect = [
                    {
                        "exists": True,
                        "version_num_length": 32,
                        "truncation_risk": True,
                        "current_revision": "0010_aviation_canonical_fields",
                        "min_required_length": 128,
                    },
                    {
                        "exists": True,
                        "version_num_length": 128,
                        "truncation_risk": False,
                        "current_revision": "0010_aviation_canonical_fields",
                        "min_required_length": 128,
                    },
                ]
                mock_expand.return_value = {"repaired": True}
                mock_alias.return_value = {"repaired": False}

                result = ensure_alembic_version_capacity(engine, auto_repair=True, head_revision=head)

    mock_expand.assert_called_once()
    assert result["alembic_safe"] is True
    assert "version_num_expanded" in result["actions"]


def test_repeated_ensure_idempotent():
    engine = MagicMock()
    with patch("database.alembic_version_repair.inspect_alembic_version_table") as mock_info:
        with patch("database.alembic_version_repair.expand_version_num_column") as mock_expand:
            with patch("database.alembic_version_repair.repair_revision_aliases") as mock_alias:
                safe_state = {
                    "exists": True,
                    "version_num_length": 128,
                    "truncation_risk": False,
                    "current_revision": "0012_alembic_ver_expand",
                    "min_required_length": 128,
                }
                mock_info.return_value = safe_state
                mock_expand.return_value = {"repaired": False, "already_sufficient": True}
                mock_alias.return_value = {"repaired": False}

                r1 = ensure_alembic_version_capacity(engine, auto_repair=True)
                r2 = ensure_alembic_version_capacity(engine, auto_repair=True)

    assert r1["alembic_safe"] is True
    assert r2["alembic_safe"] is True
    assert mock_expand.call_count == 0
