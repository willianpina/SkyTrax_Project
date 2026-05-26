from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from analytics.constants import SEED_AIRPORTS, SEED_REGIONS
from database.models import Airline, Airport, NLPResult, Region, Review, Route
from database.postgis_support import postgis_requested, runtime_postgis_active, sync_airport_geography


class GeospatialIntelligenceService:
    """Route, hub and regional reputation intelligence."""

    IATA_PATTERN = re.compile(r"\b([A-Z]{3})\b")

    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_geography(self) -> dict:
        regions = {code: Region(code=code, name=name) for code, name in SEED_REGIONS}
        for region in regions.values():
            existing = self.session.query(Region).filter_by(code=region.code).first()
            if not existing:
                self.session.add(region)
        self.session.flush()
        region_map = {row.code: row.id for row in self.session.query(Region).all()}
        created = 0
        for iata, name, lat, lon, region_code in SEED_AIRPORTS:
            if self.session.query(Airport).filter_by(iata_code=iata).first():
                continue
            self.session.add(
                Airport(
                    iata_code=iata,
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    region_id=region_map.get(region_code),
                    is_hub=iata in {"LHR", "DXB", "DOH", "FRA", "SIN"},
                )
            )
            created += 1
        self.session.commit()
        postgis_synced = sync_airport_geography(self.session)
        return {
            "airports_created": created,
            "postgis_enabled": runtime_postgis_active(),
            "postgis_geometry_synced": postgis_synced,
            "mode": "geospatial" if runtime_postgis_active() else "lightweight",
        }

    def refresh_routes(self, airline_slug: str | None = None) -> dict:
        query = self.session.query(Review).options(selectinload(Review.airline), selectinload(Review.nlp_result)).join(Airline)
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        reviews = query.filter(Review.route.isnot(None)).limit(5000).all()
        airport_map = {row.iata_code: row for row in self.session.query(Airport).all()}
        aggregates: dict[tuple[str, str], dict] = defaultdict(lambda: {"count": 0, "complaints": 0, "sentiment": 0.0})

        for review in reviews:
            label = self._normalize_route(review.route)
            if not label:
                continue
            key = (review.airline_id, label)
            aggregates[key]["count"] += 1
            if review.recommended is False or (review.nlp_result and review.nlp_result.sentiment_label == "negative"):
                aggregates[key]["complaints"] += 1
            if review.nlp_result:
                aggregates[key]["sentiment"] += review.nlp_result.sentiment_score

        updated = 0
        for (airline_id, label), stats in aggregates.items():
            origin, dest = self._parse_route_codes(label)
            route = self.session.query(Route).filter_by(airline_id=airline_id, route_label=label).first()
            if route is None:
                route = Route(airline_id=airline_id, route_label=label)
                self.session.add(route)
            route.origin_airport_id = airport_map[origin].id if origin in airport_map else None
            route.dest_airport_id = airport_map[dest].id if dest in airport_map else None
            route.review_count = stats["count"]
            route.complaint_density = round(stats["complaints"] / max(stats["count"], 1), 4)
            route.avg_sentiment_score = round(stats["sentiment"] / max(stats["count"], 1), 4)
            updated += 1
        self.session.commit()
        return {"routes_updated": updated}

    def routes(self, airline_slug: str | None = None, limit: int = 50) -> list[dict]:
        query = self.session.query(Route, Airline).join(Airline)
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        rows = query.order_by(Route.complaint_density.desc()).limit(limit).all()
        return [
            {
                "route_label": route.route_label,
                "airline": airline.name,
                "airline_slug": airline.slug,
                "review_count": route.review_count,
                "complaint_density": route.complaint_density,
                "avg_sentiment_score": route.avg_sentiment_score,
            }
            for route, airline in rows
        ]

    def hubs(self, limit: int = 20) -> list[dict]:
        airports = self.session.query(Airport).filter(Airport.is_hub.is_(True)).all()
        results = []
        for airport in airports:
            negative = (
                self.session.query(func.count(Review.id))
                .join(NLPResult)
                .filter(Review.route.ilike(f"%{airport.iata_code}%"), NLPResult.sentiment_label == "negative")
                .scalar()
                or 0
            )
            total = (
                self.session.query(func.count(Review.id)).filter(Review.route.ilike(f"%{airport.iata_code}%")).scalar() or 0
            )
            results.append(
                {
                    "iata": airport.iata_code,
                    "name": airport.name,
                    "latitude": airport.latitude,
                    "longitude": airport.longitude,
                    "complaint_density": round(negative / max(total, 1), 4),
                    "review_count": int(total),
                    "risk_level": "high" if total and negative / total > 0.4 else "medium" if total else "low",
                }
            )
        return sorted(results, key=lambda row: row["complaint_density"], reverse=True)[:limit]

    def heatmap(self) -> list[dict]:
        airports = self.session.query(Airport).filter(Airport.latitude.isnot(None)).all()
        points = []
        for airport in airports:
            total = self.session.query(func.count(Review.id)).filter(Review.route.ilike(f"%{airport.iata_code}%")).scalar() or 0
            negative = (
                self.session.query(func.count(Review.id))
                .join(NLPResult)
                .filter(Review.route.ilike(f"%{airport.iata_code}%"), NLPResult.sentiment_label == "negative")
                .scalar()
                or 0
            )
            points.append(
                {
                    "iata": airport.iata_code,
                    "name": airport.name,
                    "lat": airport.latitude,
                    "lon": airport.longitude,
                    "weight": round(negative / max(total, 1) * 100, 2) if total else 0,
                    "review_count": int(total),
                }
            )
        return points

    def regional_sentiment(self) -> list[dict]:
        rows = (
            self.session.query(Region.name, NLPResult.sentiment_label, func.count(NLPResult.id))
            .join(Airport, Airport.region_id == Region.id)
            .join(Review, Review.route.ilike(func.concat("%", Airport.iata_code, "%")))
            .join(NLPResult)
            .group_by(Region.name, NLPResult.sentiment_label)
            .all()
        )
        by_region: dict[str, dict[str, int]] = defaultdict(dict)
        for region, label, count in rows:
            by_region[region][label] = int(count)
        return [
            {
                "region": region,
                "distribution": dist,
                "negative_share": round(dist.get("negative", 0) / max(sum(dist.values()), 1), 4),
            }
            for region, dist in by_region.items()
        ]

    def geospatial_status(self) -> dict:
        """Report current geospatial capability for APIs and ops."""
        return {
            "postgis_requested": postgis_requested(),
            "postgis_active": runtime_postgis_active(),
            "mode": "geospatial" if runtime_postgis_active() else "lightweight",
            "coordinates_fields": ["latitude", "longitude"],
            "future_map_stack": ["PostGIS", "Deck.gl", "Mapbox"],
        }

    @staticmethod
    def _normalize_route(route: str | None) -> str:
        if not route:
            return ""
        cleaned = route.strip().upper()
        codes = GeospatialIntelligenceService.IATA_PATTERN.findall(cleaned)
        if len(codes) >= 2:
            return f"{codes[0]}-{codes[1]}"
        return cleaned[:64]

    @staticmethod
    def _parse_route_codes(label: str) -> tuple[str | None, str | None]:
        parts = label.split("-")
        if len(parts) >= 2 and len(parts[0]) == 3 and len(parts[1]) == 3:
            return parts[0], parts[1]
        return None, None
