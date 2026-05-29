"""Operational validator for aviation metadata entities."""

from __future__ import annotations

import re
import logging
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from database.models.aviation import AirlineMetadata, AirportMetadata, Alliance

logger = logging.getLogger(__name__)

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_ICAO_RE = re.compile(r"^[A-Z]{4}$")

KNOWN_ALLIANCES = {"oneworld", "star alliance", "skyteam"}


class AviationValidator:
    """Run structural and semantic validation across aviation metadata."""

    def __init__(self, session: Session):
        self.session = session

    def validate_all(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []

        issues.extend(self._validate_airlines())
        issues.extend(self._validate_airports())
        issues.extend(self._validate_alliances())

        severity_counts = Counter(i["severity"] for i in issues)

        return {
            "total_issues": len(issues),
            "critical": severity_counts.get("critical", 0),
            "warning": severity_counts.get("warning", 0),
            "info": severity_counts.get("info", 0),
            "issues": issues,
        }

    def _validate_airlines(self) -> list[dict[str, Any]]:
        issues = []
        airlines = self.session.query(AirlineMetadata).all()
        slug_counts: dict[str, int] = {}

        for am in airlines:
            slug_counts[am.slug] = slug_counts.get(am.slug, 0) + 1

            if not am.airline_name or len(am.airline_name.strip()) < 2:
                issues.append(
                    {
                        "entity": "airline",
                        "slug": am.slug,
                        "severity": "critical",
                        "code": "INVALID_NAME",
                        "message": f"Airline name too short or empty: '{am.airline_name}'",
                    }
                )

            if am.country and len(am.country) < 2:
                issues.append(
                    {
                        "entity": "airline",
                        "slug": am.slug,
                        "severity": "warning",
                        "code": "INVALID_COUNTRY",
                        "message": f"Suspicious country value: '{am.country}'",
                    }
                )

            if am.star_rating is not None and (am.star_rating < 1 or am.star_rating > 7):
                issues.append(
                    {
                        "entity": "airline",
                        "slug": am.slug,
                        "severity": "warning",
                        "code": "INVALID_STAR_RATING",
                        "message": f"Star rating out of range: {am.star_rating}",
                    }
                )

            if am.enrichment_confidence < 0.3:
                issues.append(
                    {
                        "entity": "airline",
                        "slug": am.slug,
                        "severity": "info",
                        "code": "LOW_CONFIDENCE",
                        "message": f"Low enrichment confidence: {am.enrichment_confidence}",
                    }
                )

        for slug, count in slug_counts.items():
            if count > 1:
                issues.append(
                    {
                        "entity": "airline",
                        "slug": slug,
                        "severity": "critical",
                        "code": "DUPLICATE_SLUG",
                        "message": f"Duplicate airline slug ({count} records)",
                    }
                )

        return issues

    def _validate_airports(self) -> list[dict[str, Any]]:
        issues = []
        airports = self.session.query(AirportMetadata).all()

        for ap in airports:
            if ap.iata and not _IATA_RE.match(ap.iata):
                issues.append(
                    {
                        "entity": "airport",
                        "name": ap.airport_name,
                        "iata": ap.iata,
                        "severity": "critical",
                        "code": "INVALID_IATA",
                        "message": f"Malformed IATA code: '{ap.iata}'",
                    }
                )

            if ap.icao and not _ICAO_RE.match(ap.icao):
                issues.append(
                    {
                        "entity": "airport",
                        "name": ap.airport_name,
                        "severity": "warning",
                        "code": "INVALID_ICAO",
                        "message": f"Malformed ICAO code: '{ap.icao}'",
                    }
                )

            if ap.latitude is not None and (ap.latitude < -90 or ap.latitude > 90):
                issues.append(
                    {
                        "entity": "airport",
                        "name": ap.airport_name,
                        "severity": "critical",
                        "code": "INVALID_LATITUDE",
                        "message": f"Latitude out of range: {ap.latitude}",
                    }
                )

            if ap.longitude is not None and (ap.longitude < -180 or ap.longitude > 180):
                issues.append(
                    {
                        "entity": "airport",
                        "name": ap.airport_name,
                        "severity": "critical",
                        "code": "INVALID_LONGITUDE",
                        "message": f"Longitude out of range: {ap.longitude}",
                    }
                )

            if not ap.country:
                issues.append(
                    {
                        "entity": "airport",
                        "name": ap.airport_name,
                        "severity": "warning",
                        "code": "MISSING_COUNTRY",
                        "message": "Airport has no country",
                    }
                )

        return issues

    def _validate_alliances(self) -> list[dict[str, Any]]:
        issues = []
        alliances = self.session.query(Alliance).all()

        for alliance in alliances:
            if alliance.name.strip().lower() not in KNOWN_ALLIANCES:
                issues.append(
                    {
                        "entity": "alliance",
                        "name": alliance.name,
                        "severity": "info",
                        "code": "UNKNOWN_ALLIANCE",
                        "message": f"Non-standard alliance name: '{alliance.name}'",
                    }
                )

            members = self.session.query(AirlineMetadata).filter_by(alliance_id=alliance.id).count()
            if members == 0:
                issues.append(
                    {
                        "entity": "alliance",
                        "name": alliance.name,
                        "severity": "warning",
                        "code": "EMPTY_ALLIANCE",
                        "message": "Alliance has no member airlines",
                    }
                )

        return issues

    def normalization_report(self) -> dict[str, Any]:
        airlines = self.session.query(AirlineMetadata).all()
        airports = self.session.query(AirportMetadata).all()

        airline_confs = [am.normalization_confidence for am in airlines]
        airport_confs = [ap.normalization_confidence for ap in airports]
        all_confs = airline_confs + airport_confs

        return {
            "total_entities": len(all_confs),
            "avg_confidence": round(sum(all_confs) / len(all_confs), 3) if all_confs else 0.0,
            "high_confidence": sum(1 for c in all_confs if c >= 0.8),
            "medium_confidence": sum(1 for c in all_confs if 0.5 <= c < 0.8),
            "low_confidence": sum(1 for c in all_confs if c < 0.5),
            "airline_avg": round(sum(airline_confs) / len(airline_confs), 3) if airline_confs else 0.0,
            "airport_avg": round(sum(airport_confs) / len(airport_confs), 3) if airport_confs else 0.0,
        }
