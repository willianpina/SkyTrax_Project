"""Backward-compatibility shim -- canonical location is scraper.pipelines.fingerprinting."""

from scraper.pipelines.fingerprinting import review_fingerprint  # noqa: F401

__all__ = ["review_fingerprint"]
