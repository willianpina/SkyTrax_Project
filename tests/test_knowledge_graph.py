"""Tests for the metadata extractor, knowledge graph, fusion engine, and source registry."""

from __future__ import annotations

from analytics.metadata_extractor import ReviewIntelligenceExtractor
from analytics.source_registry import (
    IngestedItem,
    SourceConfig,
    SourceType,
    list_sources,
)


def test_disruption_extraction_delay() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("My flight was delayed by 3 hours and then cancelled.")
    assert result["disruptions"]["delay"] is True
    assert result["disruptions"]["cancellation"] is True
    assert result["disruptions"]["baggage_loss"] is False


def test_disruption_extraction_baggage() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("They lost my luggage and I never got it back.")
    assert result["disruptions"]["baggage_loss"] is True


def test_quality_score_positive() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("The crew were excellent and the food was amazing and delicious.")
    assert result["quality_scores"].get("crew", 0) > 0
    assert result["quality_scores"].get("food", 0) > 0


def test_quality_score_negative() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("The seat was cramped and uncomfortable. Dirty cabin.")
    assert result["quality_scores"].get("seat", 0) < 0


def test_aircraft_extraction() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Flew on a Boeing 777-300ER, great plane.")
    assert any("Boeing" in ac for ac in result["aircraft_mentions"])


def test_aircraft_from_metrics() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Nice flight.", metrics={"aircraft": "A380"})
    assert "A380" in result["aircraft_mentions"]


def test_route_extraction() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Flew LHR to DXB on Emirates.")
    assert any(r.get("origin") == "LHR" and r.get("destination") == "DXB" for r in result["route_mentions"])


def test_severity_critical() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract(
        "Flight delayed 5 hours, then cancelled. Lost luggage too. "
        "Terrible crew, disgusting food, horrible seat."
    )
    assert result["operational_severity"] in ("critical", "high")


def test_severity_low_for_positive() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Wonderful flight, excellent crew, great food.")
    assert result["operational_severity"] == "low"


def test_source_registry_lists_skytrax() -> None:
    sources = list_sources()
    names = [s.name for s in sources]
    assert "skytrax" in names


def test_source_config_dataclass() -> None:
    cfg = SourceConfig(name="test", source_type=SourceType.REVIEW, base_url="https://example.com")
    assert cfg.enabled is False
    assert cfg.priority == 100


def test_ingested_item_defaults() -> None:
    item = IngestedItem(source="test", external_id="1", content="hello")
    assert item.rating is None
    assert item.airline_ref == ""


def test_no_disruptions_in_positive_text() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Great flight, on time, lovely food.")
    assert not any(result["disruptions"].values())


def test_missed_connection_detection() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("I missed my connection due to the late arrival.")
    assert result["disruptions"]["missed_connection"] is True


def test_overbooking_detection() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("We were denied boarding because the flight was overbooked.")
    assert result["disruptions"]["overbooking"] is True


def test_multiple_aircraft_extraction() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Flew a Boeing 737 outbound and an Airbus A320 on return.")
    assert len(result["aircraft_mentions"]) >= 2


def test_airport_code_extraction_filters_common_words() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("THE flight WAS great AND on time")
    assert "THE" not in result["airport_mentions"]
    assert "WAS" not in result["airport_mentions"]
    assert "AND" not in result["airport_mentions"]


def test_quality_empty_for_irrelevant_text() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Nothing to report.")
    assert result["quality_scores"] == {}


def test_route_from_metrics() -> None:
    extractor = ReviewIntelligenceExtractor()
    result = extractor.extract("Nice flight.", metrics={"route": "London to Dubai"})
    assert any(r.get("source") == "metadata" for r in result["route_mentions"])
