"""Operational reference geodata when DB feeds are sparse (aviation intelligence grounding)."""

from __future__ import annotations

from typing import Any

# Strategic hubs — real coordinates (IATA reference network)
REFERENCE_AIRPORTS: list[dict[str, Any]] = [
    {
        "id": "seed-fra",
        "iata": "FRA",
        "icao": "EDDF",
        "name": "Frankfurt",
        "city": "Frankfurt",
        "country": "DE",
        "latitude": 50.0379,
        "longitude": 8.5622,
        "hub_score": 0.92,
        "reputation_score": 0.78,
        "risk_score": 0.22,
        "alliance": "Star Alliance",
    },
    {
        "id": "seed-jfk",
        "iata": "JFK",
        "icao": "KJFK",
        "name": "JFK",
        "city": "New York",
        "country": "US",
        "latitude": 40.6413,
        "longitude": -73.7781,
        "hub_score": 0.9,
        "reputation_score": 0.72,
        "risk_score": 0.28,
        "alliance": "oneworld",
    },
    {
        "id": "seed-dxb",
        "iata": "DXB",
        "icao": "OMDB",
        "name": "Dubai",
        "city": "Dubai",
        "country": "AE",
        "latitude": 25.2532,
        "longitude": 55.3657,
        "hub_score": 0.94,
        "reputation_score": 0.8,
        "risk_score": 0.2,
        "alliance": "Independent",
    },
    {
        "id": "seed-lhr",
        "iata": "LHR",
        "icao": "EGLL",
        "name": "Heathrow",
        "city": "London",
        "country": "GB",
        "latitude": 51.4700,
        "longitude": -0.4543,
        "hub_score": 0.93,
        "reputation_score": 0.76,
        "risk_score": 0.24,
        "alliance": "oneworld",
    },
    {
        "id": "seed-gru",
        "iata": "GRU",
        "icao": "SBGR",
        "name": "Guarulhos",
        "city": "São Paulo",
        "country": "BR",
        "latitude": -23.4356,
        "longitude": -46.4731,
        "hub_score": 0.88,
        "reputation_score": 0.68,
        "risk_score": 0.32,
        "alliance": "Star Alliance",
    },
    {
        "id": "seed-mia",
        "iata": "MIA",
        "icao": "KMIA",
        "name": "Miami",
        "city": "Miami",
        "country": "US",
        "latitude": 25.7959,
        "longitude": -80.2870,
        "hub_score": 0.86,
        "reputation_score": 0.7,
        "risk_score": 0.3,
        "alliance": "oneworld",
    },
    {
        "id": "seed-sin",
        "iata": "SIN",
        "icao": "WSSS",
        "name": "Changi",
        "city": "Singapore",
        "country": "SG",
        "latitude": 1.3644,
        "longitude": 103.9915,
        "hub_score": 0.95,
        "reputation_score": 0.88,
        "risk_score": 0.12,
        "alliance": "Star Alliance",
    },
    {
        "id": "seed-hkg",
        "iata": "HKG",
        "icao": "VHHH",
        "name": "Hong Kong",
        "city": "Hong Kong",
        "country": "HK",
        "latitude": 22.3080,
        "longitude": 113.9185,
        "hub_score": 0.91,
        "reputation_score": 0.74,
        "risk_score": 0.26,
        "alliance": "oneworld",
    },
    {
        "id": "seed-cdg",
        "iata": "CDG",
        "icao": "LFPG",
        "name": "Charles de Gaulle",
        "city": "Paris",
        "country": "FR",
        "latitude": 49.0097,
        "longitude": 2.5479,
        "hub_score": 0.89,
        "reputation_score": 0.71,
        "risk_score": 0.29,
        "alliance": "SkyTeam",
    },
    {
        "id": "seed-ams",
        "iata": "AMS",
        "icao": "EHAM",
        "name": "Schiphol",
        "city": "Amsterdam",
        "country": "NL",
        "latitude": 52.3105,
        "longitude": 4.7683,
        "hub_score": 0.9,
        "reputation_score": 0.77,
        "risk_score": 0.23,
        "alliance": "SkyTeam",
    },
    {
        "id": "seed-ist",
        "iata": "IST",
        "icao": "LTFM",
        "name": "Istanbul",
        "city": "Istanbul",
        "country": "TR",
        "latitude": 41.2753,
        "longitude": 28.7519,
        "hub_score": 0.87,
        "reputation_score": 0.69,
        "risk_score": 0.31,
        "alliance": "Star Alliance",
    },
    {
        "id": "seed-lax",
        "iata": "LAX",
        "icao": "KLAX",
        "name": "Los Angeles",
        "city": "Los Angeles",
        "country": "US",
        "latitude": 33.9416,
        "longitude": -118.4085,
        "hub_score": 0.85,
        "reputation_score": 0.67,
        "risk_score": 0.33,
        "alliance": "oneworld",
    },
]

