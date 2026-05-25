from __future__ import annotations

from app.airline_catalog import SEED_AIRLINES

PRIORITY_AIRLINES = [row["slug"] for row in sorted(SEED_AIRLINES, key=lambda r: r.get("priority", 99))[:10]]

BENCHMARK_AIRLINES = [row["slug"] for row in SEED_AIRLINES]

PREMIUM_AIRLINES = [r["slug"] for r in SEED_AIRLINES if r.get("tier") == "premium"]
LOW_COST_AIRLINES = [r["slug"] for r in SEED_AIRLINES if r.get("tier") == "low_cost"]
REGIONAL_AIRLINES = [r["slug"] for r in SEED_AIRLINES if r.get("tier") == "regional"]
STRATEGIC_AIRLINES = [r["slug"] for r in SEED_AIRLINES if r.get("tier") == "strategic"]

SEMANTIC_CLUSTER_LABELS: dict[str, set[str]] = {
    "baggage": {"baggage", "luggage", "lost", "missing", "claim", "suitcase"},
    "delays": {"delay", "delayed", "late", "cancellation", "cancelled", "wait"},
    "refunds": {"refund", "compensation", "voucher", "charge", "money"},
    "premium service": {"business", "first", "premium", "lounge", "suite", "flat", "champagne"},
    "crew": {"crew", "staff", "attendant", "rude", "friendly", "pilot", "cabin"},
    "airport operations": {"airport", "terminal", "security", "immigration", "customs", "gate"},
    "customer support": {"support", "helpline", "contact", "response", "complaint", "call"},
}

SEMANTIC_CONFIDENCE_THRESHOLD = 0.35

ANOMALY_ALERT_TYPES = {
    "reputational_risk": "reputation_score",
    "operational_instability": "complaint_density",
    "premium_service_degradation": "sentiment_negative",
    "refund_crisis": "topic_refunds",
    "baggage_crisis": "topic_baggage",
    "route_instability": "route_complaints",
    "cancellation_wave": "cancellation",
}

SEED_AIRPORTS = [
    ("LHR", "London Heathrow", 51.4700, -0.4543, "EU"),
    ("DXB", "Dubai International", 25.2532, 55.3657, "ME"),
    ("DOH", "Hamad International", 25.2731, 51.6081, "ME"),
    ("FRA", "Frankfurt", 50.0379, 8.5622, "EU"),
    ("GRU", "São Paulo Guarulhos", -23.4356, -46.4731, "SA"),
    ("JFK", "New York JFK", 40.6413, -73.7781, "NA"),
    ("SIN", "Singapore Changi", 1.3644, 103.9915, "AP"),
]

SEED_REGIONS = [
    ("EU", "Europe"),
    ("ME", "Middle East"),
    ("SA", "South America"),
    ("NA", "North America"),
    ("AP", "Asia Pacific"),
]
