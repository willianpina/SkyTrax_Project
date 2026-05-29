"""Unified aviation intelligence service."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.aviation import (
    Alliance,
    AirlineMetadata,
    AirportMetadata,
    AirlineAirport,
)
from database.models.core import Airline, Review
from database.models.analytics import AnomalyEvent

logger = logging.getLogger(__name__)


class AviationIntelligenceService:
    def __init__(self, session: Session):
        self.session = session

    def _operational_airline_rows(self, limit: int = 100) -> list[dict[str, Any]]:
        """Metadata-first airline list with fallback to core airlines + reputation."""
        rows = (
            self.session.query(AirlineMetadata)
            .order_by(AirlineMetadata.star_rating.desc().nullslast())
            .limit(limit)
            .all()
        )
        if rows:
            return [
                {
                    "slug": r.slug,
                    "name": r.airline_name,
                    "country": r.country or r.canonical_country,
                    "airline_type": r.airline_type,
                    "star_rating": r.star_rating,
                    "is_premium": r.is_premium,
                    "is_low_cost": r.is_low_cost,
                    "alliance": r.alliance_rel.name if r.alliance_rel else r.alliance_code,
                    "hub_airports": r.hub_airports,
                    "enrichment_confidence": r.enrichment_confidence,
                    "avg_rating": None,
                    "review_count": 0,
                    "classification": r.airline_type or "full_service",
                    "source": "airline_metadata",
                }
                for r in rows
            ]

        from analytics.intelligence.reputation import ReputationService

        try:
            scores = {s["slug"]: s for s in ReputationService(self.session).airline_scores(min_reviews=1)}
        except Exception:
            scores = {}

        core = (
            self.session.query(Airline)
            .filter(Airline.is_active.is_(True))
            .order_by(Airline.name)
            .limit(limit)
            .all()
        )
        out: list[dict[str, Any]] = []
        for airline in core:
            rep = scores.get(airline.slug) or {}
            score = rep.get("score")
            star = round(min(5.0, max(1.0, float(score) / 20.0)), 1) if score is not None else None
            out.append(
                {
                    "slug": airline.slug,
                    "name": airline.name,
                    "country": airline.country,
                    "airline_type": "full_service",
                    "star_rating": star,
                    "is_premium": False,
                    "is_low_cost": False,
                    "alliance": rep.get("alliance"),
                    "hub_airports": [],
                    "enrichment_confidence": 0.5,
                    "avg_rating": round(float(rep.get("rating_component", 0) or 0) * 10, 2),
                    "review_count": rep.get("review_count", 0),
                    "classification": rep.get("airline_type") or "operational",
                    "source": "airlines_fallback",
                }
            )
        return sorted(out, key=lambda r: r.get("review_count", 0), reverse=True)

    def alliance_intelligence(self) -> list[dict[str, Any]]:
        alliances = self.session.query(Alliance).all()
        result = []
        for alliance in alliances:
            members = self.session.query(AirlineMetadata).filter_by(alliance_id=alliance.id).all()
            member_slugs = [m.slug for m in members]

            airlines = (
                self.session.query(Airline).filter(Airline.slug.in_(member_slugs)).all()
                if member_slugs
                else []
            )
            airline_ids = [a.id for a in airlines]

            review_count = 0
            avg_rating = 0.0
            if airline_ids:
                stats = (
                    self.session.query(func.count(Review.id), func.avg(Review.rating))
                    .filter(Review.airline_id.in_(airline_ids))
                    .first()
                )
                review_count = stats[0] or 0
                avg_rating = round(float(stats[1] or 0), 2)

            anomaly_count = 0
            if airline_ids:
                anomaly_count = (
                    self.session.query(func.count(AnomalyEvent.id))
                    .filter(AnomalyEvent.airline_id.in_(airline_ids))
                    .scalar()
                    or 0
                )

            result.append(
                {
                    "id": alliance.id,
                    "name": alliance.name,
                    "member_count": len(members),
                    "members": [
                        {"slug": m.slug, "name": m.airline_name, "star_rating": m.star_rating}
                        for m in members
                    ],
                    "total_reviews": review_count,
                    "avg_rating": avg_rating,
                    "anomaly_count": anomaly_count,
                    "operational_risk": min(100, anomaly_count * 8),
                }
            )
        if result:
            return result

        # Fallback: group by alliance_code when Alliance rows exist but FK links are missing
        grouped: dict[str, list[AirlineMetadata]] = defaultdict(list)
        for am in self.session.query(AirlineMetadata).filter(AirlineMetadata.alliance_code.isnot(None)).all():
            code = (am.alliance_code or "").strip()
            if code:
                grouped[code].append(am)

        for code, members in grouped.items():
            member_slugs = [m.slug for m in members]
            airlines = (
                self.session.query(Airline).filter(Airline.slug.in_(member_slugs)).all()
                if member_slugs
                else []
            )
            airline_ids = [a.id for a in airlines]
            review_count = 0
            avg_rating = 0.0
            if airline_ids:
                stats = (
                    self.session.query(func.count(Review.id), func.avg(Review.rating))
                    .filter(Review.airline_id.in_(airline_ids))
                    .first()
                )
                review_count = stats[0] or 0
                avg_rating = round(float(stats[1] or 0), 2)
            result.append(
                {
                    "id": code.lower().replace(" ", "-"),
                    "name": code,
                    "member_count": len(members),
                    "members": [
                        {"slug": m.slug, "name": m.airline_name, "star_rating": m.star_rating}
                        for m in members[:20]
                    ],
                    "total_reviews": review_count,
                    "avg_rating": avg_rating,
                    "anomaly_count": 0,
                    "operational_risk": 0,
                    "source": "alliance_code_fallback",
                }
            )
        return result

    def hub_intelligence(self) -> list[dict[str, Any]]:
        hubs = (
            self.session.query(AirportMetadata)
            .filter(
                AirportMetadata.hub_level.in_(
                    ("PRIMARY_HUB", "SECONDARY_HUB", "REGIONAL_HUB", "major", "regional")
                )
            )
            .all()
        )
        if not hubs:
            linked_ids = {
                row[0]
                for row in self.session.query(AirlineAirport.airport_metadata_id).distinct().all()
                if row[0]
            }
            if linked_ids:
                hubs = self.session.query(AirportMetadata).filter(AirportMetadata.id.in_(linked_ids)).all()
            elif self.session.query(func.count(AirportMetadata.id)).scalar():
                hubs = (
                    self.session.query(AirportMetadata)
                    .order_by(AirportMetadata.airport_rating.desc().nullslast())
                    .limit(50)
                    .all()
                )

        result = []
        for hub in hubs:
            connections = self.session.query(AirlineAirport).filter_by(airport_metadata_id=hub.id).count()

            result.append(
                {
                    "id": hub.id,
                    "name": hub.airport_name,
                    "iata": hub.iata,
                    "country": hub.country,
                    "region": hub.region,
                    "hub_level": hub.hub_level or ("major" if connections >= 2 else "regional"),
                    "hub_score": hub.hub_score,
                    "alliance_hub": hub.alliance_hub,
                    "strategic_hub": hub.strategic_hub,
                    "airport_rating": hub.airport_rating,
                    "airline_connections": connections,
                    "operational_labels": hub.operational_labels,
                }
            )
        return sorted(result, key=lambda h: h["airline_connections"], reverse=True)

    def regional_intelligence(self) -> list[dict[str, Any]]:
        regions: dict[str, list[AirlineMetadata]] = defaultdict(list)
        for am in self.session.query(AirlineMetadata).filter(AirlineMetadata.country.isnot(None)).all():
            regions[am.country].append(am)

        result = []
        for country, airlines in sorted(regions.items(), key=lambda x: -len(x[1])):
            avg_stars = [a.star_rating for a in airlines if a.star_rating]
            result.append(
                {
                    "country": country,
                    "airline_count": len(airlines),
                    "avg_star_rating": round(sum(avg_stars) / len(avg_stars), 1) if avg_stars else None,
                    "airlines": [
                        {"slug": a.slug, "name": a.airline_name, "star_rating": a.star_rating}
                        for a in airlines[:5]
                    ],
                    "premium_count": sum(1 for a in airlines if a.is_premium),
                    "low_cost_count": sum(1 for a in airlines if a.is_low_cost),
                }
            )
        return result

    def premium_intelligence(self) -> list[dict[str, Any]]:
        premium = (
            self.session.query(AirlineMetadata)
            .filter(AirlineMetadata.is_premium.is_(True))
            .order_by(AirlineMetadata.star_rating.desc().nullslast())
            .all()
        )

        result = []
        for am in premium:
            airline = self.session.query(Airline).filter_by(slug=am.slug).first()
            review_count = 0
            avg_rating = 0.0
            if airline:
                stats = (
                    self.session.query(func.count(Review.id), func.avg(Review.rating))
                    .filter_by(airline_id=airline.id)
                    .first()
                )
                review_count = stats[0] or 0
                avg_rating = round(float(stats[1] or 0), 2)

            result.append(
                {
                    "slug": am.slug,
                    "name": am.airline_name,
                    "star_rating": am.star_rating,
                    "alliance": am.alliance_rel.name if am.alliance_rel else None,
                    "country": am.country,
                    "review_count": review_count,
                    "avg_rating": avg_rating,
                    "certifications": am.certifications,
                }
            )
        return result

    def airline_detail(self, slug: str) -> dict[str, Any] | None:
        am = self.session.query(AirlineMetadata).filter_by(slug=slug).first()
        if not am:
            return None

        airline = self.session.query(Airline).filter_by(slug=slug).first()
        review_count = 0
        avg_rating = 0.0
        if airline:
            stats = (
                self.session.query(func.count(Review.id), func.avg(Review.rating))
                .filter_by(airline_id=airline.id)
                .first()
            )
            review_count = stats[0] or 0
            avg_rating = round(float(stats[1] or 0), 2)

        return {
            "id": am.id,
            "slug": am.slug,
            "name": am.airline_name,
            "country": am.country,
            "airline_type": am.airline_type,
            "star_rating": am.star_rating,
            "is_premium": am.is_premium,
            "is_low_cost": am.is_low_cost,
            "alliance": am.alliance_rel.name if am.alliance_rel else None,
            "hub_airports": am.hub_airports,
            "certifications": am.certifications,
            "operational_labels": am.operational_labels,
            "review_count": review_count,
            "avg_rating": avg_rating,
            "enrichment_confidence": am.enrichment_confidence,
            "last_enriched_at": am.last_enriched_at.isoformat() if am.last_enriched_at else None,
        }

    def airport_detail(self, iata: str) -> dict[str, Any] | None:
        ap = self.session.query(AirportMetadata).filter_by(iata=iata.upper()).first()
        if not ap:
            return None

        connections = self.session.query(AirlineAirport).filter_by(airport_metadata_id=ap.id).count()

        return {
            "id": ap.id,
            "name": ap.airport_name,
            "iata": ap.iata,
            "icao": ap.icao,
            "city": ap.city,
            "country": ap.country,
            "region": ap.region,
            "latitude": ap.latitude,
            "longitude": ap.longitude,
            "airport_rating": ap.airport_rating,
            "hub_level": ap.hub_level,
            "passenger_volume": ap.passenger_volume,
            "airline_connections": connections,
            "operational_labels": ap.operational_labels,
            "enrichment_confidence": ap.enrichment_confidence,
        }

    def metadata_summary(self) -> dict[str, Any]:
        return {
            "airlines_total": self.session.query(func.count(AirlineMetadata.id)).scalar() or 0,
            "airports_total": self.session.query(func.count(AirportMetadata.id)).scalar() or 0,
            "alliances_total": self.session.query(func.count(Alliance.id)).scalar() or 0,
            "hubs_total": self.session.query(func.count(AirportMetadata.id))
            .filter(
                AirportMetadata.hub_level.in_(
                    ("PRIMARY_HUB", "SECONDARY_HUB", "REGIONAL_HUB", "major", "regional")
                )
            )
            .scalar()
            or 0,
            "classified_hubs": self.session.query(func.count(AirportMetadata.id))
            .filter(AirportMetadata.hub_level.in_(("PRIMARY_HUB", "SECONDARY_HUB", "REGIONAL_HUB")))
            .scalar()
            or 0,
            "total_airports": self.session.query(func.count(AirportMetadata.id)).scalar() or 0,
            "coverage_percent": round(
                (
                    self.session.query(func.count(AirportMetadata.id))
                    .filter(AirportMetadata.hub_level.in_(("PRIMARY_HUB", "SECONDARY_HUB", "REGIONAL_HUB")))
                    .scalar()
                    or 0
                )
                / max(self.session.query(func.count(AirportMetadata.id)).scalar() or 1, 1)
                * 100,
                2,
            ),
            "premium_airlines": self.session.query(func.count(AirlineMetadata.id))
            .filter(AirlineMetadata.is_premium.is_(True))
            .scalar()
            or 0,
            "low_cost_airlines": self.session.query(func.count(AirlineMetadata.id))
            .filter(AirlineMetadata.is_low_cost.is_(True))
            .scalar()
            or 0,
        }