REFERENCE_ROUTES: list[dict[str, Any]] = [
    {
        "id": "seed-r1",
        "source_icao": "FRA",
        "destination_icao": "JFK",
        "source_lat": 50.0379,
        "source_lng": 8.5622,
        "destination_lat": 40.6413,
        "destination_lng": -73.7781,
        "frequency": 420,
        "risk_score": 0.18,
        "reputation_score": 0.82,
    },
    {
        "id": "seed-r2",
        "source_icao": "DXB",
        "destination_icao": "LHR",
        "source_lat": 25.2532,
        "source_lng": 55.3657,
        "destination_lat": 51.47,
        "destination_lng": -0.4543,
        "frequency": 510,
        "risk_score": 0.22,
        "reputation_score": 0.8,
    },
    {
        "id": "seed-r3",
        "source_icao": "GRU",
        "destination_icao": "MIA",
        "source_lat": -23.4356,
        "source_lng": -46.4731,
        "destination_lat": 25.7959,
        "destination_lng": -80.287,
        "frequency": 280,
        "risk_score": 0.35,
        "reputation_score": 0.68,
    },
    {
        "id": "seed-r4",
        "source_icao": "SIN",
        "destination_icao": "LHR",
        "source_lat": 1.3644,
        "source_lng": 103.9915,
        "destination_lat": 51.47,
        "destination_lng": -0.4543,
        "frequency": 390,
        "risk_score": 0.15,
        "reputation_score": 0.86,
    },
    {
        "id": "seed-r5",
        "source_icao": "HKG",
        "destination_icao": "FRA",
        "source_lat": 22.308,
        "source_lng": 113.9185,
        "destination_lat": 50.0379,
        "destination_lng": 8.5622,
        "frequency": 310,
        "risk_score": 0.28,
        "reputation_score": 0.74,
    },
    {
        "id": "seed-r6",
        "source_icao": "CDG",
        "destination_icao": "JFK",
        "source_lat": 49.0097,
        "source_lng": 2.5479,
        "destination_lat": 40.6413,
        "destination_lng": -73.7781,
        "frequency": 360,
        "risk_score": 0.24,
        "reputation_score": 0.76,
    },
    {
        "id": "seed-r7",
        "source_icao": "AMS",
        "destination_icao": "DXB",
        "source_lat": 52.3105,
        "source_lng": 4.7683,
        "destination_lat": 25.2532,
        "destination_lng": 55.3657,
        "frequency": 295,
        "risk_score": 0.2,
        "reputation_score": 0.79,
    },
    {
        "id": "seed-r8",
        "source_icao": "IST",
        "destination_icao": "GRU",
        "source_lat": 41.2753,
        "source_lng": 28.7519,
        "destination_lat": -23.4356,
        "destination_lng": -46.4731,
        "frequency": 190,
        "risk_score": 0.38,
        "reputation_score": 0.65,
    },
    {
        "id": "seed-r9",
        "source_icao": "LAX",
        "destination_icao": "HKG",
        "source_lat": 33.9416,
        "source_lng": -118.4085,
        "destination_lat": 22.308,
        "destination_lng": 113.9185,
        "frequency": 240,
        "risk_score": 0.26,
        "reputation_score": 0.72,
    },
    {
        "id": "seed-r10",
        "source_icao": "MIA",
        "destination_icao": "LHR",
        "source_lat": 25.7959,
        "source_lng": -80.287,
        "destination_lat": 51.47,
        "destination_lng": -0.4543,
        "frequency": 265,
        "risk_score": 0.3,
        "reputation_score": 0.7,
    },
]


def reference_events() -> list[dict[str, Any]]:
    events = []
    for route in REFERENCE_ROUTES:
        risk = float(route.get("risk_score", 0))
        prioridade = (
            "critical" if risk >= 0.55 else "high" if risk >= 0.35 else "medium" if risk >= 0.2 else "low"
        )
        events.append(
            {
                "id": f"evt-{route['id']}",
                "companhia": f"{route['source_icao']} Network",
                "tipo_evento": "route_density",
                "prioridade": prioridade,
                "latitude": (float(route["source_lat"]) + float(route["destination_lat"])) / 2,
                "longitude": (float(route["source_lng"]) + float(route["destination_lng"])) / 2,
                "score": risk,
                "descricao": f"{route['source_icao']} → {route['destination_icao']} operational signal",
            }
        )
    return events


def merge_operational_seed(
    airports: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    min_airports: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Supplement sparse DB payloads with reference aviation network."""
    used_seed = False
    out_airports = list(airports)
    out_routes = list(routes)
    out_events = list(events)

    if len(out_airports) < min_airports:
        seen = {a.get("iata") for a in out_airports}
        for ref in REFERENCE_AIRPORTS:
            if ref["iata"] not in seen:
                out_airports.append(ref)
                seen.add(ref["iata"])
        used_seed = True

    if len(out_routes) < 6:
        seen_r = {(r.get("source_icao"), r.get("destination_icao")) for r in out_routes}
        for ref in REFERENCE_ROUTES:
            key = (ref["source_icao"], ref["destination_icao"])
            if key not in seen_r:
                out_routes.append(ref)
                seen_r.add(key)
        used_seed = True

    if len(out_events) < 4:
        seen_e = {e.get("id") for e in out_events}
        for ref in reference_events():
            if ref["id"] not in seen_e:
                out_events.append(ref)
        used_seed = True

    return out_airports, out_routes, out_events, used_seed
