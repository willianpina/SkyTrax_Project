"""Metadata Extraction Engine — mines structured aviation intelligence from review text.

Extracts disruptions, quality dimensions, aircraft mentions, route references,
airport codes, and operational severity from free-text reviews.
"""

from __future__ import annotations

import re
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from database.models.core import Review
from database.models.graph import ReviewIntelligence

logger = logging.getLogger(__name__)

DISRUPTION_PATTERNS: dict[str, re.Pattern] = {
    "delay": re.compile(
        r"delay(?:ed|s)?|hours?\s+late|late\s+(?:arrival|departure)|"
        r"waited\s+\d+\s+hours?|behind\s+schedule",
        re.IGNORECASE,
    ),
    "cancellation": re.compile(
        r"cancel(?:led|lation|ed)|flight\s+cancelled|no[\s-]+show",
        re.IGNORECASE,
    ),
    "baggage_loss": re.compile(
        r"lost\s+(?:\w+\s+)?(?:luggage|baggage|bag|suitcase)|"
        r"missing\s+(?:\w+\s+)?(?:luggage|bag)|"
        r"damaged\s+(?:\w+\s+)?(?:luggage|baggage|suitcase)",
        re.IGNORECASE,
    ),
    "diversion": re.compile(
        r"divert(?:ed)?|emergency\s+landing|unscheduled\s+stop",
        re.IGNORECASE,
    ),
    "overbooking": re.compile(
        r"overbook(?:ed|ing)|denied\s+boarding|bumped\s+off",
        re.IGNORECASE,
    ),
    "missed_connection": re.compile(
        r"missed?\s+(?:\w+\s+)?(?:connection|connecting|transfer)|"
        r"couldn'?t\s+(?:make|catch)\s+(?:my|the)\s+(?:connection|flight)",
        re.IGNORECASE,
    ),
}

QUALITY_PATTERNS: dict[str, re.Pattern] = {
    "crew": re.compile(r"crew|staff|attendant|steward(?:ess)?|purser|cabin\s+crew", re.I),
    "food": re.compile(r"food|meal|catering|snack|beverage|drink|wine|breakfast|dinner|lunch", re.I),
    "seat": re.compile(r"\bseat\b|legroom|leg\s+room|pitch|recline|comfort(?:able)?", re.I),
    "entertainment": re.compile(r"entertainment|ife\b|screen|movie|wifi|wi-fi|usb|charging", re.I),
    "lounge": re.compile(r"lounge|priority\s+pass|fast\s+track|business\s+class\s+lounge", re.I),
    "boarding": re.compile(r"boarding|gate|check[\s-]in|checkin|priority\s+boarding", re.I),
    "punctuality": re.compile(r"on[\s-]time|punctual|delay|late|early\s+arrival", re.I),
    "cleanliness": re.compile(r"clean|dirty|hygien|sanit|filthy|spotless|tidy|stain", re.I),
    "baggage": re.compile(r"baggage|luggage|suitcase|carry[\s-]on|overhead\s+bin", re.I),
    "transfer": re.compile(r"transfer|transit|connect(?:ion|ing)|layover|stopover", re.I),
}

POSITIVE_WORDS = re.compile(
    r"excellent|amazing|great|wonderful|outstanding|superb|fantastic|"
    r"impressive|perfect|best|loved|pleasant|comfortable|friendly|"
    r"efficient|helpful|delicious|spacious|smooth",
    re.I,
)
NEGATIVE_WORDS = re.compile(
    r"terrible|awful|horrible|worst|disgusting|rude|broken|dirty|"
    r"unacceptable|poor|bad|cold|stale|cramped|uncomfortable|"
    r"unfriendly|slow|appalling|dreadful|abysmal",
    re.I,
)

AIRCRAFT_PATTERNS = [
    (re.compile(r"(?:boeing|b)[\s-]*(\d{3})(?:-(\d{1,3}))?", re.I), "Boeing {}"),
    (re.compile(r"(?:airbus|a)[\s-]*(\d{3})(?:-(\d{1,3}))?", re.I), "Airbus A{}"),
    (re.compile(r"embraer[\s-]*(?:e)?(\d{3})", re.I), "Embraer E{}"),
    (re.compile(r"(?:bombardier\s+)?crj[\s-]*(\d{3})", re.I), "CRJ-{}"),
    (re.compile(r"atr[\s-]*(\d{2})", re.I), "ATR {}"),
    (re.compile(r"dash[\s-]*8", re.I), "Dash 8"),
    (re.compile(r"(?:dreamliner|787)", re.I), "Boeing 787"),
    (re.compile(r"(?:a380|superjumbo)", re.I), "Airbus A380"),
]

