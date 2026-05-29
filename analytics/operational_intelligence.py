"""Operational Aviation Intelligence -- transforms review corpus into actionable intelligence.

Provides:
  - Review enrichment (route, airport, cabin class, premium/low-cost detection)
  - Operational risk scoring (airline, alliance, hub, route)
  - Heatmap generators (airline x topic, airport x complaint, route x sentiment)
  - Executive intelligence signals (deterioration, emerging patterns, abrupt changes)
"""

from __future__ import annotations

import re
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Integer, func, case, desc
from sqlalchemy.orm import Session

from database.models.core import Airline, Review

logger = logging.getLogger(__name__)

CABIN_CLASSES = {
    "first class": "first_class",
    "business class": "business",
    "premium economy": "premium_economy",
    "economy class": "economy",
    "economy": "economy",
    "business": "business",
    "first": "first_class",
}

COMPLAINT_CATEGORIES = {
    "baggage": {"baggage", "luggage", "lost bag", "suitcase", "missing bag", "damaged bag"},
    "delays": {"delay", "delayed", "late", "cancelled", "cancellation", "hours late"},
    "refund": {"refund", "compensation", "voucher", "reimbursement", "money back"},
    "crew": {"rude", "unfriendly", "unprofessional", "staff", "attendant", "crew"},
    "food": {"food", "meal", "catering", "drink", "snack", "hungry"},
    "comfort": {"uncomfortable", "legroom", "cramped", "narrow", "seat", "recline"},
    "entertainment": {"entertainment", "screen", "ife", "wifi", "headphones"},
    "boarding": {"boarding", "gate", "priority", "queue", "check-in", "checkin"},
    "lounge": {"lounge", "access", "priority pass", "business lounge"},
    "transfer": {"transfer", "connection", "connecting", "layover", "transit", "stopover"},
    "cleanliness": {"dirty", "clean", "hygiene", "toilet", "lavatory", "filthy"},
    "safety": {"safety", "emergency", "turbulence", "security", "mask"},
}

AIRPORT_PATTERNS = re.compile(
    r"\b([A-Z]{3})\b"
    r"|(?:at|from|to|via|through|into)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Airport|International|Terminal))",
    re.IGNORECASE,
)

ROUTE_PATTERN = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:to|→|->|-)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
)


class ReviewEnrichmentEngine:
    """Extract structured intelligence from review text."""

    def enrich(self, review: dict) -> dict:
        text = (review.get("text") or "").lower()
        title = (review.get("title") or "").lower()
        combined = f"{title} {text}"
        metrics = review.get("metrics") or {}

        cabin = self._detect_cabin(combined, metrics)
        complaints = self._detect_complaints(combined)
        airports = self._detect_airports(review.get("text") or "", review.get("route"))
        is_premium = cabin in ("first_class", "business")
        is_transfer = "transfer" in complaints or bool(
            re.search(r"connect|layover|transit|stopover", combined)
        )

        return {
            "cabin_class": cabin,
            "complaints": complaints,
            "airports_mentioned": airports,
            "is_premium_cabin": is_premium,
            "is_transfer_journey": is_transfer,
            "complaint_count": len(complaints),
            "route": review.get("route") or metrics.get("route"),
            "aircraft": review.get("aircraft") or metrics.get("aircraft"),
        }

    def _detect_cabin(self, text: str, metrics: dict) -> str:
        seat = metrics.get("seat_type", "").lower()
        for keyword, cabin in CABIN_CLASSES.items():
            if keyword in seat or keyword in text:
                return cabin
        return "economy"

    def _detect_complaints(self, text: str) -> list[str]:
        found = []
        for category, keywords in COMPLAINT_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                found.append(category)
        return found

    def _detect_airports(self, text: str, route: str | None) -> list[str]:
        airports = set()
        iata_codes = re.findall(r"\b([A-Z]{3})\b", text)
        for code in iata_codes:
            if code not in {
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
            }:
                airports.add(code)
        if route:
            parts = re.split(r"\s+to\s+|\s*[-→>]\s*", route, flags=re.IGNORECASE)
            for part in parts:
                iata = re.search(r"\b([A-Z]{3})\b", part)
                if iata:
                    airports.add(iata.group(1))
        return sorted(airports)


