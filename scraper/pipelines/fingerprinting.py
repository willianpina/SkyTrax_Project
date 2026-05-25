from __future__ import annotations

import hashlib


def review_fingerprint(*parts: str | None) -> str:
    """Stable hash used for incremental collection and deduplication."""
    normalized = "||".join((part or "").strip().lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