IATA_RE = re.compile(r"\b([A-Z]{3})\b")
ROUTE_RE = re.compile(r"([A-Z]{3})\s*[-–—→to]+\s*([A-Z]{3})")

COMMON_WORDS = frozenset(
    {
        "THE",
        "AND",
        "FOR",
        "WAS",
        "NOT",
        "BUT",
        "ARE",
        "ALL",
        "CAN",
        "HAS",
        "HAD",
        "HER",
        "HIS",
        "HIM",
        "HOW",
        "ITS",
        "MAY",
        "NEW",
        "NOW",
        "OLD",
        "OUR",
        "OUT",
        "OWN",
        "SAY",
        "SHE",
        "TOO",
        "USE",
        "WAY",
        "WHO",
        "BOY",
        "DID",
        "GET",
        "HIT",
        "LET",
        "PUT",
        "SAT",
        "TOP",
        "RED",
        "RUN",
        "SET",
        "TEN",
        "TWO",
        "WIN",
        "BIG",
        "FAR",
        "FEW",
        "GOT",
        "MAN",
        "AIR",
        "DAY",
        "EAT",
        "FLY",
        "LEG",
        "LOW",
        "ONE",
        "PAY",
        "SEA",
        "SIT",
        "TRY",
        "YES",
        "YET",
    }
)


class ReviewIntelligenceExtractor:
    """Extract structured aviation intelligence from review text."""

    def extract(self, text: str, title: str = "", metrics: dict | None = None) -> dict:
        combined = f"{title} {text}"
        metrics = metrics or {}

        disruptions = self._extract_disruptions(combined)
        quality = self._extract_quality(combined)
        aircraft = self._extract_aircraft(combined, metrics)
        routes = self._extract_routes(combined, metrics)
        airports = self._extract_airports(combined)
        severity = self._compute_severity(disruptions, quality)

        return {
            "disruptions": disruptions,
            "quality_scores": quality,
            "aircraft_mentions": aircraft,
            "route_mentions": routes,
            "airport_mentions": airports,
            "operational_severity": severity,
        }

    def _extract_disruptions(self, text: str) -> dict[str, bool]:
        return {k: bool(p.search(text)) for k, p in DISRUPTION_PATTERNS.items()}

    def _extract_quality(self, text: str) -> dict[str, float]:
        scores: dict[str, float] = {}
        for dim, pattern in QUALITY_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            pos = neg = 0
            for m in matches:
                start = max(0, m.start() - 60)
                end = min(len(text), m.end() + 60)
                window = text[start:end]
                pos += len(POSITIVE_WORDS.findall(window))
                neg += len(NEGATIVE_WORDS.findall(window))
            total = pos + neg
            scores[dim] = round((pos - neg) / max(total, 1), 2)
        return scores

    def _extract_aircraft(self, text: str, metrics: dict) -> list[str]:
        found: set[str] = set()
        if metrics.get("aircraft"):
            found.add(metrics["aircraft"])
        for pattern, fmt in AIRCRAFT_PATTERNS:
            for m in pattern.finditer(text):
                model = m.group(1) if m.lastindex else ""
                if model:
                    found.add(fmt.format(model))
                else:
                    found.add(fmt.format(""))
        return sorted(found)

    def _extract_routes(self, text: str, metrics: dict) -> list[dict]:
        routes: list[dict] = []
        if metrics.get("route"):
            routes.append({"raw": metrics["route"], "source": "metadata"})
        for m in ROUTE_RE.finditer(text):
            origin, dest = m.group(1), m.group(2)
            if origin not in COMMON_WORDS and dest not in COMMON_WORDS:
                routes.append({"origin": origin, "destination": dest, "source": "text"})
        return routes

    def _extract_airports(self, text: str) -> list[str]:
        codes = set()
        for m in IATA_RE.finditer(text):
            code = m.group(1)
            if code not in COMMON_WORDS and len(code) == 3:
                codes.add(code)
        return sorted(codes)

    def _compute_severity(self, disruptions: dict, quality: dict) -> str:
        active = sum(1 for v in disruptions.values() if v)
        neg_dims = sum(1 for v in quality.values() if v < -0.3)
        if active >= 3 or (active >= 2 and neg_dims >= 2):
            return "critical"
        if active >= 2 or neg_dims >= 3:
            return "high"
        if active >= 1 or neg_dims >= 1:
            return "medium"
        return "low"


