"""Temporary domain audit logging for Aviation / Hubs / Alliances / Coverage."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DOMAINS = frozenset({"AVIATION", "HUBS", "ALLIANCES", "COVERAGE"})


def log_domain(
    domain: str,
    *,
    endpoint: str = "",
    records_found: int | None = None,
    records_loaded: int | None = None,
    records_returned: int | None = None,
    records_rendered: int | None = None,
    query_time_ms: float | None = None,
    response_size: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Structured log line for cross-layer aviation audits."""
    tag = domain.upper()
    if tag not in _DOMAINS:
        tag = "AVIATION"
    parts = [f"[{tag}]"]
    if endpoint:
        parts.append(f"endpoint={endpoint}")
    if records_found is not None:
        parts.append(f"records_found={records_found}")
    if records_loaded is not None:
        parts.append(f"records_loaded={records_loaded}")
    if records_returned is not None:
        parts.append(f"records_returned={records_returned}")
    if records_rendered is not None:
        parts.append(f"records_rendered={records_rendered}")
    if query_time_ms is not None:
        parts.append(f"query_time_ms={query_time_ms}")
    if response_size is not None:
        parts.append(f"response_size={response_size}")
    if extra:
        parts.append(" ".join(f"{k}={v}" for k, v in extra.items()))
    logger.info(" ".join(parts))
