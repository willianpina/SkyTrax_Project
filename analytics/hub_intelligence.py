"""Hub & Airport Intelligence -- cross-references airport metadata with review
corpus to produce hub-level risk, concentration, and network analytics.

Provides:
  - Hub dashboard KPIs (monitored airports, active hubs, risk signals)
  - Hub/airport rankings with composite operational and risk scores
  - Hub risk matrix (complaint category breakdown per airport)
  - Alliance hub network aggregation
  - Airport incident timeline (complaint spike detection)
  - Hub concentration analysis per airline
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import Counter, defaultdict
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from database.models.core import Review
from database.models.aviation import (
    AirlineAirport,
    AirlineMetadata,
    AirportMetadata,
    Alliance,
)

logger = logging.getLogger(__name__)

_MENTION_CACHE_LOCK = Lock()
_MENTION_CACHE: dict[str, Any] = {"built_at": 0.0, "review_count": -1, "index": {}}
_MENTION_CACHE_TTL_S = int(os.getenv("HUB_MENTION_CACHE_TTL", "300"))
_MENTION_REVIEW_LIMIT = int(os.getenv("HUB_MENTION_REVIEW_LIMIT", "12000"))

COMPLAINT_CATEGORIES = {
    "baggage": {"baggage", "luggage", "lost bag", "suitcase", "missing bag", "damaged bag"},
    "delays": {"delay", "delayed", "late", "cancelled", "cancellation", "hours late"},
    "transfers": {"transfer", "connection", "connecting", "layover", "transit", "stopover"},
    "security": {"security", "screening", "tsa", "checkpoint", "prohibited"},
    "boarding": {"boarding", "gate", "priority", "queue", "check-in", "checkin"},
    "lounge": {"lounge", "access", "priority pass", "business lounge"},
    "crew": {"rude", "unfriendly", "unprofessional", "staff", "attendant", "crew"},
    "cleanliness": {"dirty", "clean", "hygiene", "toilet", "lavatory", "filthy"},
}

_COMMON_WORDS = frozenset(
    {
        "THE",
        "AND",
        "FOR",
        "BUT",
        "NOT",
        "WAS",
        "ARE",
        "HAS",
        "HAD",
        "ALL",
        "ONE",
        "TWO",
        "HER",
        "HIS",
        "ITS",
        "OUR",
        "OUT",
        "CAN",
        "DID",
        "HOW",
        "NEW",
        "OLD",
        "DAY",
        "WAY",
        "MAY",
        "SAY",
        "GET",
        "GOT",
        "LET",
        "SET",
        "TRY",
        "USE",
        "RUN",
        "FLY",
        "FAR",
        "FEW",
        "BIG",
        "BAD",
        "YES",
        "YET",
        "NOW",
        "ANY",
        "WHO",
        "WHY",
        "MAN",
        "OWN",
        "TOO",
        "END",
        "SEE",
        "AIR",
    }
)


class HubIntelligenceService:
    """Full hub-level intelligence derived from airport metadata and reviews."""

    def __init__(self, session: Session):
        self.session = session
        self._mention_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_airports(self) -> List[AirportMetadata]:
        return self.session.query(AirportMetadata).all()

    def _airport_mention_index(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build a mapping of airport IATA -> list of review dicts that mention it.

        Scans review text, title, and route fields.  Uses compiled regex with
        word boundaries for IATA codes to avoid false positives.  Result is
        cached on the instance and shared across requests (TTL) to avoid pool
        exhaustion when the UI fires parallel hub-intelligence calls.
        """
        if self._mention_cache is not None:
            return self._mention_cache

        review_count = self.session.query(func.count(Review.id)).scalar() or 0
        now = time.time()
        with _MENTION_CACHE_LOCK:
            cache_fresh = (
                _MENTION_CACHE.get("review_count") == review_count
                and (now - float(_MENTION_CACHE.get("built_at", 0))) < _MENTION_CACHE_TTL_S
                and _MENTION_CACHE.get("index") is not None
            )
            if cache_fresh:
                self._mention_cache = _MENTION_CACHE["index"]
                return self._mention_cache

        airports = self._load_airports()
        if not airports:
            self._mention_cache = {}
            return self._mention_cache

        iata_to_airport: Dict[str, AirportMetadata] = {}
        name_patterns: List[Tuple[re.Pattern, str]] = []

        for ap in airports:
            if ap.iata:
                code = ap.iata.upper()
                if code not in _COMMON_WORDS and len(code) == 3:
                    iata_to_airport[code] = ap
            if ap.airport_name:
                safe_name = re.escape(ap.airport_name)
                try:
                    pat = re.compile(safe_name, re.IGNORECASE)
                    name_patterns.append((pat, ap.iata or ap.airport_name))
                except re.error:
                    pass

        iata_regex = re.compile(r"\b([A-Z]{3})\b")

        reviews_q = self.session.query(
            Review.id, Review.title, Review.text, Review.rating, Review.route, Review.review_date
        ).order_by(Review.review_date.desc().nullslast())
        if _MENTION_REVIEW_LIMIT > 0:
            reviews_q = reviews_q.limit(_MENTION_REVIEW_LIMIT)
        reviews = reviews_q.all()

        index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for rev_id, title, text, rating, route, review_date in reviews:
            combined = "{} {} {}".format(title or "", text or "", route or "")
            combined_upper = combined.upper()

            matched_codes: set = set()

            for m in iata_regex.finditer(combined_upper):
                code = m.group(1)
                if code in iata_to_airport and code not in _COMMON_WORDS:
                    matched_codes.add(code)

            for pat, key in name_patterns:
                if pat.search(combined):
                    iata_key = key.upper() if key and len(key) == 3 else key
                    if iata_key and iata_key in iata_to_airport:
                        matched_codes.add(iata_key)

            review_dict = {
                "id": rev_id,
                "title": title,
                "text": text,
                "rating": rating,
                "route": route,
                "review_date": review_date,
            }

            for code in matched_codes:
                index[code].append(review_dict)

        built = dict(index)
        self._mention_cache = built
        with _MENTION_CACHE_LOCK:
            _MENTION_CACHE["built_at"] = now
            _MENTION_CACHE["review_count"] = review_count
            _MENTION_CACHE["index"] = built
        return self._mention_cache

    def _detect_complaints(self, text: str) -> List[str]:
        found = []
        lower = text.lower()
        for category, keywords in COMPLAINT_CATEGORIES.items():
            if any(kw in lower for kw in keywords):
                found.append(category)
        return found

    def _is_negative(self, review: Dict[str, Any]) -> bool:
        return (review.get("rating") or 10) < 5

    # ------------------------------------------------------------------
    # 1. Hub Dashboard
    # ------------------------------------------------------------------

    def hub_dashboard(self) -> dict:
        """Top-level KPIs for the hub intelligence module."""
        total_airports = self.session.query(func.count(AirportMetadata.id)).scalar() or 0

        if total_airports == 0:
            return {
                "airports_monitored": 0,
                "active_hubs": 0,
                "critical_hubs": 0,
                "high_risk_airports": 0,
                "alliance_coverage": 0.0,
                "operational_concentration": 0.0,
                "top_hubs": [],
            }

        active_hubs = (
            self.session.query(AirportMetadata).filter(AirportMetadata.hub_level.isnot(None)).all()
        )
        if not active_hubs:
            linked_ids = [
                row[0]
                for row in self.session.query(AirlineAirport.airport_metadata_id).distinct().all()
                if row[0]
            ]
            if linked_ids:
                active_hubs = (
                    self.session.query(AirportMetadata)
                    .filter(AirportMetadata.id.in_(linked_ids))
                    .limit(50)
                    .all()
                )
        if not active_hubs:
            active_hubs = (
                self.session.query(AirportMetadata)
                .order_by(AirportMetadata.airport_rating.desc().nullslast())
                .limit(50)
                .all()
            )

        review_count = self.session.query(func.count(Review.id)).scalar() or 0
        use_mention_scan = review_count <= 8000 and len(active_hubs) <= 80

        critical_hubs = 0
        high_risk = 0
        if use_mention_scan:
            mention_index = self._airport_mention_index()
            complaint_counts: List[Tuple[str, int]] = []
            for ap in active_hubs:
                code = (ap.iata or "").upper()
                mentions = mention_index.get(code, [])
                neg = sum(1 for r in mentions if self._is_negative(r))
                complaint_counts.append((code, neg))

            complaint_counts.sort(key=lambda x: x[1], reverse=True)
            top_10_pct = max(1, len(complaint_counts) // 10)
            critical_threshold = complaint_counts[top_10_pct - 1][1] if complaint_counts else 0
            critical_hubs = sum(1 for _, c in complaint_counts if c >= critical_threshold and c > 0)

            for ap in active_hubs:
                code = (ap.iata or "").upper()
                mentions = mention_index.get(code, [])
                if mentions:
                    avg_r = sum(float(r.get("rating") or 5) for r in mentions) / len(mentions)
                    if avg_r < 5.0:
                        high_risk += 1
        else:
            critical_hubs = sum(
                1 for ap in active_hubs if (ap.airport_rating or 10) < 4.0 or ap.hub_level == "critical"
            )
            high_risk = sum(1 for ap in active_hubs if (ap.airport_rating or 10) < 5.0)

        # Alliance coverage
        airports_with_alliance_airline = set()
        alliance_airlines = (
            self.session.query(AirlineMetadata.id).filter(AirlineMetadata.alliance_id.isnot(None)).subquery()
        )
        linked = (
            self.session.query(AirlineAirport.airport_metadata_id)
            .filter(AirlineAirport.airline_metadata_id.in_(self.session.query(alliance_airlines.c.id)))
            .distinct()
            .all()
        )
        airports_with_alliance_airline = {row[0] for row in linked}
        alliance_coverage = round(len(airports_with_alliance_airline) / max(total_airports, 1) * 100, 1)

        # Operational concentration (Herfindahl index of airline-airport links)
        link_counts = (
            self.session.query(
                AirlineAirport.airport_metadata_id,
                func.count(AirlineAirport.id).label("cnt"),
            )
            .group_by(AirlineAirport.airport_metadata_id)
            .all()
        )
        total_links = sum(cnt for _, cnt in link_counts)
        hhi = 0.0
        if total_links > 0:
            for _, cnt in link_counts:
                share = cnt / total_links
                hhi += share * share
        hhi = round(hhi, 4)

        # Top hubs by airline connection count
        top_hub_rows = (
            self.session.query(
                AirportMetadata.airport_name,
                AirportMetadata.iata,
                AirportMetadata.country,
                AirportMetadata.hub_level,
                func.count(AirlineAirport.id).label("airline_count"),
            )
            .join(AirlineAirport, AirlineAirport.airport_metadata_id == AirportMetadata.id)
            .group_by(AirportMetadata.id)
            .order_by(desc("airline_count"))
            .limit(10)
            .all()
        )
        top_hubs = [
            {
                "airport_name": name,
                "iata": iata,
                "country": country,
                "hub_level": hl,
                "airline_count": int(cnt),
            }
            for name, iata, country, hl, cnt in top_hub_rows
        ]

        return {
            "airports_monitored": total_airports,
            "active_hubs": len(active_hubs),
            "critical_hubs": critical_hubs,
            "high_risk_airports": high_risk,
            "alliance_coverage": alliance_coverage,
            "operational_concentration": hhi,
            "top_hubs": top_hubs,
        }

    # ------------------------------------------------------------------
    # 2. Hub Rankings
    # ------------------------------------------------------------------

    def hub_rankings(self) -> List[dict]:
        """Ranked list of airports/hubs with composite scores."""
        airports = self._load_airports()
        if not airports:
            return []

        mention_index = self._airport_mention_index()

        airline_count_map: Dict[str, int] = {}
        rows = (
            self.session.query(
                AirlineAirport.airport_metadata_id,
                func.count(AirlineAirport.id).label("cnt"),
            )
            .group_by(AirlineAirport.airport_metadata_id)
            .all()
        )
        for ap_id, cnt in rows:
            airline_count_map[ap_id] = int(cnt)

        # Primary alliance per airport
        alliance_map: Dict[str, str] = {}
        alliance_rows = (
            self.session.query(
                AirlineAirport.airport_metadata_id,
                Alliance.name,
            )
            .join(AirlineMetadata, AirlineMetadata.id == AirlineAirport.airline_metadata_id)
            .join(Alliance, Alliance.id == AirlineMetadata.alliance_id)
            .all()
        )
        alliance_counter: Dict[str, Counter] = defaultdict(Counter)
        for ap_id, alliance_name in alliance_rows:
            alliance_counter[ap_id][alliance_name] += 1
        for ap_id, counter in alliance_counter.items():
            alliance_map[ap_id] = counter.most_common(1)[0][0]

        result = []
        for ap in airports:
            code = (ap.iata or "").upper()
            mentions = mention_index.get(code, [])
            mention_count = len(mentions)
            airlines_served = airline_count_map.get(ap.id, 0)
            alliance = alliance_map.get(ap.id)

            neg_mentions = sum(1 for r in mentions if self._is_negative(r))
            complaint_density = round(neg_mentions / max(mention_count, 1), 3)

            avg_rating_reviews = 0.0
            if mentions:
                avg_rating_reviews = sum(float(r.get("rating") or 5) for r in mentions) / mention_count

            airport_rating_norm = ((ap.airport_rating or 3) / 5.0) * 100
            review_rating_norm = (avg_rating_reviews / 10.0) * 100 if mentions else 50.0
            connectivity_norm = min(airlines_served * 5, 100)
            complaint_penalty = complaint_density * 100

            operational_score = round(
                0.30 * airport_rating_norm
                + 0.30 * review_rating_norm
                + 0.20 * connectivity_norm
                - 0.20 * complaint_penalty,
                1,
            )
            operational_score = max(0.0, min(100.0, operational_score))

            risk_score = round(
                0.50 * complaint_density * 100
                + 0.30 * max(0, (50 - review_rating_norm))
                + 0.20 * max(0, (60 - airport_rating_norm)),
                1,
            )
            risk_score = max(0.0, min(100.0, risk_score))

            result.append(
                {
                    "airport_name": ap.airport_name,
                    "iata": ap.iata,
                    "country": ap.country,
                    "hub_level": ap.hub_level,
                    "airport_rating": ap.airport_rating,
                    "airlines_served": airlines_served,
                    "alliance": alliance,
                    "complaint_density": complaint_density,
                    "operational_score": operational_score,
                    "risk_score": risk_score,
                    "mention_count": mention_count,
                }
            )

        result.sort(key=lambda x: x["operational_score"], reverse=True)
        return result

    # ------------------------------------------------------------------
    # 3. Hub Risk Matrix
    # ------------------------------------------------------------------

    def hub_risk_matrix(self) -> List[dict]:
        """Complaint category breakdown for each hub airport."""
        airports = self._load_airports()
        hub_airports = [ap for ap in airports if ap.hub_level is not None]
        if not hub_airports:
            return []

        mention_index = self._airport_mention_index()
        result = []

        for ap in hub_airports:
            code = (ap.iata or "").upper()
            mentions = mention_index.get(code, [])
            if not mentions:
                result.append(
                    {
                        "airport_name": ap.airport_name,
                        "iata": ap.iata,
                        "risks": {cat: 0 for cat in COMPLAINT_CATEGORIES},
                    }
                )
                continue

            category_counts: Counter = Counter()
            for review in mentions:
                combined = "{} {}".format(review.get("title") or "", review.get("text") or "")
                for cat in self._detect_complaints(combined):
                    category_counts[cat] += 1

            risks = {cat: category_counts.get(cat, 0) for cat in COMPLAINT_CATEGORIES}
            result.append(
                {
                    "airport_name": ap.airport_name,
                    "iata": ap.iata,
                    "risks": risks,
                }
            )

        return result

    # ------------------------------------------------------------------
    # 4. Alliance Hub Network
    # ------------------------------------------------------------------

    def alliance_hub_network(self) -> List[dict]:
        """Group hubs by alliance with aggregated risk and ratings."""
        alliances = self.session.query(Alliance).all()
        if not alliances:
            return []

        mention_index = self._airport_mention_index()
        result = []

        for alliance in alliances:
            members = (
                self.session.query(AirlineMetadata).filter(AirlineMetadata.alliance_id == alliance.id).all()
            )
            if not members:
                continue

            member_ids = [m.id for m in members]
            hub_airport_ids = (
                self.session.query(AirlineAirport.airport_metadata_id)
                .filter(AirlineAirport.airline_metadata_id.in_(member_ids))
                .distinct()
                .all()
            )
            hub_ap_ids = {row[0] for row in hub_airport_ids}

            hub_airports = (
                (self.session.query(AirportMetadata).filter(AirportMetadata.id.in_(hub_ap_ids)).all())
                if hub_ap_ids
                else []
            )

            hubs_list = []
            total_risk_mentions = 0
            rating_sum = 0.0
            rating_count = 0

            for ap in hub_airports:
                code = (ap.iata or "").upper()
                mentions = mention_index.get(code, [])
                neg = sum(1 for r in mentions if self._is_negative(r))
                total_risk_mentions += neg

                if ap.airport_rating is not None:
                    rating_sum += ap.airport_rating
                    rating_count += 1

                hubs_list.append(
                    {
                        "airport_name": ap.airport_name,
                        "iata": ap.iata,
                        "country": ap.country,
                        "hub_level": ap.hub_level,
                        "airport_rating": ap.airport_rating,
                        "negative_mentions": neg,
                        "total_mentions": len(mentions),
                    }
                )

            avg_rating = round(rating_sum / rating_count, 2) if rating_count else 0.0

            result.append(
                {
                    "alliance_name": alliance.name,
                    "alliance_slug": alliance.slug,
                    "hubs": hubs_list,
                    "avg_rating": avg_rating,
                    "total_risk_mentions": total_risk_mentions,
                    "hub_count": len(hubs_list),
                }
            )

        return result

    # ------------------------------------------------------------------
    # 5. Airport Incidents
    # ------------------------------------------------------------------

    def airport_incidents(self) -> List[dict]:
        """Timeline of airport-related complaint spikes by month."""
        airports = self._load_airports()
        if not airports:
            return []

        mention_index = self._airport_mention_index()
        result = []

        for ap in airports:
            code = (ap.iata or "").upper()
            mentions = mention_index.get(code, [])
            if not mentions:
                continue

            monthly: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for review in mentions:
                rd = review.get("review_date")
                if rd is None:
                    continue
                month_key = rd.strftime("%Y-%m") if hasattr(rd, "strftime") else str(rd)[:7]
                monthly[month_key].append(review)

            if not monthly:
                continue

            complaint_counts_per_month = {}
            for month, revs in monthly.items():
                neg = [r for r in revs if self._is_negative(r)]
                complaint_counts_per_month[month] = len(neg)

            counts = list(complaint_counts_per_month.values())
            if not counts:
                continue
            avg_complaints = sum(counts) / len(counts)
            threshold = avg_complaints * 1.5

            for month, neg_count in complaint_counts_per_month.items():
                if neg_count <= threshold or neg_count == 0:
                    continue

                revs = monthly[month]
                ratings = [float(r.get("rating") or 5) for r in revs]
                avg_r = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

                all_complaints: Counter = Counter()
                for review in revs:
                    combined = "{} {}".format(review.get("title") or "", review.get("text") or "")
                    for cat in self._detect_complaints(combined):
                        all_complaints[cat] += 1

                top_complaints = [c for c, _ in all_complaints.most_common(3)]

                ratio = neg_count / max(avg_complaints, 1)
                if ratio >= 3.0:
                    severity = "critical"
                elif ratio >= 2.0:
                    severity = "high"
                else:
                    severity = "medium"

                result.append(
                    {
                        "airport_name": ap.airport_name,
                        "iata": ap.iata,
                        "month": month,
                        "complaint_count": neg_count,
                        "avg_rating": avg_r,
                        "top_complaints": top_complaints,
                        "severity": severity,
                    }
                )

        result.sort(key=lambda x: (x["severity"] == "critical", x["complaint_count"]), reverse=True)
        return result

    # ------------------------------------------------------------------
    # 6. Hub Concentration
    # ------------------------------------------------------------------

    def hub_concentration(self) -> List[dict]:
        """Per-airline hub dependency analysis."""
        airline_metas = self.session.query(AirlineMetadata).all()
        if not airline_metas:
            return []

        mention_index = self._airport_mention_index()
        result = []

        for am in airline_metas:
            links = (
                self.session.query(AirlineAirport).filter(AirlineAirport.airline_metadata_id == am.id).all()
            )
            if not links:
                continue

            airport_ids = [lnk.airport_metadata_id for lnk in links]
            hub_airports = (
                self.session.query(AirportMetadata).filter(AirportMetadata.id.in_(airport_ids)).all()
            )

            hub_count = len(hub_airports)
            if hub_count == 0:
                continue

            # Count review mentions per hub for this airline
            hub_mentions: Dict[str, int] = {}
            for ap in hub_airports:
                code = (ap.iata or "").upper()
                hub_mentions[code] = len(mention_index.get(code, []))

            total_mentions = sum(hub_mentions.values())
            if total_mentions == 0:
                primary_hub_code = hub_airports[0].iata
                concentration_ratio = 0.0
            else:
                primary_hub_code = max(hub_mentions, key=hub_mentions.get)  # type: ignore[arg-type]
                concentration_ratio = round(hub_mentions[primary_hub_code] / total_mentions, 3)

            primary_airport = next(
                (ap for ap in hub_airports if (ap.iata or "").upper() == primary_hub_code),
                hub_airports[0],
            )

            if concentration_ratio >= 0.7:
                exposure = "critical"
            elif concentration_ratio >= 0.5:
                exposure = "high"
            elif concentration_ratio >= 0.3:
                exposure = "medium"
            else:
                exposure = "low"

            result.append(
                {
                    "airline_name": am.airline_name,
                    "airline_slug": am.slug,
                    "hub_count": hub_count,
                    "primary_hub": primary_airport.iata,
                    "concentration_ratio": concentration_ratio,
                    "exposure_risk": exposure,
                }
            )

        result.sort(key=lambda x: x["concentration_ratio"], reverse=True)
        return result
