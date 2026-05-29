"""Operational Semantic Friction Matrix — weighted airline x cluster intelligence.

Replaces the naive topic_heatmap (raw TF-IDF term counts) with a proper
operational ontology, sentiment-weighted scoring, temporal decay and
derived risk metrics.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from database.models.core import Airline, NLPResult, Review

# ── Operational Ontology ──────────────────────────────────────
# Maps semantic cluster ids → keyword sets used for classification.
OPERATIONAL_CLUSTERS: dict[str, dict[str, Any]] = {
    "operational_delay": {
        "label": "Operational Delay",
        "keywords": {
            "delay",
            "delayed",
            "late",
            "cancelled",
            "cancellation",
            "missed connection",
            "flight disruption",
            "hours late",
            "rescheduled",
            "diverted",
            "waiting",
        },
        "severity": 0.90,
    },
    "baggage_incident": {
        "label": "Baggage Incident",
        "keywords": {
            "baggage",
            "luggage",
            "lost bag",
            "damaged luggage",
            "missing bag",
            "suitcase",
            "checked bag",
            "bag delayed",
            "broken suitcase",
        },
        "severity": 0.80,
    },
    "refund_problem": {
        "label": "Refund Problem",
        "keywords": {
            "refund",
            "compensation",
            "voucher",
            "reimbursement",
            "money back",
            "chargeback",
            "no refund",
            "claim denied",
            "credit",
        },
        "severity": 0.95,
    },
    "customer_service": {
        "label": "Customer Service",
        "keywords": {
            "rude",
            "unfriendly",
            "unprofessional",
            "staff",
            "customer service",
            "support",
            "helpdesk",
            "attitude",
            "ignored",
            "unhelpful",
            "arrogant",
        },
        "severity": 0.70,
    },
    "premium_experience": {
        "label": "Premium Experience",
        "keywords": {
            "lounge",
            "business class",
            "first class",
            "premium",
            "vip",
            "priority",
            "champagne",
            "amenity kit",
            "flat bed",
            "lie flat",
        },
        "severity": 0.20,
    },
    "seat_comfort": {
        "label": "Seat Comfort",
        "keywords": {
            "legroom",
            "cramped",
            "narrow",
            "seat",
            "recline",
            "uncomfortable",
            "pitch",
            "width",
            "cushion",
            "hard seat",
        },
        "severity": 0.35,
    },
    "food_quality": {
        "label": "Food & Catering",
        "keywords": {
            "food",
            "meal",
            "catering",
            "drink",
            "snack",
            "hungry",
            "tasteless",
            "cold food",
            "menu",
            "beverage",
        },
        "severity": 0.25,
    },
    "boarding_process": {
        "label": "Boarding Process",
        "keywords": {
            "boarding",
            "gate",
            "queue",
            "check-in",
            "checkin",
            "priority boarding",
            "boarding pass",
            "security",
            "chaotic",
            "disorganized",
        },
        "severity": 0.50,
    },
    "crew_behavior": {
        "label": "Crew Behavior",
        "keywords": {
            "crew",
            "attendant",
            "cabin crew",
            "flight attendant",
            "friendly crew",
            "helpful crew",
            "rude crew",
            "smiling",
            "attentive",
        },
        "severity": 0.55,
    },
    "connectivity": {
        "label": "IFE & Connectivity",
        "keywords": {
            "entertainment",
            "wifi",
            "screen",
            "ife",
            "headphones",
            "usb",
            "power outlet",
            "charging",
            "movie",
            "internet",
        },
        "severity": 0.15,
    },
    "safety_perception": {
        "label": "Safety Perception",
        "keywords": {
            "safety",
            "emergency",
            "turbulence",
            "security",
            "mask",
            "unsafe",
            "accident",
            "frightening",
        },
        "severity": 0.85,
    },
    "cleanliness": {
        "label": "Cleanliness & Hygiene",
        "keywords": {
            "dirty",
            "clean",
            "hygiene",
            "toilet",
            "lavatory",
            "filthy",
            "stain",
            "smell",
            "odor",
        },
        "severity": 0.45,
    },
    "disruption_management": {
        "label": "Disruption Management",
        "keywords": {
            "rebooking",
            "alternative flight",
            "hotel voucher",
            "no information",
            "communication",
            "stranded",
            "overnight",
            "no assistance",
        },
        "severity": 0.88,
    },
    "overbooking": {
        "label": "Overbooking",
        "keywords": {
            "overbooked",
            "overbooking",
            "denied boarding",
            "bumped",
            "involuntary",
            "standby",
        },
        "severity": 0.92,
    },
    "cancellation_risk": {
        "label": "Cancellation Risk",
        "keywords": {
            "cancelled",
            "cancellation",
            "no fly",
            "grounded",
            "suspended",
            "route cancelled",
        },
        "severity": 0.93,
    },
    "transfer_connection": {
        "label": "Transfer & Connections",
        "keywords": {
            "transfer",
            "connection",
            "connecting",
            "layover",
            "transit",
            "stopover",
            "missed connection",
            "tight connection",
        },
        "severity": 0.60,
    },
    "airport_experience": {
        "label": "Airport Experience",
        "keywords": {
            "airport",
            "terminal",
            "gate change",
            "long walk",
            "immigration",
            "customs",
            "passport control",
        },
        "severity": 0.30,
    },
}

CLUSTER_IDS = list(OPERATIONAL_CLUSTERS.keys())
CLUSTER_LABELS = [c["label"] for c in OPERATIONAL_CLUSTERS.values()]


def _temporal_weight(review_date: date | None, ref_date: date | None = None) -> float:
    """Exponential decay: 30d=1.0, 90d=0.6, 365d=0.15, older=0.05."""
    if not review_date:
        return 0.3
    ref = ref_date or date.today()
    days = max(0, (ref - review_date).days)
    if days <= 30:
        return 1.0
    return max(0.05, math.exp(-0.005 * days))


def _classify_review(text: str) -> list[str]:
    """Return list of cluster ids that match review text."""
    lower = text.lower()
    matched = []
    for cid, cfg in OPERATIONAL_CLUSTERS.items():
        if any(kw in lower for kw in cfg["keywords"]):
            matched.append(cid)
    return matched


class FrictionMatrixService:
    """Build the Operational Semantic Friction Matrix for airlines."""

    def __init__(self, session: Session):
        self.session = session

    def compute(self, top_airlines: int = 15) -> dict[str, Any]:
        """Return the full friction matrix payload for the frontend."""
        airlines = self._top_airlines(top_airlines)
        if not airlines:
            return {
                "airlines": [],
                "clusters": CLUSTER_LABELS,
                "cluster_ids": CLUSTER_IDS,
                "matrix": [],
                "metrics": {},
            }

        airline_map = {a["id"]: a for a in airlines}
        airline_ids = list(airline_map.keys())
        ref_date = date.today()

        reviews = (
            self.session.query(
                Review.airline_id,
                Review.text,
                Review.title,
                Review.rating,
                Review.recommended,
                Review.review_date,
                NLPResult.sentiment_label,
                NLPResult.sentiment_score,
            )
            .outerjoin(NLPResult, NLPResult.review_id == Review.id)
            .filter(Review.airline_id.in_(airline_ids))
            .all()
        )

        # airline_id → cluster_id → aggregated stats
        matrix_data: dict[str, dict[str, dict]] = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "count": 0,
                    "neg_count": 0,
                    "pos_count": 0,
                    "neu_count": 0,
                    "sentiment_sum": 0.0,
                    "weight_sum": 0.0,
                    "rating_sum": 0.0,
                    "rating_count": 0,
                    "recent_count": 0,
                    "older_count": 0,
                }
            )
        )

        airline_review_counts: Counter = Counter()

        for aid, text, title, rating, recommended, review_date, sent_label, sent_score in reviews:
            combined = f"{(title or '')} {(text or '')}"
            clusters = _classify_review(combined)
            if not clusters:
                continue

            t_weight = _temporal_weight(review_date, ref_date)
            airline_review_counts[aid] += 1

            for cid in clusters:
                cell = matrix_data[aid][cid]
                cell["count"] += 1
                cell["weight_sum"] += t_weight
                cell["sentiment_sum"] += sent_score or 0.0

                if sent_label == "negative":
                    cell["neg_count"] += 1
                elif sent_label == "positive":
                    cell["pos_count"] += 1
                else:
                    cell["neu_count"] += 1

                if rating is not None:
                    cell["rating_sum"] += rating
                    cell["rating_count"] += 1

                if review_date and (ref_date - review_date).days <= 30:
                    cell["recent_count"] += 1
                else:
                    cell["older_count"] += 1

        matrix_rows = []
        global_max_score = 0.01

        for aid in airline_ids:
            slug = airline_map[aid]["slug"]
            name = airline_map[aid]["name"]
            row_scores = []

            for cid in CLUSTER_IDS:
                cell = matrix_data[aid][cid]
                count = cell["count"]
                if count == 0:
                    row_scores.append(self._empty_cell(slug, name, cid))
                    continue

                severity = OPERATIONAL_CLUSTERS[cid]["severity"]
                neg_ratio = cell["neg_count"] / max(count, 1)
                avg_temporal = cell["weight_sum"] / max(count, 1)
                freq_ratio = count / max(airline_review_counts[aid], 1)

                friction_score = round(
                    100
                    * (
                        0.30 * neg_ratio
                        + 0.25 * severity
                        + 0.20 * freq_ratio
                        + 0.15 * avg_temporal
                        + 0.10
                        * (1.0 - min(cell.get("rating_sum", 5) / max(cell["rating_count"], 1) / 10.0, 1.0))
                    ),
                    1,
                )
                global_max_score = max(global_max_score, friction_score)

                avg_rating = (
                    round(cell["rating_sum"] / cell["rating_count"], 1) if cell["rating_count"] else None
                )
                trend_pct = _trend_pct(cell["recent_count"], cell["older_count"])

                row_scores.append(
                    {
                        "airline_slug": slug,
                        "airline_name": name,
                        "cluster_id": cid,
                        "cluster_label": OPERATIONAL_CLUSTERS[cid]["label"],
                        "score": friction_score,
                        "count": count,
                        "neg_pct": round(100 * neg_ratio, 1),
                        "pos_pct": round(100 * cell["pos_count"] / max(count, 1), 1),
                        "avg_rating": avg_rating,
                        "trend_pct": trend_pct,
                        "trend_dir": "worsening"
                        if trend_pct > 10
                        else "improving"
                        if trend_pct < -10
                        else "stable",
                        "recent_30d": cell["recent_count"],
                        "severity": severity,
                    }
                )

            matrix_rows.append(row_scores)

        aggregated_metrics = self._aggregate_metrics(matrix_rows, airline_map, airline_ids)

        return {
            "airlines": [
                {"slug": airline_map[a]["slug"], "name": airline_map[a]["name"]} for a in airline_ids
            ],
            "clusters": CLUSTER_LABELS,
            "cluster_ids": CLUSTER_IDS,
            "matrix": matrix_rows,
            "max_score": round(global_max_score, 1),
            "metrics": aggregated_metrics,
        }

    def cluster_drilldown(self, airline_slug: str, cluster_id: str, limit: int = 30) -> dict[str, Any]:
        """Detailed drill-down for a specific airline + cluster combination."""
        airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
        if not airline or cluster_id not in OPERATIONAL_CLUSTERS:
            return {"reviews": [], "cluster": cluster_id}

        cfg = OPERATIONAL_CLUSTERS[cluster_id]
        kw_list = list(cfg["keywords"])

        reviews = (
            self.session.query(
                Review.id,
                Review.title,
                Review.text,
                Review.rating,
                Review.review_date,
                Review.route,
                Review.seat_type,
                NLPResult.sentiment_label,
                NLPResult.sentiment_score,
            )
            .outerjoin(NLPResult, NLPResult.review_id == Review.id)
            .filter(Review.airline_id == airline.id)
            .order_by(Review.review_date.desc().nullslast())
            .limit(500)
            .all()
        )

        matched = []
        monthly: Counter = Counter()
        routes: Counter = Counter()

        for rid, title, text, rating, rdate, route, seat, slabel, sscore in reviews:
            combined = f"{(title or '')} {(text or '')}".lower()
            if not any(kw in combined for kw in kw_list):
                continue

            if rdate:
                monthly[rdate.strftime("%Y-%m")] += 1
            if route:
                routes[route] += 1

            matched.append(
                {
                    "id": rid,
                    "title": title,
                    "text": (text or "")[:300],
                    "rating": rating,
                    "date": rdate.isoformat() if rdate else None,
                    "route": route,
                    "seat_type": seat,
                    "sentiment": slabel,
                    "sentiment_score": round(sscore, 3) if sscore else None,
                }
            )
            if len(matched) >= limit:
                break

        timeline = [{"month": k, "count": v} for k, v in sorted(monthly.items())[-12:]]

        return {
            "airline": airline.name,
            "airline_slug": airline_slug,
            "cluster_id": cluster_id,
            "cluster_label": cfg["label"],
            "severity": cfg["severity"],
            "reviews": matched,
            "total_matched": len(matched),
            "timeline": timeline,
            "top_routes": [{"route": r, "count": c} for r, c in routes.most_common(8)],
        }

    # ── Private helpers ───────────────────────────────────────

    def _top_airlines(self, n: int) -> list[dict]:
        rows = (
            self.session.query(
                Airline.id,
                Airline.name,
                Airline.slug,
                func.count(Review.id).label("cnt"),
            )
            .join(Review, Review.airline_id == Airline.id)
            .filter(Airline.is_active.is_(True))
            .group_by(Airline.id, Airline.name, Airline.slug)
            .having(func.count(Review.id) >= 5)
            .order_by(desc("cnt"))
            .limit(n)
            .all()
        )
        return [{"id": r.id, "name": r.name, "slug": r.slug, "review_count": r.cnt} for r in rows]

    def _empty_cell(self, slug: str, name: str, cid: str) -> dict:
        return {
            "airline_slug": slug,
            "airline_name": name,
            "cluster_id": cid,
            "cluster_label": OPERATIONAL_CLUSTERS[cid]["label"],
            "score": 0,
            "count": 0,
            "neg_pct": 0,
            "pos_pct": 0,
            "avg_rating": None,
            "trend_pct": 0,
            "trend_dir": "stable",
            "recent_30d": 0,
            "severity": OPERATIONAL_CLUSTERS[cid]["severity"],
        }

    def _aggregate_metrics(self, matrix_rows: list, airline_map: dict, airline_ids: list) -> dict:
        airline_friction = {}
        cluster_friction: dict[str, list] = defaultdict(list)

        for row in matrix_rows:
            if not row:
                continue
            slug = row[0]["airline_slug"]
            scores = [c["score"] for c in row if c["score"] > 0]
            airline_friction[slug] = round(sum(scores) / max(len(scores), 1), 1) if scores else 0

            for c in row:
                if c["score"] > 0:
                    cluster_friction[c["cluster_id"]].append(c["score"])

        hottest_clusters = sorted(
            [(cid, round(sum(s) / len(s), 1)) for cid, s in cluster_friction.items() if s],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        riskiest = sorted(airline_friction.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "hottest_clusters": [{"cluster_id": c, "avg_score": s} for c, s in hottest_clusters],
            "riskiest_airlines": [{"slug": s, "friction_score": f} for s, f in riskiest],
            "global_friction": round(sum(airline_friction.values()) / max(len(airline_friction), 1), 1),
        }


def _trend_pct(recent: int, older: int) -> float:
    """Percentage change from older baseline to recent 30-day window."""
    if older == 0:
        return 100.0 if recent > 0 else 0.0
    return round(100 * (recent - older) / max(older, 1), 1)
