"""JSON-safe payload normalization for API governance responses."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

_JSON_PRIMITIVES = (str, int, float, bool, type(None))
_MAX_DEPTH = 32
_MAX_STRING = 16_384


def _record_repair() -> None:
    try:
        from app.observability import record_worker_metric

        record_worker_metric("skytrax_governance_payload_repairs", 1.0)
    except Exception:
        pass


def _record_serialization_error() -> None:
    try:
        from app.observability import record_worker_metric

        record_worker_metric("skytrax_payload_serialization_errors", 1.0)
    except Exception:
        pass


def safe_json_value(value: Any, *, _depth: int = 0) -> Any:
    """Recursively coerce a value into JSON-serializable primitives."""
    if _depth > _MAX_DEPTH:
        return str(value)[:_MAX_STRING]

    if value is None or isinstance(value, _JSON_PRIMITIVES):
        if isinstance(value, str) and len(value) > _MAX_STRING:
            return value[:_MAX_STRING]
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Enum):
        return value.value if hasattr(value, "value") else str(value)

    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")[:_MAX_STRING]
        except Exception:
            return str(value)[:_MAX_STRING]

    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            try:
                out[str(key)] = safe_json_value(item, _depth=_depth + 1)
            except Exception as exc:
                _record_repair()
                logger.debug("[PAYLOAD_SERIALIZATION] key=%s skipped: %s", key, exc)
                out[str(key)] = str(item)[:512]
        return out

    if isinstance(value, (set, frozenset)):
        _record_repair()
        return [safe_json_value(item, _depth=_depth + 1) for item in sorted(value, key=str)]

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [safe_json_value(item, _depth=_depth + 1) for item in value]

    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return safe_json_value(value.to_dict(), _depth=_depth + 1)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return safe_json_value(vars(value), _depth=_depth + 1)
        except Exception:
            pass

    _record_repair()
    return str(value)[:_MAX_STRING]


def safe_json_payload(payload: Any, *, context: str = "") -> dict[str, Any]:
    """Normalize top-level API payloads; always returns a dict."""
    try:
        normalized = safe_json_value(payload)
        if isinstance(normalized, dict):
            return normalized
        return {"value": normalized}
    except Exception as exc:
        _record_serialization_error()
        logger.warning(
            "[PAYLOAD_SERIALIZATION] failed context=%s error=%s",
            context or "unknown",
            exc,
        )
        return {
            "status": "degraded",
            "readiness": "degraded",
            "payload_safe": False,
            "serialization_error": str(exc)[:500],
        }
