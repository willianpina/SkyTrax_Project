"""Alembic version table repair — supports long semantic revision IDs."""

from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DEFAULT_MIN_LENGTH = 128
TARGET_VARCHAR_LENGTH = 128

# Orphan short revision ids from broken migration chain.
REVISION_ALIASES: dict[str, str] = {
    "0010": "0010_aviation_canonical_fields",
    "0009": "0009_knowledge_graph",
}


def _min_length_from_env() -> int:
    try:
        return max(32, int(os.getenv("ALEMBIC_VERSION_MIN_LENGTH", str(DEFAULT_MIN_LENGTH))))
    except ValueError:
        return DEFAULT_MIN_LENGTH


def _auto_repair_enabled() -> bool:
    return os.getenv("ALEMBIC_VERSION_AUTO_REPAIR", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def inspect_alembic_version_table(engine: Engine) -> dict[str, Any]:
    """Validate alembic_version structure and version_num capacity."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "alembic_version" not in tables:
        logger.warning("[ALEMBIC] alembic_version table missing")
        return {
            "exists": False,
            "version_num_length": 0,
            "version_num_type": None,
            "truncation_risk": True,
            "current_revision": None,
            "current_revision_length": 0,
        }

    col_info: dict[str, Any] = {}
    for col in inspector.get_columns("alembic_version"):
        if col["name"] == "version_num":
            col_info = col
            break

    length = col_info.get("type").length if col_info.get("type") is not None else None
    if length is None:
        length = _infer_varchar_length(engine)

    current: str | None = None
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            current = row[0] if row else None
    except Exception as exc:
        logger.warning("[ALEMBIC] read version_num failed: %s", exc)

    min_required = _min_length_from_env()
    truncation_risk = length is not None and int(length) < min_required

    logger.info(
        "[SCHEMA] alembic_version version_num type=varchar(%s) current=%s len=%s",
        length,
        current,
        len(current) if current else 0,
    )

    return {
        "exists": True,
        "version_num_length": int(length) if length is not None else 0,
        "version_num_type": str(col_info.get("type", "unknown")),
        "truncation_risk": truncation_risk,
        "current_revision": current,
        "current_revision_length": len(current) if current else 0,
        "min_required_length": min_required,
    }


def _infer_varchar_length(engine: Engine) -> int | None:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'alembic_version' AND column_name = 'version_num'"
                )
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def expand_version_num_column(
    engine: Engine,
    *,
    target_length: int | None = None,
) -> dict[str, Any]:
    """Idempotently widen alembic_version.version_num to VARCHAR(target_length)."""
    target = target_length or _min_length_from_env()
    info = inspect_alembic_version_table(engine)
    if not info.get("exists"):
        return {"repaired": False, "reason": "table_missing", **info}

    current_len = info.get("version_num_length") or 0
    if current_len >= target:
        logger.info("[ALEMBIC] version_num already varchar(%s) — skip expand", current_len)
        return {
            "repaired": False,
            "already_sufficient": True,
            "version_num_length": current_len,
            "target": target,
        }

    logger.warning(
        "[MIGRATION] Expanding alembic_version.version_num %s -> %s",
        current_len,
        target,
    )
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({target})"))
    except Exception as exc:
        logger.error("[ALEMBIC] expand version_num failed: %s", exc)
        return {"repaired": False, "error": str(exc), **info}

    after = inspect_alembic_version_table(engine)
    logger.info("[ALEMBIC] version_num expanded to %s", after.get("version_num_length"))
    return {
        "repaired": True,
        "previous_length": current_len,
        "version_num_length": after.get("version_num_length"),
        "target": target,
    }


def repair_revision_aliases(engine: Engine) -> dict[str, Any]:
    """Fix known orphan short revision ids in alembic_version."""
    info = inspect_alembic_version_table(engine)
    current = info.get("current_revision")
    if not current or current not in REVISION_ALIASES:
        return {"repaired": False, "current_revision": current}

    canonical = REVISION_ALIASES[current]
    if len(canonical) > (info.get("version_num_length") or 32):
        expand_version_num_column(engine)

    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE alembic_version SET version_num = :rev"),
                {"rev": canonical},
            )
        logger.info("[ALEMBIC] Repaired revision alias %s -> %s", current, canonical)
        return {"repaired": True, "from": current, "to": canonical}
    except Exception as exc:
        logger.error("[ALEMBIC] revision alias repair failed: %s", exc)
        return {"repaired": False, "error": str(exc), "from": current, "to": canonical}


def ensure_alembic_version_capacity(
    engine: Engine,
    *,
    auto_repair: bool | None = None,
    head_revision: str | None = None,
) -> dict[str, Any]:
    """Pre-flight: expand column and fix aliases before alembic upgrade."""
    if auto_repair is None:
        auto_repair = _auto_repair_enabled()

    info = inspect_alembic_version_table(engine)
    head = head_revision
    if head is None:
        try:
            from database.schema_health import _alembic_head_revision

            head = _alembic_head_revision()
        except Exception:
            pass

    head_len = len(head) if head else 0
    required = max(_min_length_from_env(), head_len)
    info["head_revision"] = head
    info["head_revision_length"] = head_len
    info["required_length"] = required

    actions: list[str] = []
    expand_result: dict[str, Any] = {"repaired": False}

    needs_expand = info.get("truncation_risk") or (
        head_len > 0 and (info.get("version_num_length") or 0) < head_len
    )

    if needs_expand and auto_repair:
        expand_result = expand_version_num_column(engine, target_length=max(required, TARGET_VARCHAR_LENGTH))
        if expand_result.get("repaired"):
            actions.append("version_num_expanded")
        info = inspect_alembic_version_table(engine)
    elif needs_expand:
        logger.warning("[ALEMBIC] truncation risk — auto repair disabled")
        actions.append("truncation_risk_unrepaired")

    alias_result = repair_revision_aliases(engine)
    if alias_result.get("repaired"):
        actions.append("revision_alias_fixed")
        info = inspect_alembic_version_table(engine)

    safe = not (
        info.get("truncation_risk") or (head_len > 0 and (info.get("version_num_length") or 0) < head_len)
    )

    return {
        **info,
        "alembic_safe": safe,
        "alembic_version_length": info.get("version_num_length"),
        "actions": actions,
        "expand_result": expand_result,
        "alias_result": alias_result,
    }


def check_migration_chain(engine: Engine) -> dict[str, Any]:
    """Verify alembic script head vs DB version and column capacity."""
    from database.schema_health import _alembic_head_revision

    head = _alembic_head_revision()
    info = inspect_alembic_version_table(engine)
    current = info.get("current_revision")

    chain_valid = True
    errors: list[str] = []

    if not head:
        chain_valid = False
        errors.append("head_revision_unresolved")

    if current and current in REVISION_ALIASES:
        chain_valid = False
        errors.append(f"orphan_revision:{current}")
    elif current:
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            from database.schema_health import ALEMBIC_INI

            if ALEMBIC_INI.is_file():
                script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
                known = {r.revision for r in script.walk_revisions()}
                if current not in known:
                    chain_valid = False
                    errors.append(f"unknown_revision:{current}")
        except Exception as exc:
            chain_valid = False
            errors.append(f"chain_check_failed:{exc}")

    head_len = len(head) if head else 0
    col_len = info.get("version_num_length") or 0
    if head_len > col_len:
        chain_valid = False
        errors.append("head_exceeds_version_num_capacity")

    return {
        "migration_chain_valid": chain_valid,
        "head_revision": head,
        "current_revision": current,
        "errors": errors,
    }
