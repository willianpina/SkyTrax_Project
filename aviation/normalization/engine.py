"""Normalization engine for airline and airport entities."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import NamedTuple

from sqlalchemy.orm import Session

from database.models.aviation import AirlineMetadata, AirportMetadata


class NormalizationResult(NamedTuple):
    canonical_name: str
    entity_id: str | None
    entity_type: str
    confidence: float
    method: str


AIRLINE_ALIASES: dict[str, str] = {
    "ba": "british-airways",
    "british airways": "british-airways",
    "ua": "united-airlines",
    "united": "united-airlines",
    "aa": "american-airlines",
    "american": "american-airlines",
    "dl": "delta-air-lines",
    "delta": "delta-air-lines",
    "lh": "lufthansa",
    "ek": "emirates",
    "sq": "singapore-airlines",
    "qf": "qantas-airways",
    "qantas": "qantas-airways",
    "nh": "ana-all-nippon-airways",
    "cx": "cathay-pacific",
    "qr": "qatar-airways",
    "tk": "turkish-airlines",
    "af": "air-france",
    "klm": "klm-royal-dutch-airlines",
}

AIRPORT_ALIASES: dict[str, str] = {
    "heathrow": "LHR",
    "gatwick": "LGW",
    "jfk": "JFK",
    "kennedy": "JFK",
    "lax": "LAX",
    "changi": "SIN",
    "schiphol": "AMS",
    "dubai": "DXB",
    "doha": "DOH",
    "istanbul": "IST",
    "narita": "NRT",
    "haneda": "HND",
    "cdg": "CDG",
    "de gaulle": "CDG",
    "frankfurt": "FRA",
    "hong kong": "HKG",
    "bangkok": "BKK",
    "sydney": "SYD",
}


class NormalizationEngine:
    """Resolve raw entity strings to canonical aviation entities."""

    def __init__(self, session: Session):
        self.session = session
        self._airline_cache: dict[str, AirlineMetadata] = {}
        self._airport_cache: dict[str, AirportMetadata] = {}

    def _warm_cache(self) -> None:
        if not self._airline_cache:
            for am in self.session.query(AirlineMetadata).all():
                self._airline_cache[am.slug] = am
                self._airline_cache[am.airline_name.lower()] = am
        if not self._airport_cache:
            for ap in self.session.query(AirportMetadata).all():
                if ap.iata:
                    self._airport_cache[ap.iata.upper()] = ap
                self._airport_cache[ap.airport_name.lower()] = ap

    def normalize_airline(self, raw: str) -> NormalizationResult:
        self._warm_cache()
        key = raw.strip().lower()

        if key in AIRLINE_ALIASES:
            slug = AIRLINE_ALIASES[key]
            if slug in self._airline_cache:
                am = self._airline_cache[slug]
                return NormalizationResult(am.airline_name, am.id, "airline", 1.0, "alias")

        if key in self._airline_cache:
            am = self._airline_cache[key]
            return NormalizationResult(am.airline_name, am.id, "airline", 1.0, "exact")

        best, best_score = None, 0.0
        for name, am in self._airline_cache.items():
            score = SequenceMatcher(None, key, name).ratio()
            if score > best_score:
                best, best_score = am, score

        if best and best_score >= 0.75:
            return NormalizationResult(best.airline_name, best.id, "airline", round(best_score, 3), "fuzzy")

        return NormalizationResult(raw, None, "airline", 0.0, "unresolved")

    def normalize_airport(self, raw: str) -> NormalizationResult:
        self._warm_cache()
        key = raw.strip()

        iata_match = re.match(r"^[A-Z]{3}$", key.upper())
        if iata_match:
            code = key.upper()
            if code in self._airport_cache:
                ap = self._airport_cache[code]
                return NormalizationResult(ap.airport_name, ap.id, "airport", 1.0, "iata")

        low = key.lower()
        if low in AIRPORT_ALIASES:
            code = AIRPORT_ALIASES[low]
            if code in self._airport_cache:
                ap = self._airport_cache[code]
                return NormalizationResult(ap.airport_name, ap.id, "airport", 1.0, "alias")

        if low in self._airport_cache:
            ap = self._airport_cache[low]
            return NormalizationResult(ap.airport_name, ap.id, "airport", 1.0, "exact")

        best, best_score = None, 0.0
        for name, ap in self._airport_cache.items():
            score = SequenceMatcher(None, low, name).ratio()
            if score > best_score:
                best, best_score = ap, score

        if best and best_score >= 0.70:
            return NormalizationResult(best.airport_name, best.id, "airport", round(best_score, 3), "fuzzy")

        return NormalizationResult(raw, None, "airport", 0.0, "unresolved")
