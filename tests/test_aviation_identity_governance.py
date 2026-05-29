"""Unit tests for aviation MDM identity governance (slug, merge, resolution)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from aviation.aviation_identity_governance import (
    IdentityStats,
    canonical_airline_slug,
    merge_raw_metadata,
    normalize_iata,
    resolve_airline_identity,
)
from aviation.master_data.sources import OpenFlightsAirline


def test_merge_raw_metadata_shallow_and_nested() -> None:
    assert merge_raw_metadata(None, {"a": 1}) == {"a": 1}
    merged = merge_raw_metadata({"a": {"b": 1}}, {"a": {"c": 2}, "d": 3})
    assert merged["a"]["b"] == 1
    assert merged["a"]["c"] == 2
    assert merged["d"] == 3


def test_normalize_iata_sentinels() -> None:
    assert normalize_iata(None) is None
    assert normalize_iata("\\N") is None
    assert normalize_iata("-") is None
    assert normalize_iata("lh") == "LH"


def test_canonical_slug_space_hyphen_equivalence() -> None:
    a = canonical_airline_slug("Lufthansa Airlines")
    b = canonical_airline_slug("Lufthansa-Airlines")
    c = canonical_airline_slug("Lufthansa  Airlines")
    assert a == b == c == "lufthansa-airlines"


def test_resolve_airline_identity_merge_via_slug_lookup() -> None:
    """Same canonical slug → merge onto existing row; no blind second insert."""
    now = datetime.now(timezone.utc)
    existing = MagicMock()
    existing.slug = "british-airways"
    existing.airline_name = "British Air"
    existing.iata_code = None
    existing.icao_code = None
    existing.callsign = None
    existing.country = None
    existing.canonical_country = None
    existing.region = None
    existing.normalized_name = None
    existing.alliance_id = None
    existing.alliance_code = None
    existing.raw_metadata = {}
    existing.enrichment_confidence = 0.0
    existing.source_confidence = 0.0
    existing.normalization_confidence = 0.0
    existing.metadata_quality_score = 0.0
    existing.enrichment_status = "pending"
    slug_lookup = {"british-airways": existing}
    sess = MagicMock()
    stats = IdentityStats()
    ofa = OpenFlightsAirline(
        openflights_id="99",
        name="British Airways",
        alias="",
        iata="BA",
        icao="BAW",
        callsign="SPEEDBIRD",
        country="United Kingdom",
        active=True,
    )
    ent, action, _changed = resolve_airline_identity(
        sess,
        ofa,
        slug_lookup,
        alliance_id=None,
        alliance_code=None,
        region="Europe",
        now=now,
        identity_stats=stats,
    )
    assert ent is existing
    assert action == "merge"
    sess.add.assert_not_called()


def test_resolve_airline_identity_create_when_missing() -> None:
    now = datetime.now(timezone.utc)
    sess = MagicMock()
    sess.scalar.return_value = None
    slug_lookup: dict[str, MagicMock] = {}
    stats = IdentityStats()
    ofa = OpenFlightsAirline(
        openflights_id="1",
        name="Contoso Airways",
        alias="",
        iata=None,
        icao=None,
        callsign=None,
        country="US",
        active=True,
    )
    _ent, action, changed = resolve_airline_identity(
        sess,
        ofa,
        slug_lookup,
        alliance_id=None,
        alliance_code=None,
        region=None,
        now=now,
        identity_stats=stats,
    )
    assert action == "create"
    assert changed is True
    assert sess.add.call_count == 1
    assert stats.upserts == 1
    assert "contoso-airways" in slug_lookup