class OperationalIntelligenceService:
    """Full operational intelligence from review corpus."""

    def __init__(self, session: Session):
        self.session = session
        self.enricher = ReviewEnrichmentEngine()

    def operational_dashboard(self) -> dict[str, Any]:
        """Complete operational intelligence dashboard payload."""
        airlines_with_reviews = self._airlines_with_reviews()
        slugs = [a["slug"] for a in airlines_with_reviews]

        return {
            "corpus_stats": self._corpus_stats(),
            "airline_rankings": self._airline_rankings(limit=30),
            "operational_risk": self._operational_risk_ranking(slugs),
            "cabin_analysis": self._cabin_class_analysis(),
            "complaint_heatmap": self._complaint_heatmap(slugs[:20]),
            "route_intelligence": self._route_intelligence(),
            "deterioration_alerts": self._deterioration_alerts(),
            "premium_dissatisfaction": self._premium_dissatisfaction(),
            "executive_signals": self._executive_signals(),
        }

    def _corpus_stats(self) -> dict:
        total = self.session.query(func.count(Review.id)).scalar() or 0
        airlines = self.session.query(func.count(func.distinct(Review.airline_id))).scalar() or 0
        with_route = self.session.query(func.count(Review.id)).filter(Review.route.isnot(None)).scalar() or 0
        avg_rating = self.session.query(func.avg(Review.rating)).scalar()
        rec_rate = self.session.query(func.avg(func.cast(Review.recommended, Integer))).scalar()
        oldest = self.session.query(func.min(Review.review_date)).scalar()
        newest = self.session.query(func.max(Review.review_date)).scalar()
        return {
            "total_reviews": total,
            "airlines_covered": airlines,
            "reviews_with_route": with_route,
            "average_rating": round(float(avg_rating or 0), 2),
            "recommendation_rate": round(float(rec_rate or 0), 3),
            "date_range": {
                "oldest": oldest.isoformat() if oldest else None,
                "newest": newest.isoformat() if newest else None,
            },
        }

    def _airlines_with_reviews(self) -> list[dict]:
        rows = (
            self.session.query(
                Airline.name,
                Airline.slug,
                Airline.country,
                func.count(Review.id).label("cnt"),
                func.avg(Review.rating).label("avg_r"),
            )
            .join(Review)
            .group_by(Airline.id)
            .order_by(desc("cnt"))
            .all()
        )
        return [
            {"name": n, "slug": s, "country": c, "review_count": cnt, "avg_rating": round(float(avg or 0), 2)}
            for n, s, c, cnt, avg in rows
        ]

    def _airline_rankings(self, limit: int = 30) -> list[dict]:
        rows = (
            self.session.query(
                Airline.name,
                Airline.slug,
                Airline.country,
                func.count(Review.id).label("review_count"),
                func.avg(Review.rating).label("avg_rating"),
                func.avg(func.cast(Review.recommended, Integer)).label("rec_rate"),
                func.count(case((Review.recommended.is_(False), 1))).label("complaints"),
            )
            .join(Review)
            .group_by(Airline.id)
            .having(func.count(Review.id) >= 10)
            .order_by(desc("avg_rating"))
            .limit(limit)
            .all()
        )
        return [
            {
                "rank": i + 1,
                "name": name,
                "slug": slug,
                "country": country,
                "review_count": int(cnt),
                "avg_rating": round(float(avg or 0), 2),
                "recommendation_rate": round(float(rec or 0), 3),
                "complaint_count": int(comp),
                "complaint_density": round(int(comp) / max(int(cnt), 1), 3),
            }
            for i, (name, slug, country, cnt, avg, rec, comp) in enumerate(rows)
        ]

    def _operational_risk_ranking(self, slugs: list[str]) -> list[dict]:
        if not slugs:
            return []
        result = []
        for slug in slugs[:30]:
            airline = self.session.query(Airline).filter_by(slug=slug).first()
            if not airline:
                continue
            stats = (
                self.session.query(
                    func.count(Review.id),
                    func.avg(Review.rating),
                    func.avg(func.cast(Review.recommended, Integer)),
                    func.count(case((Review.recommended.is_(False), 1))),
                )
                .filter(Review.airline_id == airline.id)
                .first()
            )

            total, avg_r, rec, complaints = stats
            if not total:
                continue
            complaint_density = int(complaints) / max(int(total), 1)
            low_rating_penalty = max(0, (5.0 - float(avg_r or 5)) / 5.0)
            risk_score = round(
                0.5 * complaint_density + 0.3 * low_rating_penalty + 0.2 * (1 - float(rec or 0.5)),
                3,
            )
            result.append(
                {
                    "airline": airline.name,
                    "slug": slug,
                    "risk_score": round(risk_score * 100, 1),
                    "complaint_density": round(complaint_density, 3),
                    "avg_rating": round(float(avg_r or 0), 2),
                    "review_count": int(total),
                    "risk_level": "critical"
                    if risk_score > 0.6
                    else "high"
                    if risk_score > 0.4
                    else "medium"
                    if risk_score > 0.25
                    else "low",
                }
            )
        return sorted(result, key=lambda x: x["risk_score"], reverse=True)

    def _cabin_class_analysis(self) -> dict:
        rows = (
            self.session.query(
                Review.seat_type,
                func.count(Review.id),
                func.avg(Review.rating),
                func.avg(func.cast(Review.recommended, Integer)),
            )
            .filter(Review.seat_type.isnot(None))
            .group_by(Review.seat_type)
            .all()
        )
        return {
            "by_cabin": [
                {
                    "cabin": st or "Unknown",
                    "review_count": int(cnt),
                    "avg_rating": round(float(avg or 0), 2),
                    "recommendation_rate": round(float(rec or 0), 3),
                }
                for st, cnt, avg, rec in rows
            ],
        }

    def _complaint_heatmap(self, slugs: list[str]) -> list[dict]:
        """airline x complaint_category matrix."""
        if not slugs:
            return []
        airlines = self.session.query(Airline).filter(Airline.slug.in_(slugs)).all()
        result = []
        for airline in airlines:
            reviews = (
                self.session.query(Review.text, Review.title)
                .filter(Review.airline_id == airline.id)
                .limit(500)
                .all()
            )
            cat_counts: Counter = Counter()
            for text, title in reviews:
                combined = f"{(title or '').lower()} {(text or '').lower()}"
                for category, keywords in COMPLAINT_CATEGORIES.items():
                    if any(kw in combined for kw in keywords):
                        cat_counts[category] += 1
            if cat_counts:
                result.append(
                    {
                        "airline": airline.name,
                        "slug": airline.slug,
                        "categories": dict(cat_counts.most_common(12)),
                        "dominant_complaint": cat_counts.most_common(1)[0][0] if cat_counts else None,
                    }
                )
        return result

    def _route_intelligence(self) -> dict:
        rows = (
            self.session.query(
                Review.route,
                func.count(Review.id).label("cnt"),
                func.avg(Review.rating).label("avg"),
                func.avg(func.cast(Review.recommended, Integer)).label("rec"),
            )
            .filter(Review.route.isnot(None), Review.route != "")
            .group_by(Review.route)
            .having(func.count(Review.id) >= 3)
            .order_by(desc("cnt"))
            .limit(30)
            .all()
        )
        routes = [
            {
                "route": route,
                "review_count": int(cnt),
                "avg_rating": round(float(avg or 0), 2),
                "recommendation_rate": round(float(rec or 0), 3),
                "risk_level": "high" if float(avg or 5) < 4 else "medium" if float(avg or 5) < 6 else "low",
            }
            for route, cnt, avg, rec in rows
        ]
        worst = sorted(routes, key=lambda x: x["avg_rating"])[:10]
        best = sorted(routes, key=lambda x: -x["avg_rating"])[:10]
        return {"top_routes": routes, "worst_routes": worst, "best_routes": best}

    def _deterioration_alerts(self) -> list[dict]:
        """Detect airlines with worsening ratings over recent periods."""
        alerts = []
        cutoff_recent = date.today() - timedelta(days=90)
        cutoff_old = date.today() - timedelta(days=365)

        rows = (
            self.session.query(
                Airline.name,
                Airline.slug,
                func.avg(case((Review.review_date >= cutoff_recent, Review.rating))).label("recent_avg"),
                func.avg(case((Review.review_date < cutoff_recent, Review.rating))).label("old_avg"),
                func.count(case((Review.review_date >= cutoff_recent, Review.id))).label("recent_count"),
            )
            .join(Review)
            .filter(Review.review_date >= cutoff_old)
            .group_by(Airline.id)
            .having(func.count(Review.id) >= 20)
            .all()
        )
        for name, slug, recent_avg, old_avg, recent_count in rows:
            if recent_avg is None or old_avg is None:
                continue
            r, o = float(recent_avg), float(old_avg)
            if o > 0:
                delta = (r - o) / o
                if delta <= -0.10:
                    alerts.append(
                        {
                            "airline": name,
                            "slug": slug,
                            "recent_avg_rating": round(r, 2),
                            "historical_avg_rating": round(o, 2),
                            "delta_pct": round(delta * 100, 1),
                            "recent_reviews": int(recent_count),
                            "severity": "critical"
                            if delta <= -0.25
                            else "high"
                            if delta <= -0.15
                            else "medium",
                            "signal": "deterioration",
                        }
                    )
        return sorted(alerts, key=lambda x: x["delta_pct"])

    def _premium_dissatisfaction(self) -> dict:
        """Analyze premium cabin sentiment vs economy."""
        premium_types = ["Business Class", "First Class"]
        economy_types = ["Economy Class"]

        def _stats(seat_types):
            return (
                self.session.query(
                    func.count(Review.id),
                    func.avg(Review.rating),
                    func.avg(func.cast(Review.recommended, Integer)),
                )
                .filter(Review.seat_type.in_(seat_types))
                .first()
            )

        prem = _stats(premium_types)
        econ = _stats(economy_types)

        premium_rows = (
            self.session.query(
                Airline.name,
                Airline.slug,
                func.count(Review.id),
                func.avg(Review.rating),
            )
            .join(Review)
            .filter(Review.seat_type.in_(premium_types))
            .group_by(Airline.id)
            .having(func.count(Review.id) >= 5)
            .order_by(func.avg(Review.rating).asc())
            .limit(10)
            .all()
        )

        return {
            "premium": {
                "count": int(prem[0] or 0),
                "avg_rating": round(float(prem[1] or 0), 2),
                "rec_rate": round(float(prem[2] or 0), 3),
            },
            "economy": {
                "count": int(econ[0] or 0),
                "avg_rating": round(float(econ[1] or 0), 2),
                "rec_rate": round(float(econ[2] or 0), 3),
            },
            "gap": round(float(prem[1] or 0) - float(econ[1] or 0), 2) if prem[1] and econ[1] else 0,
            "worst_premium_airlines": [
                {"airline": n, "slug": s, "reviews": int(c), "avg_rating": round(float(a or 0), 2)}
                for n, s, c, a in premium_rows
            ],
        }

    def _executive_signals(self) -> list[dict]:
        """High-level executive intelligence signals from the corpus."""
        signals = []

        total = self.session.query(func.count(Review.id)).scalar() or 0
        airlines_count = self.session.query(func.count(func.distinct(Review.airline_id))).scalar() or 0
        avg = self.session.query(func.avg(Review.rating)).scalar()

        if total >= 100:
            rec_false = (
                self.session.query(func.count(Review.id)).filter(Review.recommended.is_(False)).scalar() or 0
            )
            complaint_share = rec_false / max(total, 1)
            if complaint_share > 0.45:
                signals.append(
                    {
                        "type": "portfolio_risk",
                        "severity": "high",
                        "signal": f"Industry-wide complaint rate at {round(complaint_share * 100, 1)}% across {airlines_count} airlines.",
                        "metric": round(complaint_share * 100, 1),
                    }
                )

        recent = date.today() - timedelta(days=30)
        recent_avg = self.session.query(func.avg(Review.rating)).filter(Review.review_date >= recent).scalar()
        if recent_avg and avg:
            delta = float(recent_avg) - float(avg)
            if abs(delta) > 0.5:
                direction = "improving" if delta > 0 else "deteriorating"
                signals.append(
                    {
                        "type": "trend_shift",
                        "severity": "medium" if abs(delta) < 1.0 else "high",
                        "signal": f"Industry sentiment is {direction}: 30-day avg {round(float(recent_avg), 2)} vs historical {round(float(avg), 2)}.",
                        "metric": round(delta, 2),
                    }
                )

        worst_airlines = (
            self.session.query(Airline.name, func.avg(Review.rating))
            .join(Review)
            .group_by(Airline.id)
            .having(func.count(Review.id) >= 20)
            .order_by(func.avg(Review.rating).asc())
            .limit(3)
            .all()
        )
        for name, r in worst_airlines:
            if float(r or 10) < 3.5:
                signals.append(
                    {
                        "type": "airline_risk",
                        "severity": "critical",
                        "signal": f"{name} has critical reputation risk with avg rating {round(float(r), 2)}/10.",
                        "metric": round(float(r), 2),
                    }
                )

        return signals

    def alliance_risk(self) -> list[dict]:
        """Risk analysis per alliance."""
        try:
            from database.models.aviation import AirlineMetadata, Alliance

            alliances = self.session.query(Alliance).all()
        except Exception:
            return []

        result = []
        for alliance in alliances:
            from database.models.aviation import AirlineMetadata

            members = self.session.query(AirlineMetadata).filter_by(alliance_id=alliance.id).all()
            member_slugs = [m.slug for m in members]
            if not member_slugs:
                continue

            airlines = self.session.query(Airline).filter(Airline.slug.in_(member_slugs)).all()
            airline_ids = [a.id for a in airlines]
            if not airline_ids:
                continue

            stats = (
                self.session.query(
                    func.count(Review.id),
                    func.avg(Review.rating),
                    func.avg(func.cast(Review.recommended, Integer)),
                    func.count(case((Review.recommended.is_(False), 1))),
                )
                .filter(Review.airline_id.in_(airline_ids))
                .first()
            )

            total, avg_r, rec, complaints = stats
            complaint_density = int(complaints or 0) / max(int(total or 1), 1)
            risk = round(complaint_density * 0.6 + (1 - float(rec or 0.5)) * 0.4, 3) if total else 0

            result.append(
                {
                    "alliance": alliance.name,
                    "member_count": len(members),
                    "total_reviews": int(total or 0),
                    "avg_rating": round(float(avg_r or 0), 2),
                    "complaint_density": round(complaint_density, 3),
                    "risk_score": round(risk * 100, 1),
                    "risk_level": "high" if risk > 0.5 else "medium" if risk > 0.3 else "low",
                }
            )
        return sorted(result, key=lambda x: x["risk_score"], reverse=True)

    def airport_friction(self) -> list[dict]:
        """Detect airports with high complaint density from review routes."""
        rows = (
            self.session.query(Review.route, Review.text, Review.title, Review.rating)
            .filter(
                Review.route.isnot(None),
            )
            .limit(5000)
            .all()
        )

        airport_stats: dict[str, dict] = defaultdict(
            lambda: {"mentions": 0, "complaints": 0, "rating_sum": 0.0}
        )
        for route, text, title, rating in rows:
            combined = f"{route or ''} {title or ''} {text or ''}"
            codes = re.findall(r"\b([A-Z]{3})\b", combined)
            skip = {
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
            }
            for code in set(codes) - skip:
                airport_stats[code]["mentions"] += 1
                airport_stats[code]["rating_sum"] += float(rating or 5)
                low_text = combined.lower()
                if any(
                    kw in low_text for kw in ("delay", "lost", "cancelled", "rude", "dirty", "queue", "hours")
                ):
                    airport_stats[code]["complaints"] += 1

        result = []
        for code, data in airport_stats.items():
            if data["mentions"] >= 5:
                friction = data["complaints"] / data["mentions"]
                avg_r = data["rating_sum"] / data["mentions"]
                result.append(
                    {
                        "iata": code,
                        "mentions": data["mentions"],
                        "complaints": data["complaints"],
                        "friction_score": round(friction * 100, 1),
                        "avg_rating": round(avg_r, 2),
                        "risk_level": "high" if friction > 0.5 else "medium" if friction > 0.3 else "low",
                    }
                )
        return sorted(result, key=lambda x: x["friction_score"], reverse=True)[:30]

    def transfer_bottlenecks(self) -> list[dict]:
        """Detect connection/transfer pain points from review text."""
        transfer_keywords = {
            "connection",
            "connecting",
            "transfer",
            "layover",
            "transit",
            "stopover",
            "missed",
        }
        rows = (
            self.session.query(
                Airline.name, Airline.slug, Review.text, Review.title, Review.route, Review.rating
            )
            .join(Airline)
            .limit(5000)
            .all()
        )

        airline_transfer: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "complaint": 0, "rating_sum": 0.0}
        )
        for name, slug, text, title, route, rating in rows:
            combined = f"{(title or '').lower()} {(text or '').lower()}"
            if any(kw in combined for kw in transfer_keywords):
                airline_transfer[slug]["name"] = name
                airline_transfer[slug]["count"] += 1
                airline_transfer[slug]["rating_sum"] += float(rating or 5)
                if any(kw in combined for kw in ("missed", "lost", "delay", "hours", "cancelled")):
                    airline_transfer[slug]["complaint"] += 1

        result = []
        for slug, data in airline_transfer.items():
            if data["count"] >= 3:
                friction = data["complaint"] / data["count"]
                result.append(
                    {
                        "airline": data.get("name", slug),
                        "slug": slug,
                        "transfer_reviews": data["count"],
                        "transfer_complaints": data["complaint"],
                        "friction_rate": round(friction, 3),
                        "avg_rating": round(data["rating_sum"] / data["count"], 2),
                    }
                )
        return sorted(result, key=lambda x: x["friction_rate"], reverse=True)[:20]
