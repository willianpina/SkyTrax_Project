#!/usr/bin/env python3
"""Repair Alembic chain — version_num capacity, aliases, aviation migrations.

1. Expand alembic_version.version_num to VARCHAR(128) if truncated (32)
2. Fix orphan revision ids (0010 -> 0010_aviation_canonical_fields)
3. Run alembic upgrade head
4. Revalidate schema

Usage:
    PYTHONPATH=. python scripts/repair_alembic_aviation.py
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("repair_alembic")


def main() -> int:
    from database.alembic_version_repair import (
        check_migration_chain,
        ensure_alembic_version_capacity,
        inspect_alembic_version_table,
    )
    from database.schema_health import bootstrap_schema, run_migrations_upgrade
    from database.session import engine

    info = inspect_alembic_version_table(engine)
    if not info.get("exists"):
        logger.error("[ALEMBIC] alembic_version table missing — run initial migrations first")
        return 1

    logger.info(
        "[SCHEMA] alembic_version varchar(%s) revision=%s (len=%s)",
        info.get("version_num_length"),
        info.get("current_revision"),
        info.get("current_revision_length"),
    )

    head = None
    try:
        from database.schema_health import _alembic_head_revision

        head = _alembic_head_revision()
        logger.info("[MIGRATION] Target head revision=%s (len=%s)", head, len(head) if head else 0)
    except Exception as exc:
        logger.warning("[MIGRATION] Could not resolve head: %s", exc)

    if head and len(head) > (info.get("version_num_length") or 0):
        logger.warning(
            "[ALEMBIC] Truncation risk: head revision (%d chars) exceeds version_num (%s)",
            len(head),
            info.get("version_num_length"),
        )

    preflight = ensure_alembic_version_capacity(engine, head_revision=head)
    if preflight.get("actions"):
        logger.info("[ALEMBIC] Pre-flight repairs: %s", ", ".join(preflight["actions"]))
    if not preflight.get("alembic_safe"):
        logger.error(
            "[ALEMBIC] version_num still unsafe (length=%s) — set ALEMBIC_VERSION_AUTO_REPAIR=true",
            preflight.get("version_num_length"),
        )
        return 1

    chain_before = check_migration_chain(engine)
    logger.info("[MIGRATION] Chain valid before upgrade: %s", chain_before.get("migration_chain_valid"))

    logger.info("[MIGRATION] Running alembic upgrade head...")
    upgrade_result = run_migrations_upgrade(engine)
    if not upgrade_result.get("success"):
        logger.error("[MIGRATION] Upgrade failed: %s", upgrade_result.get("error"))
        return 1

    chain_after = check_migration_chain(engine)
    logger.info(
        "[MIGRATION] Chain valid after upgrade: %s current=%s head=%s",
        chain_after.get("migration_chain_valid"),
        chain_after.get("current_revision"),
        chain_after.get("head_revision"),
    )

    report, _ = bootstrap_schema(engine)
    final_info = inspect_alembic_version_table(engine)

    logger.info(
        "[SCHEMA] Final alembic_version varchar(%s) revision=%s",
        final_info.get("version_num_length"),
        final_info.get("current_revision"),
    )

    if report.get("semantic_drift"):
        logger.warning("[SCHEMA] Semantic drift remains: %s", report.get("semantic_audit"))

    if report.get("healthy") and chain_after.get("migration_chain_valid"):
        logger.info("[SCHEMA] Repair complete — schema healthy at %s", report.get("current_revision"))
        return 0

    logger.error(
        "[SCHEMA] Still unhealthy: missing=%s semantic=%s alembic_safe=%s chain=%s",
        report.get("missing_tables"),
        report.get("semantic_drift"),
        report.get("alembic_safe"),
        chain_after.get("errors"),
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