def _pending_reviews_query(session: Session, batch_size: int):
    """Reviews without a review_intelligence row (NOT EXISTS — safe for large corpora)."""
    from sqlalchemy import exists, select

    has_intel = exists(select(ReviewIntelligence.id).where(ReviewIntelligence.review_id == Review.id))
    return session.query(Review).filter(~has_intel).order_by(Review.created_at.asc()).limit(batch_size)


def run_metadata_extraction(session: Session, batch_size: int = 500) -> dict:
    """Process unanalyzed reviews and persist ReviewIntelligence records."""
    from sqlalchemy import func

    extractor = ReviewIntelligenceExtractor()

    try:
        reviews = _pending_reviews_query(session, batch_size).all()
        total_reviews = session.query(func.count(Review.id)).scalar() or 0
        total_before = session.query(func.count(ReviewIntelligence.id)).scalar() or 0
    except Exception as exc:
        logger.exception("[METADATA] Failed to load pending reviews: %s", exc)
        session.rollback()
        return {
            "error": f"metadata_query_failed: {exc}",
            "reviews_analyzed": 0,
            "metadata_total": 0,
            "remaining": -1,
        }
    logger.info(
        "[METADATA] batch_start reviews_total=%d metadata_existing=%d pending=%d",
        total_reviews,
        total_before,
        len(reviews),
    )

    created = 0
    severity_counts: dict[str, int] = defaultdict(int)
    disruption_counts: dict[str, int] = defaultdict(int)

    for review in reviews:
        intel = extractor.extract(review.text, review.title or "", review.metrics or {})
        ri = ReviewIntelligence(
            review_id=review.id,
            disruptions=intel["disruptions"],
            quality_scores=intel["quality_scores"],
            aircraft_mentions=intel["aircraft_mentions"],
            route_mentions=intel["route_mentions"],
            airport_mentions=intel["airport_mentions"],
            operational_severity=intel["operational_severity"],
            intelligence_data=intel,
        )
        session.add(ri)
        created += 1
        severity_counts[intel["operational_severity"]] += 1
        for k, v in intel["disruptions"].items():
            if v:
                disruption_counts[k] += 1

    try:
        session.commit()
        logger.info(
            "[REVIEW_INTELLIGENCE] committed created=%d severities=%s disruptions=%s",
            created,
            dict(severity_counts),
            dict(disruption_counts),
        )
    except Exception as exc:
        logger.exception("[REVIEW_INTELLIGENCE] commit failed: %s", exc)
        session.rollback()
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "reviews_analyzed": 0,
            "metadata_total": total_before,
            "remaining": max(0, total_reviews - total_before),
            "pending_in_batch": len(reviews),
        }

    metadata_total = session.query(func.count(ReviewIntelligence.id)).scalar() or 0
    remaining = max(0, total_reviews - metadata_total)
    logger.info(
        "[METADATA] batch_done created=%d metadata_total=%d remaining=%d",
        created,
        metadata_total,
        remaining,
    )
    payload = {
        "reviews_analyzed": created,
        "metadata_total": metadata_total,
        "remaining": remaining,
        "severity_distribution": dict(severity_counts),
        "disruptions_found": dict(disruption_counts),
    }
    if created > 0 and metadata_total <= total_before:
        payload["error"] = "metadata_commit_no_rows_visible"
        payload["reviews_analyzed"] = 0
        logger.error(
            "[REVIEW_INTELLIGENCE] commit reported success but row count unchanged before=%d after=%d",
            total_before,
            metadata_total,
        )
    return payload


def run_metadata_extraction_until_done(
    session: Session,
    *,
    batch_size: int = 1000,
    max_batches: int = 50,
) -> dict:
    """Run metadata batches until corpus is covered or max_batches reached."""
    total_created = 0
    last: dict = {"reviews_analyzed": 0, "remaining": 0}
    batches_run = 0
    for _ in range(max_batches):
        batches_run += 1
        last = run_metadata_extraction(session, batch_size=batch_size)
        if "error" in last:
            last["batches_run"] = batches_run
            last["reviews_analyzed"] = total_created
            return last
        batch_created = int(last.get("reviews_analyzed", 0))
        total_created += batch_created
        if batch_created == 0 or last.get("remaining", 0) == 0:
            break
    last["reviews_analyzed"] = total_created
    last["batches_run"] = batches_run
    return last
