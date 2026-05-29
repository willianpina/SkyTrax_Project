"""Coverage audit engine -- computes quality, completeness, and readiness scores."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.aviation import (
    Alliance,
    AirlineMetadata,
    AirportMetadata,
    AirlineAirport,
)

logger = logging.getLogger(__name__)


class CoverageAuditEngine:
    def __init__(self, session: Session):
        self.session = session

    def generate_report(self) -> dict[str, Any]:
        airlines = self.session.query(AirlineMetadata).all()
        airports = self.session.query(AirportMetadata).all()
        alliances_count = self.session.query(func.count(Alliance.id)).scalar() or 0

        missing_iata = sum(1 for ap in airports if not ap.iata)
        missing_icao = sum(1 for ap in airports if not ap.icao)
        missing_country_airports = sum(1 for ap in airports if not ap.country)
        missing_country_airlines = sum(1 for al in airlines if not al.country)
        missing_coordinates = sum(1 for ap in airports if ap.latitude is None or ap.longitude is None)

        dupes = self._detect_duplicates(airlines, airports)
        orphans = self._detect_orphans(airlines, airports)
        norm_failures = self._normalization_failures(airlines, airports)

        total_a = len(airlines)
        total_ap = len(airports)

        completeness = self._metadata_completeness(airlines, airports)
        enrichment = self._enrichment_score(airlines, airports)
        graph_ready = self._graph_readiness_score(airlines, airports)
        coverage = self._coverage_score(
            total_a,
            total_ap,
            missing_iata,
            missing_country_airlines + missing_country_airports,
            dupes["total"],
            orphans["total"],
        )

        return {
            "total_airlines": total_a,
            "total_airports": total_ap,
            "total_alliances": alliances_count,
            "missing_iata": missing_iata,
            "missing_icao": missing_icao,
            "missing_country": missing_country_airlines + missing_country_airports,
            "missing_coordinates": missing_coordinates,
            "duplicate_entities": dupes["total"],
            "duplicate_details": dupes["details"],
            "orphan_airports": orphans["airports"],
            "orphan_airlines": orphans["airlines"],
            "normalization_failures": norm_failures,
            "coverage_score": round(coverage, 1),
            "metadata_completeness": round(completeness, 1),
            "enrichment_score": round(enrichment, 1),
            "graph_readiness": round(graph_ready, 1),
        }

    def missing_fields(self) -> dict[str, list[dict[str, Any]]]:
        airlines_missing = []
        for am in self.session.query(AirlineMetadata).all():
            missing = []
            if not am.country:
                missing.append("country")
            if am.star_rating is None:
                missing.append("star_rating")
            if not am.airline_type:
                missing.append("airline_type")
            if missing:
                airlines_missing.append({"slug": am.slug, "name": am.airline_name, "missing": missing})

        airports_missing = []
        for ap in self.session.query(AirportMetadata).all():
            missing = []
            if not ap.iata:
                missing.append("iata")
            if not ap.icao:
                missing.append("icao")
            if not ap.country:
                missing.append("country")
            if ap.latitude is None:
                missing.append("latitude")
            if ap.longitude is None:
                missing.append("longitude")
            if not ap.region:
                missing.append("region")
            if missing:
                airports_missing.append({"name": ap.airport_name, "iata": ap.iata, "missing": missing})

        return {"airlines": airlines_missing, "airports": airports_missing}

    def detect_duplicates(self) -> dict[str, list[dict]]:
        airlines = self.session.query(AirlineMetadata).all()
        airports = self.session.query(AirportMetadata).all()
        return self._detect_duplicates(airlines, airports)

    def detect_orphans(self) -> dict[str, Any]:
        airlines = self.session.query(AirlineMetadata).all()
        airports = self.session.query(AirportMetadata).all()
        return self._detect_orphans(airlines, airports)

    def _detect_duplicates(self, airlines: list, airports: list) -> dict[str, Any]:
        name_counts: dict[str, int] = {}
        details = []
        for am in airlines:
            key = am.airline_name.strip().lower()
            name_counts[key] = name_counts.get(key, 0) + 1
        for name, count in name_counts.items():
            if count > 1:
                details.append({"type": "airline", "name": name, "count": count})

        iata_counts: dict[str, int] = {}
        for ap in airports:
            if ap.iata:
                iata_counts[ap.iata] = iata_counts.get(ap.iata, 0) + 1
        for iata, count in iata_counts.items():
            if count > 1:
                details.append({"type": "airport_iata", "iata": iata, "count": count})

        return {"total": len(details), "details": details}

    def _detect_orphans(self, airlines: list, airports: list) -> dict[str, Any]:
        linked_airline_ids = {row[0] for row in self.session.query(AirlineAirport.airline_metadata_id).all()}
        linked_airport_ids = {row[0] for row in self.session.query(AirlineAirport.airport_metadata_id).all()}
        orphan_airlines = sum(1 for am in airlines if am.id not in linked_airline_ids)
        orphan_airports = sum(1 for ap in airports if ap.id not in linked_airport_ids)
        return {
            "airlines": orphan_airlines,
            "airports": orphan_airports,
            "total": orphan_airlines + orphan_airports,
        }

    def _normalization_failures(self, airlines: list, airports: list) -> int:
        failures = 0
        failures += sum(1 for am in airlines if am.enrichment_confidence < 0.3)
        failures += sum(1 for ap in airports if ap.enrichment_confidence < 0.3)
        return failures

    def _metadata_completeness(self, airlines: list, airports: list) -> float:
        if not airlines and not airports:
            return 0.0

        airline_fields = ["country", "airline_type", "star_rating", "alliance_id"]
        airport_fields = ["iata", "country", "region", "latitude", "longitude"]

        total_checks = 0
        total_filled = 0
        for am in airlines:
            for f in airline_fields:
                total_checks += 1
                if getattr(am, f, None) is not None:
                    total_filled += 1
        for ap in airports:
            for f in airport_fields:
                total_checks += 1
                if getattr(ap, f, None) is not None:
                    total_filled += 1

        return (total_filled / total_checks * 100) if total_checks else 0.0

    def _enrichment_score(self, airlines: list, airports: list) -> float:
        all_confs = [am.enrichment_confidence for am in airlines] + [
            ap.enrichment_confidence for ap in airports
        ]
        return (sum(all_confs) / len(all_confs) * 100) if all_confs else 0.0

    def _graph_readiness_score(self, airlines: list, airports: list) -> float:
        if not airlines and not airports:
            return 0.0

        checks = 0
        passed = 0

        for am in airlines:
            checks += 3
            if am.country:
                passed += 1
            if am.alliance_id:
                passed += 1
            if am.hub_airports:
                passed += 1

        for ap in airports:
            checks += 3
            if ap.iata:
                passed += 1
            if ap.country:
                passed += 1
            if ap.hub_level:
                passed += 1

        link_count = self.session.query(func.count(AirlineAirport.id)).scalar() or 0
        total_possible = max(len(airlines), 1)
        link_ratio = min(link_count / total_possible, 1.0)

        base = (passed / checks * 100) if checks else 0.0
        return base * 0.7 + link_ratio * 100 * 0.3

    def _coverage_score(
        self,
        airlines: int,
        airports: int,
        missing_iata: int,
        missing_country: int,
        duplicates: int,
        orphans: int,
    ) -> float:
        total = airlines + airports
        if total == 0:
            return 0.0
        issues = missing_iata + missing_country + duplicates + orphans
        return max(0.0, (1 - issues / (total * 2)) * 100)
