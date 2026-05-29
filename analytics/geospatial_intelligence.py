from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from analytics.geospatial_seed import merge_operational_seed


@dataclass(slots=True)
class GeospatialPayload:
    airports: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    events: list[dict[str, Any]]
    zones: dict[str, Any]
    summary: dict[str, Any]


class GeospatialIntelligenceService:
    """Operational geospatial feed for Deck.gl layers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def overview(self) -> dict[str, Any]:
        airports = self._airports()
        routes = self._routes()
        events = self._events()
        airports, routes, events, seeded = merge_operational_seed(airports, routes, events)
        zones = self._zones(airports)
        return GeospatialPayload(
            airports=airports,
            routes=routes,
            events=events,
            zones=zones,
            summary={
                "airport_count": len(airports),
                "route_count": len(routes),
                "event_count": len(events),
                "hub_count": sum(1 for a in airports if float(a.get("hub_score", 0) or 0) >= 0.65),
                "seeded": seeded,
            },
        ).__dict__

    @staticmethod
    def _ring(lng: float, lat: float, radius_deg: float, points: int = 36) -> list[list[float]]:
        coords: list[list[float]] = []
        lat_scale = max(0.35, math.cos(math.radians(lat)))
        for i in range(points + 1):
            angle = (2 * math.pi * i) / points
            coords.append(
                [
                    lng + (radius_deg * math.cos(angle)) / lat_scale,
                    lat + radius_deg * math.sin(angle) * 0.82,
                ]
            )
        return coords

    def _zones(self, airports: list[dict[str, Any]]) -> dict[str, Any]:
        features: list[dict[str, Any]] = []
        for airport in airports:
            hub_score = float(airport.get("hub_score", 0) or 0)
            if hub_score < 0.65:
                continue
            lng = float(airport["longitude"])
            lat = float(airport["latitude"])
            radius = 0.8 + hub_score * 2.2
            ring = self._ring(lng, lat, radius)
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "name": airport.get("iata") or airport.get("icao") or airport.get("name"),
                        "tier": "strategic_hub",
                        "hub_score": hub_score,
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )
            if len(features) >= 48:
                break
        return {"type": "FeatureCollection", "features": features}

    def _airports(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                  a.id,
                  a.iata_code AS iata,
                  am.icao_code AS icao,
                  COALESCE(am.airport_name, a.name) AS name,
                  COALESCE(am.city, a.city) AS city,
                  COALESCE(am.country, a.country) AS country,
                  COALESCE(am.latitude, a.latitude) AS latitude,
                  COALESCE(am.longitude, a.longitude) AS longitude,
                  CASE WHEN a.is_hub THEN 0.9 ELSE 0.45 END AS hub_score,
                  COALESCE(am.metadata_quality_score, 0.5) AS reputation_score,
                  1.0 - COALESCE(am.metadata_quality_score, 0.5) AS risk_score,
                  COALESCE(am.passenger_volume, '0') AS movimentacao,
                  COALESCE(al.name, 'Independent') AS alliance
                FROM airports a
                LEFT JOIN airport_metadata am ON am.airport_id = a.id
                LEFT JOIN regions r ON r.id = a.region_id
                LEFT JOIN alliances al ON lower(al.name) = lower(r.name)
                WHERE COALESCE(am.latitude, a.latitude) IS NOT NULL
                  AND COALESCE(am.longitude, a.longitude) IS NOT NULL
                ORDER BY a.is_hub DESC, reputation_score DESC
                LIMIT 1800
                """
            )
        ).mappings()
        return [dict(r) for r in rows]

    def _routes(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                  r.id,
                  ao.iata_code AS source_icao,
                  ad.iata_code AS destination_icao,
                  COALESCE(NULLIF(r.review_count, 0), 1) AS frequency,
                  COALESCE(r.complaint_density, 0) AS risk_score,
                  GREATEST(0, LEAST(1, (COALESCE(r.avg_sentiment_score, 5) / 10.0))) AS reputation_score,
                  ao.latitude AS source_lat,
                  ao.longitude AS source_lng,
                  ad.latitude AS destination_lat,
                  ad.longitude AS destination_lng
                FROM routes r
                JOIN airports ao ON ao.id = r.origin_airport_id
                JOIN airports ad ON ad.id = r.dest_airport_id
                WHERE ao.latitude IS NOT NULL
                  AND ao.longitude IS NOT NULL
                  AND ad.latitude IS NOT NULL
                  AND ad.longitude IS NOT NULL
                ORDER BY r.review_count DESC, r.complaint_density DESC
                LIMIT 2200
                """
            )
        ).mappings()
        return [dict(r) for r in rows]

    def _events(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                  CONCAT('route-', r.id) AS id,
                  al.name AS companhia,
                  'operational_risk' AS tipo_evento,
                  CASE
                    WHEN r.complaint_density >= 0.75 THEN 'critical'
                    WHEN r.complaint_density >= 0.45 THEN 'high'
                    WHEN r.complaint_density >= 0.25 THEN 'medium'
                    ELSE 'low'
                  END AS prioridade,
                  ((ao.latitude + ad.latitude) / 2.0) AS latitude,
                  ((ao.longitude + ad.longitude) / 2.0) AS longitude,
                  COALESCE(r.complaint_density, 0) AS score,
                  CONCAT(r.route_label, ' operational friction') AS descricao,
                  now() AS created_at
                FROM routes r
                JOIN airlines al ON al.id = r.airline_id
                JOIN airports ao ON ao.id = r.origin_airport_id
                JOIN airports ad ON ad.id = r.dest_airport_id
                WHERE ao.latitude IS NOT NULL
                  AND ao.longitude IS NOT NULL
                  AND ad.latitude IS NOT NULL
                  AND ad.longitude IS NOT NULL
                ORDER BY r.complaint_density DESC, r.review_count DESC
                LIMIT 600
                """
            )
        ).mappings()
        return [dict(r) for r in rows]
