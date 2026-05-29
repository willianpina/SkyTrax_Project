"""Metadata extraction — review_intelligence persistence."""

from __future__ import annotations

import os
import uuid

import pytest

pgvector = pytest.importorskip("pgvector")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analytics.metadata_extractor import run_metadata_extraction, run_metadata_extraction_until_done
from database.models.core import Airline, Review
from database.models.graph import ReviewIntelligence


@pytest.fixture
def metadata_session():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    if db_url.startswith("sqlite"):
        pytest.skip("metadata extractor integration requires PostgreSQL (pgvector types)")
    engine = create_engine(db_url, future=True)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = Session()
    suffix = uuid.uuid4().hex[:8]
    airline = Airline(
        id=str(uuid.uuid4()),
        slug=f"test-air-{suffix}",
        name=f"Test Air {suffix}",
        source="test",
    )
    session.add(airline)
    session.flush()
    for i in range(5):
        session.add(
            Review(
                id=str(uuid.uuid4()),
                airline_id=airline.id,
                source="test",
                external_id=f"ext-{suffix}-{i}",
                fingerprint=f"fp-{suffix}-{i}",
                title=f"Delay on flight {i}",
                text="Terrible delay and lost baggage at JFK to LHR on Boeing 787.",
                rating=2,
            )
        )
    session.flush()
    yield session, airline
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


def _intel_count_for_airline(session, airline_id: str) -> int:
    return (
        session.query(ReviewIntelligence)
        .join(Review, Review.id == ReviewIntelligence.review_id)
        .filter(Review.airline_id == airline_id)
        .count()
    )


def test_metadata_extraction_persists_rows(metadata_session):
    session, airline = metadata_session
    result = run_metadata_extraction(session, batch_size=10)
    assert "error" not in result
    assert result["reviews_analyzed"] == 5
    assert result["remaining"] == 0
    assert _intel_count_for_airline(session, airline.id) == 5


def test_metadata_extraction_idempotent(metadata_session):
    session, airline = metadata_session
    run_metadata_extraction_until_done(session, batch_size=2, max_batches=20)
    second = run_metadata_extraction(session, batch_size=10)
    assert second["reviews_analyzed"] == 0
    assert _intel_count_for_airline(session, airline.id) == 5


def test_metadata_until_done_covers_corpus(metadata_session):
    session, airline = metadata_session
    result = run_metadata_extraction_until_done(session, batch_size=2, max_batches=10)
    assert result["reviews_analyzed"] == 5
    assert result["remaining"] == 0
    assert _intel_count_for_airline(session, airline.id) == 5
