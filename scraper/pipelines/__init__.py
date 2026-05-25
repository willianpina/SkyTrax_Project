"""Scrapy item pipelines for validation, fingerprinting, and persistence."""

from scraper.pipelines.fingerprinting import review_fingerprint
from scraper.pipelines.scrapy_pipeline import (
    FingerprintPipeline,
    PostgresPersistencePipeline,
    ValidationPipeline,
)

__all__ = [
    "FingerprintPipeline",
    "PostgresPersistencePipeline",
    "ValidationPipeline",
    "review_fingerprint",
]
