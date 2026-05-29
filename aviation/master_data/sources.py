"""Canonical aviation data sources — OpenFlights + OurAirports ingestion."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

OPENFLIGHTS_AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
OPENFLIGHTS_AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
OPENFLIGHTS_ROUTES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

OURAIRPORTS_AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"


@dataclass
class OpenFlightsAirline:
    openflights_id: str
    name: str
    alias: str | None
    iata: str | None
    icao: str | None
    callsign: str | None
    country: str | None
    active: bool = True


@dataclass
class OpenFlightsAirport:
    openflights_id: str
    name: str
    city: str | None
    country: str | None
    iata: str | None
    icao: str | None
    latitude: float | None
    longitude: float | None
    altitude: int | None
    timezone_offset: float | None
    dst: str | None
    tz_name: str | None


@dataclass
class OurAirportsRecord:
    ident: str
    type: str
    name: str
    latitude: float | None
    longitude: float | None
    elevation_ft: int | None
    continent: str | None
    iso_country: str | None
    iso_region: str | None
    municipality: str | None
    gps_code: str | None
    iata_code: str | None
    local_code: str | None


def _safe_float(val: str) -> float | None:
    try:
        return float(val) if val and val != "\\N" else None
    except (ValueError, TypeError):
        return None


def _safe_int(val: str) -> int | None:
    try:
        return int(float(val)) if val and val != "\\N" else None
    except (ValueError, TypeError):
        return None


def _clean(val: str) -> str | None:
    """Clean a field from OpenFlights DAT format."""
    val = val.strip().strip('"')
    return val if val and val != "\\N" and val != "-" else None


def fetch_openflights_airlines(timeout: float = 30.0) -> list[OpenFlightsAirline]:
    """Download and parse OpenFlights airlines.dat."""
    logger.info("[AVIATION_MASTER] Fetching OpenFlights airlines.dat...")
    resp = httpx.get(OPENFLIGHTS_AIRLINES_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()

    airlines: list[OpenFlightsAirline] = []
    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if len(row) < 8:
            continue
        airlines.append(
            OpenFlightsAirline(
                openflights_id=row[0],
                name=_clean(row[1]) or "",
                alias=_clean(row[2]),
                iata=_clean(row[3]),
                icao=_clean(row[4]),
                callsign=_clean(row[5]),
                country=_clean(row[6]),
                active=row[7].strip() == "Y",
            )
        )

    logger.info("[AVIATION_MASTER] Parsed %d airlines from OpenFlights", len(airlines))
    return airlines


def fetch_openflights_airports(timeout: float = 30.0) -> list[OpenFlightsAirport]:
    """Download and parse OpenFlights airports.dat."""
    logger.info("[AVIATION_MASTER] Fetching OpenFlights airports.dat...")
    resp = httpx.get(OPENFLIGHTS_AIRPORTS_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()

    airports: list[OpenFlightsAirport] = []
    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if len(row) < 12:
            continue
        airports.append(
            OpenFlightsAirport(
                openflights_id=row[0],
                name=_clean(row[1]) or "",
                city=_clean(row[2]),
                country=_clean(row[3]),
                iata=_clean(row[4]),
                icao=_clean(row[5]),
                latitude=_safe_float(row[6]),
                longitude=_safe_float(row[7]),
                altitude=_safe_int(row[8]),
                timezone_offset=_safe_float(row[9]),
                dst=_clean(row[10]),
                tz_name=_clean(row[11]) if len(row) > 11 else None,
            )
        )

    logger.info("[AVIATION_MASTER] Parsed %d airports from OpenFlights", len(airports))
    return airports


def fetch_ourairports(timeout: float = 60.0) -> list[OurAirportsRecord]:
    """Download and parse OurAirports airports.csv (large file)."""
    logger.info("[AVIATION_MASTER] Fetching OurAirports airports.csv...")
    resp = httpx.get(OURAIRPORTS_AIRPORTS_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()

    airports: list[OurAirportsRecord] = []
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        airport_type = row.get("type", "")
        if airport_type not in ("large_airport", "medium_airport"):
            continue
        airports.append(
            OurAirportsRecord(
                ident=row.get("ident", ""),
                type=airport_type,
                name=row.get("name", ""),
                latitude=_safe_float(row.get("latitude_deg", "")),
                longitude=_safe_float(row.get("longitude_deg", "")),
                elevation_ft=_safe_int(row.get("elevation_ft", "")),
                continent=row.get("continent"),
                iso_country=row.get("iso_country"),
                iso_region=row.get("iso_region"),
                municipality=row.get("municipality"),
                gps_code=row.get("gps_code"),
                iata_code=row.get("iata_code") or None,
                local_code=row.get("local_code"),
            )
        )

    logger.info("[AVIATION_MASTER] Parsed %d airports from OurAirports (medium+large)", len(airports))
    return airports
