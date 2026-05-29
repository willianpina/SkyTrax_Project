"""Shared pytest fixtures for the SkyTrax test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Pytest prepends tests/ to sys.path; force repo root before any skytrax imports.
_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NLP_ENABLE_EMBEDDINGS", "false")
os.environ.setdefault("SCHEMA_VALIDATE_ON_STARTUP", "false")
os.environ.setdefault("API_TRUSTED_HOSTS", "testserver,localhost,127.0.0.1")


def _load_fastapi_app():
    """Load api/main.py without relying on top-level `api` package resolution."""
    import importlib.util

    main_path = _ROOT / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("skytrax_api_main", main_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load FastAPI app from {main_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

app = _load_fastapi_app()
from database.session import get_session


@pytest.fixture()
def fake_session():
    """SQLAlchemy-compatible mock session with common method stubs."""
    session = MagicMock(spec_set=["query", "execute", "commit", "rollback", "add", "close"])
    session.query.return_value = session
    session.execute.return_value = MagicMock()
    return session


@pytest.fixture()
def test_client(fake_session):
    """FastAPI TestClient with the DB session dependency replaced by *fake_session*."""

    def _override_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_airline() -> dict:
    """Minimal airline record suitable for unit tests."""
    return {
        "slug": "qatar-airways",
        "airline_name": "Qatar Airways",
        "overall_score": 9.1,
        "review_count": 2473,
    }


@pytest.fixture()
def sample_review() -> dict:
    """Minimal review record suitable for unit tests."""
    return {
        "id": 1,
        "airline": "qatar-airways",
        "title": "Outstanding cabin crew service",
        "content": (
            "Flew QR920 Doha to Bangkok in business class. "
            "The crew were attentive and the food was excellent."
        ),
        "rating": 9,
        "date": "2026-03-15",
    }


@pytest.fixture()
def sample_anomaly() -> dict:
    """Minimal anomaly record suitable for unit tests."""
    return {
        "id": 1,
        "airline": "qatar-airways",
        "anomaly_type": "rating_spike",
        "severity": "high",
        "observed_value": 9.8,
        "expected_value": 7.2,
        "detected_at": datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
    }
