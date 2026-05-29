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
from database.session import Base


@pytest.fixture
def metadata_session():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    if db_url.startswith("sqlite"):
        pytest.skip("metadata extractor integration requires PostgreSQL (pgvector types)")
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    airline = Airline(
        id=str(uuid.uuid4()),
        slug="test-air",
        name="Test Air",
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
                external_id=f"ext-{i}",
                fingerprint=f"fp-{i}",
                title=f"Delay on flight {i}",
                text="Terrible delay and lost baggage at JFK to LHR on Boeing 787.",
                rating=2,
            )
        )
    session.commit()
    yield session
    session.close()


def test_metadata_extraction_persists_rows(metadata_session):
    result = run_metadata_extraction(metadata_session, batch_size=10)
    assert "error" not in result
    assert result["reviews_analyzed"] == 5
    assert result["metadata_total"] == 5
    assert result["remaining"] == 0
    count = metadata_session.query(ReviewIntelligence).count()
    assert count == 5


def test_metadata_extraction_idempotent(metadata_session):
    run_metadata_extraction_until_done(metadata_session, batch_size=2, max_batches=20)
    second = run_metadata_extraction(metadata_session, batch_size=10)
    assert second["reviews_analyzed"] == 0
    assert second["metadata_total"] == 5


def test_metadata_until_done_covers_corpus(metadata_session):
    result = run_metadata_extraction_until_done(metadata_session, batch_size=2, max_batches=10)
    assert result["reviews_analyzed"] == 5
    assert result["remaining"] == 0
