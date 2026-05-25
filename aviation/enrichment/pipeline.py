"""Enrich incoming reviews with aviation metadata context."""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from aviation.normalization.engine import NormalizationEngine
from database.models.aviation import AirlineMetadata, AirportMetadata

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    airline_metadata_id: str | None = None
    airline_canonical: str | None = None
    alliance: str | None = None
    airline_type: str | None = None
    star_rating: int | None = None
    airports_detected: list[dict[str, Any]] = field(default_factory=list)
    region: str | None = None
    operational_context: dict[str, Any] = field(default_factory=dict)
    enrichment_confidence: float = 0.0
    methods_used: list[str] = field(default_factory=list)


_IATA_PATTERN = re.compile(r"\b([A-Z]{3})\b")


class ReviewEnrichmentPipeline:
    """Stateless enrichment pipeline that decorates reviews with aviation context."""

    def __init__(self, session: Session):
        self.session = session
        self.normalizer = NormalizationEngine(session)

    def enrich(self, airline_slug: str, route: str | None = None, text: str | None = None) -> EnrichmentResult:
        result = EnrichmentResult()
        methods = []

        airline_norm = self.normalizer.normalize_airline(airline_slug)
        if airline_norm.entity_id:
            am = self.session.query(AirlineMetadata).get(airline_norm.entity_id)
            if am:
                result.airline_metadata_id = am.id
                result.airline_canonical = am.airline_name
                result.airline_type = am.airline_type
                result.star_rating = am.star_rating
                if am.alliance_rel:
                    result.alliance = am.alliance_rel.name
                result.operational_context["hub_airports"] = am.hub_airports
                result.operational_context["certifications"] = am.certifications
                result.operational_context["is_premium"] = am.is_premium
                result.operational_context["is_low_cost"] = am.is_low_cost
                methods.append(f"airline:{airline_norm.method}")

        airport_candidates = set()
        if route:
            for part in re.split(r"[-–/\s]+", route):
                clean = part.strip()
                if len(clean) >= 2:
                    airport_candidates.add(clean)

        if text:
            for match in _IATA_PATTERN.finditer(text):
                airport_candidates.add(match.group(1))

        for candidate in airport_candidates:
            ap_norm = self.normalizer.normalize_airport(candidate)
            if ap_norm.entity_id:
                ap = self.session.query(AirportMetadata).get(ap_norm.entity_id)
                if ap:
                    result.airports_detected.append({
                        "id": ap.id,
                        "name": ap.airport_name,
                        "iata": ap.iata,
                        "country": ap.country,
                        "region": ap.region,
                        "hub_level": ap.hub_level,
                        "confidence": ap_norm.confidence,
                    })
                    if not result.region and ap.region:
                        result.region = ap.region
                    methods.append(f"airport:{ap_norm.method}")

        confidences = [airline_norm.confidence]
        for ap_info in result.airports_detected:
            confidences.append(ap_info["confidence"])
        result.enrichment_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        result.methods_used = methods

        return result
