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
    operational_category: str | None = None
    premium_segment: str | None = None
    hub_classification: str | None = None
    geospatial_context: dict[str, Any] = field(default_factory=dict)
    operational_context: dict[str, Any] = field(default_factory=dict)
    enrichment_confidence: float = 0.0
    methods_used: list[str] = field(default_factory=list)
    matched_aliases: list[str] = field(default_factory=list)
    fallback_matches: list[str] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)


_IATA_PATTERN = re.compile(r"\b([A-Z]{3})\b")


class ReviewEnrichmentPipeline:
    """Stateless enrichment pipeline that decorates reviews with aviation context."""

    def __init__(self, session: Session):
        self.session = session
        self.normalizer = NormalizationEngine(session)

    def enrich(self, airline_slug: str, route: str | None = None, text: str | None = None) -> EnrichmentResult:
        result = EnrichmentResult()
        methods = []
        aliases = []

        airline_norm = self.normalizer.normalize_airline(airline_slug)
        result.lineage["airline_input"] = airline_slug
        result.lineage["airline_method"] = airline_norm.method

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
                result.operational_context["operational_labels"] = am.operational_labels

                if am.is_premium:
                    result.premium_segment = "premium"
                    result.operational_category = "full_service_premium"
                elif am.is_low_cost:
                    result.premium_segment = "economy"
                    result.operational_category = "low_cost_carrier"
                else:
                    result.premium_segment = "standard"
                    result.operational_category = am.airline_type or "full_service"

                methods.append(f"airline:{airline_norm.method}")
                if airline_norm.method in ("alias", "fuzzy"):
                    aliases.append(airline_slug)
        else:
            result.fallback_matches.append(airline_slug)

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
                    ap_info = {
                        "id": ap.id,
                        "name": ap.airport_name,
                        "iata": ap.iata,
                        "country": ap.country,
                        "region": ap.region,
                        "hub_level": ap.hub_level,
                        "confidence": ap_norm.confidence,
                    }
                    if ap.latitude is not None and ap.longitude is not None:
                        ap_info["latitude"] = ap.latitude
                        ap_info["longitude"] = ap.longitude
                    result.airports_detected.append(ap_info)

                    if not result.region and ap.region:
                        result.region = ap.region
                    if ap.hub_level and not result.hub_classification:
                        result.hub_classification = ap.hub_level
                    if ap.latitude is not None and ap.longitude is not None:
                        result.geospatial_context[ap.iata or ap.airport_name] = {
                            "lat": ap.latitude, "lon": ap.longitude,
                        }

                    methods.append(f"airport:{ap_norm.method}")
                    if ap_norm.method in ("alias", "fuzzy"):
                        aliases.append(candidate)
            else:
                result.fallback_matches.append(candidate)

        confidences = [airline_norm.confidence]
        for ap_info in result.airports_detected:
            confidences.append(ap_info["confidence"])
        result.enrichment_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        result.methods_used = methods
        result.matched_aliases = aliases
        result.lineage["airports_candidates"] = len(airport_candidates)
        result.lineage["airports_resolved"] = len(result.airports_detected)

        return result
