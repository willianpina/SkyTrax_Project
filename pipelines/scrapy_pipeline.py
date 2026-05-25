"""Backward-compatibility shim -- canonical location is scraper.pipelines.scrapy_pipeline."""

from scraper.pipelines.scrapy_pipeline import (  # noqa: F401
    FingerprintPipeline,
    PostgresPersistencePipeline,
    ValidationPipeline,
)

__all__ = [
    "FingerprintPipeline",
    "PostgresPersistencePipeline",
    "ValidationPipeline",
]
