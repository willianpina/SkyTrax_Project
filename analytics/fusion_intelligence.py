"""Fusion Intelligence Engine — generates strategic signals by correlating graph data.

Produces high-level intelligence such as:
- Alliance-level reputational deterioration
- Hub stress patterns
- Regional complaint trends
- Aircraft-specific quality issues
- Emerging operational patterns
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.heartbeat import TimedHeartbeat
from database.models.core import Airline, Review
from database.models.graph import (
    FusionSignal,
    ReviewIntelligence,
)

logger = logging.getLogger(__name__)

_FUSION_SAFE_MODE = os.getenv("FUSION_SAFE_MODE", "0").lower() in ("1", "true", "yes")
_FUSION_SAFE_INTEL_LIMIT = int(os.getenv("FUSION_SAFE_INTEL_LIMIT", "8000"))


def _fusion_safe_mode() -> bool:
    return _FUSION_SAFE_MODE


class FusionIntelligenceEngine:
    """Cross-reference aviation knowledge graph to produce strategic intelligence signals."""

    def __init__(self, session: Session):
        self.session = session

    def generate_and_persist(
        self,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
        *,
        operation_id: str = "",
    ) -> dict:
        started = time.perf_counter()
        if heartbeat_fn:
            heartbeat_fn("fusion: correlation signals started")
        safe = _fusion_safe_mode()
        logger.info(
            "[SEMANTIC_CORRELATION] generate_and_persist start safe_mode=%s op=%s",
            safe,
            operation_id or "—",
        )
        if safe:
            logger.warning("[SAFE_MODE] FUSION_SAFE_MODE active — corpus limited for correlation")

        signals = self.generate_signals(heartbeat_fn=heartbeat_fn, operation_id=operation_id)

        if heartbeat_fn:
            heartbeat_fn(f"fusion: persisting {len(signals)} signals")
        persist_timer = TimedHeartbeat(
            heartbeat_fn, stage="fusion", substage="persist_signals", interval_s=25
        )

        try:
            self.session.query(FusionSignal).filter(FusionSignal.is_active.is_(True)).update(
                {"is_active": False},
                synchronize_session=False,
            )

            for idx, sig in enumerate(signals):
                self.session.add(
                    FusionSignal(
                        category=sig["category"],
                        severity=sig["severity"],
                        title=sig["title"],
                        description=sig["description"],
                        entities=sig.get("entities", []),
                        evidence=sig.get("evidence", {}),
                        confidence=sig.get("confidence", 0.5),
                    )
                )
                persist_timer.pulse_if_needed(
                    detail=f"fusion: persisting signal {idx}/{len(signals)}",
                    processed=idx,
                    total=len(signals),
                    current_substage="persist_signals",
                )
            self.session.commit()
            if heartbeat_fn:
                heartbeat_fn("fusion: commit complete")
            logger.info(
                "[GRAPH_PERSISTENCE] fusion_signals committed count=%d op=%s",
                len(signals),
                operation_id or "—",
            )
        except Exception as exc:
            logger.exception(
                "[GRAPH_PERSISTENCE] fusion signal persist failed: %s op=%s", exc, operation_id or "—"
            )
            self.session.rollback()

        total_active = (
            self.session.query(func.count(FusionSignal.id)).filter(FusionSignal.is_active.is_(True)).scalar()
            or 0
        )
        logger.info(
            "[OPS][FUSION] Generated %d strategic signals (active_in_db=%d)",
            len(signals),
            total_active,
        )
        categories: dict[str, int] = defaultdict(int)
        for s in signals:
            categories[s["category"]] += 1
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[SEMANTIC_CORRELATION] generate_and_persist done ms=%d semantic_pairs_generated=%d active_db=%d op=%s",
            duration_ms,
            len(signals),
            total_active,
            operation_id or "—",
        )
        return {
            "signals_generated": len(signals),
            "signals_total": int(total_active),
            "categories": dict(categories),
            "duration_ms": duration_ms,
            "safe_mode": safe,
            "persistence_validation": {"active_signals": int(total_active), "committed": True},
        }

    def generate_signals(
        self,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
        *,
        operation_id: str = "",
    ) -> list[dict]:
        signals: list[dict] = []
        intels_full = self._load_intels()
        logger.info(
            "[SEMANTIC_CORRELATION] metadata_loaded=%d op=%s",
            len(intels_full),
            operation_id or "—",
        )
        if heartbeat_fn:
            heartbeat_fn(f"fusion: loaded {len(intels_full)} intelligence rows")

        analyzers = (
            ("alliance_deterioration", lambda: self._alliance_deterioration()),
            ("hub_stress", lambda: self._hub_stress(intels_full, heartbeat_fn)),
            ("regional_trends", lambda: self._regional_trends(intels_full, heartbeat_fn)),
            ("aircraft_quality", lambda: self._aircraft_quality(intels_full, heartbeat_fn)),
            ("disruption_clusters", lambda: self._disruption_clusters(heartbeat_fn)),
        )
        for name, fn in analyzers:
            if heartbeat_fn:
                heartbeat_fn(f"fusion: analyzing {name}")
            logger.info("[SIGNALS] analyzer=%s", name)
            batch = fn()
            signals.extend(batch)
            if heartbeat_fn:
                heartbeat_fn(f"fusion: {name} produced {len(batch)} signals")
        return signals

    def _alliance_deterioration(self) -> list[dict]:
        """Detect alliance-level reputational patterns."""
        signals = []
        try:
            from database.models.aviation import AirlineMetadata, Alliance

            alliances = self.session.query(Alliance).all()
            for alliance in alliances:
                members = self.session.query(AirlineMetadata).filter_by(alliance_id=alliance.id).all()
                if len(members) < 2:
                    continue

                slugs = [m.slug for m in members]
                airlines = self.session.query(Airline).filter(Airline.slug.in_(slugs)).all()
                airline_ids = [a.id for a in airlines]
                if not airline_ids:
                    continue

                cutoff = datetime.now(timezone.utc) - timedelta(days=90)
                recent = (
                    self.session.query(func.avg(Review.rating))
                    .filter(Review.airline_id.in_(airline_ids), Review.review_date >= cutoff.date())
                    .scalar()
                )
                overall = (
                    self.session.query(func.avg(Review.rating))
                    .filter(Review.airline_id.in_(airline_ids))
                    .scalar()
                )

                if recent and overall and recent < overall * 0.85:
                    drop_pct = round((1 - recent / overall) * 100, 1)
                    signals.append(
                        {
                            "category": "alliance_deterioration",
                            "severity": "high" if drop_pct > 15 else "medium",
                            "title": f"{alliance.name} showing reputational decline",
                            "description": (
                                f"Average rating for {alliance.name} members dropped "
                                f"{drop_pct}% in the last 90 days vs. historical average."
                            ),
                            "entities": slugs,
                            "evidence": {
                                "recent_avg": round(recent, 2),
                                "overall_avg": round(overall, 2),
                                "drop_pct": drop_pct,
                                "member_count": len(members),
                            },
                            "confidence": min(0.9, 0.5 + len(airline_ids) * 0.05),
                        }
                    )
        except Exception as exc:
            logger.warning("[OPS][FUSION] Alliance analysis error: %s", exc)
        return signals

    def _preload_airline_map(self) -> dict[str, str]:
        """Preload airline_id → slug mapping to avoid N+1 queries."""
        if not hasattr(self, "_airline_map"):
            rows = self.session.query(Airline.id, Airline.slug).all()
            self._airline_map = {aid: slug for aid, slug in rows}
        return self._airline_map

    def _load_intels(self, since_days: int | None = None) -> list:
        """Load ReviewIntelligence+Review with optional date filter (single query)."""
        q = self.session.query(ReviewIntelligence, Review).join(
            Review, Review.id == ReviewIntelligence.review_id
        )
        if since_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            q = q.filter(Review.review_date >= cutoff.date())
        if _fusion_safe_mode() and since_days is None:
            q = q.limit(_FUSION_SAFE_INTEL_LIMIT)
            logger.warning(
                "[FUSION] FUSION_SAFE_MODE active — limiting corpus to %d rows",
                _FUSION_SAFE_INTEL_LIMIT,
            )
        return q.all()

    def _heartbeat_during_loop(
        self,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None,
        timer: TimedHeartbeat | None,
        label: str,
        index: int,
        total: int,
    ) -> None:
        if not heartbeat_fn:
            return
        if timer:
            timer.pulse_if_needed(
                detail=f"fusion: {label} {index}/{total}",
                processed=index,
                total=total,
                current_substage=label,
            )

    def _hub_stress(
        self,
        intels: list | None = None,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
    ) -> list[dict]:
        """Detect hubs with unusually high complaint density."""
        signals = []
        hub_complaints = defaultdict(lambda: {"total": 0, "disruptions": 0, "airlines": set()})
        airline_map = self._preload_airline_map()

        try:
            rows = intels if intels is not None else self._load_intels()
        except Exception as exc:
            logger.warning("[FUSION] Hub stress query failed: %s", exc)
            return []

        if not rows:
            return []
        timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="hub_stress", interval_s=25)

        for idx, (ri, review) in enumerate(rows):
            self._heartbeat_during_loop(heartbeat_fn, timer, "hub_stress scan", idx, len(rows))
            slug = airline_map.get(review.airline_id, "unknown")
            for code in ri.airport_mentions:
                hub_complaints[code]["total"] += 1
                hub_complaints[code]["airlines"].add(slug)
                if any(ri.disruptions.get(k) for k in ("delay", "cancellation", "missed_connection")):
                    hub_complaints[code]["disruptions"] += 1

        for code, data in hub_complaints.items():
            if data["total"] >= 10 and data["disruptions"] / data["total"] > 0.3:
                signals.append(
                    {
                        "category": "hub_stress",
                        "severity": "high" if data["disruptions"] > 20 else "medium",
                        "title": f"Operational stress detected at {code}",
                        "description": (
                            f"{code} has {data['disruptions']} disruption mentions across "
                            f"{len(data['airlines'])} airlines ({data['total']} total mentions)."
                        ),
                        "entities": sorted(data["airlines"]),
                        "evidence": {
                            "total_mentions": data["total"],
                            "disruption_mentions": data["disruptions"],
                            "airlines_affected": len(data["airlines"]),
                            "disruption_ratio": round(data["disruptions"] / data["total"], 2),
                        },
                        "confidence": min(0.9, 0.4 + data["total"] * 0.01),
                    }
                )
        return signals

    def _regional_trends(
        self,
        intels: list | None = None,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
    ) -> list[dict]:
        """Detect complaint trends by geographic region."""
        signals = []
        try:
            from database.models.aviation import AirlineMetadata

            region_data = defaultdict(lambda: {"count": 0, "total_rating": 0.0, "disruptions": 0})

            metas = self.session.query(AirlineMetadata).filter(AirlineMetadata.country.isnot(None)).all()
            slug_to_country = {m.slug: m.country for m in metas}

            airline_map = self._preload_airline_map()
            airline_country = {}
            for aid, slug in airline_map.items():
                airline_country[aid] = slug_to_country.get(slug)
            remaining_ids = [aid for aid, c in airline_country.items() if not c]
            if remaining_ids:
                rows = (
                    self.session.query(Airline.id, Airline.country)
                    .filter(Airline.id.in_(remaining_ids))
                    .all()
                )
                for aid, country in rows:
                    if country:
                        airline_country[aid] = country

            try:
                intel_rows = intels if intels is not None else self._load_intels()
            except Exception as exc:
                logger.warning("[FUSION] Regional intels query failed: %s", exc)
                return []
            timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="regional_trends", interval_s=25)

            for idx, (ri, review) in enumerate(intel_rows):
                self._heartbeat_during_loop(heartbeat_fn, timer, "regional scan", idx, len(intel_rows))
                country = airline_country.get(review.airline_id)
                if not country:
                    continue
                region_data[country]["count"] += 1
                region_data[country]["total_rating"] += review.rating or 0
                if any(ri.disruptions.values()):
                    region_data[country]["disruptions"] += 1

            for country, data in region_data.items():
                if data["count"] < 20:
                    continue
                avg_rating = data["total_rating"] / data["count"]
                disruption_rate = data["disruptions"] / data["count"]
                if avg_rating < 4.0 or disruption_rate > 0.25:
                    signals.append(
                        {
                            "category": "regional_trend",
                            "severity": "high" if avg_rating < 3.0 else "medium",
                            "title": f"Quality concerns in {country} carriers",
                            "description": (
                                f"{country}: avg rating {avg_rating:.1f}/10, "
                                f"{disruption_rate:.0%} disruption rate across {data['count']} reviews."
                            ),
                            "entities": [country],
                            "evidence": {
                                "avg_rating": round(avg_rating, 2),
                                "disruption_rate": round(disruption_rate, 2),
                                "review_count": data["count"],
                            },
                            "confidence": min(0.85, 0.3 + data["count"] * 0.005),
                        }
                    )
        except Exception as exc:
            logger.warning("[OPS][FUSION] Regional analysis error: %s", exc)
        return signals

    def _aircraft_quality(
        self,
        intels: list | None = None,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
    ) -> list[dict]:
        """Detect aircraft types with quality patterns."""
        signals = []
        aircraft_data = defaultdict(lambda: {"mentions": 0, "negative": 0, "airlines": set()})
        airline_map = self._preload_airline_map()

        try:
            rows = intels if intels is not None else self._load_intels()
        except Exception as exc:
            logger.warning("[FUSION] Aircraft quality query failed: %s", exc)
            return []

        if not rows:
            return []
        timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="aircraft_quality", interval_s=25)

        for idx, (ri, review) in enumerate(rows):
            self._heartbeat_during_loop(heartbeat_fn, timer, "aircraft scan", idx, len(rows))
            slug = airline_map.get(review.airline_id, "unknown")
            for ac in ri.aircraft_mentions:
                aircraft_data[ac]["mentions"] += 1
                aircraft_data[ac]["airlines"].add(slug)
                neg_count = sum(1 for v in ri.quality_scores.values() if v < -0.2)
                if neg_count >= 2:
                    aircraft_data[ac]["negative"] += 1

        for ac, data in aircraft_data.items():
            if data["mentions"] >= 10 and data["negative"] / data["mentions"] > 0.4:
                signals.append(
                    {
                        "category": "aircraft_quality",
                        "severity": "medium",
                        "title": f"Quality concerns on {ac} fleet",
                        "description": (
                            f"{ac} has {data['negative']}/{data['mentions']} negative quality mentions "
                            f"across {len(data['airlines'])} airlines."
                        ),
                        "entities": sorted(data["airlines"]),
                        "evidence": {
                            "mentions": data["mentions"],
                            "negative_ratio": round(data["negative"] / data["mentions"], 2),
                            "airlines": len(data["airlines"]),
                        },
                        "confidence": min(0.8, 0.3 + data["mentions"] * 0.01),
                    }
                )
        return signals

    def _disruption_clusters(
        self,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None = None,
    ) -> list[dict]:
        """Detect airlines with emerging disruption patterns."""
        signals = []
        airline_disruptions = defaultdict(lambda: defaultdict(int))

        airline_names = {row.id: row.name for row in self.session.query(Airline.id, Airline.name).all()}

        try:
            intels = self._load_intels(since_days=90)
        except Exception as exc:
            logger.warning("[FUSION] Disruption cluster query failed: %s", exc)
            return []

        if not intels:
            return []
        timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="disruption_clusters", interval_s=25)

        for idx, (ri, review) in enumerate(intels):
            self._heartbeat_during_loop(heartbeat_fn, timer, "disruption scan", idx, len(intels))
            name = airline_names.get(review.airline_id)
            if not name:
                continue
            for k, v in ri.disruptions.items():
                if v:
                    airline_disruptions[name][k] += 1

        for airline_name, types in airline_disruptions.items():
            total = sum(types.values())
            if total >= 5:
                dominant = max(types, key=types.get)
                signals.append(
                    {
                        "category": "disruption_cluster",
                        "severity": "high" if total >= 15 else "medium",
                        "title": f"{airline_name}: {dominant.replace('_', ' ')} pattern emerging",
                        "description": (
                            f"{airline_name} has {total} disruption mentions in 90 days. "
                            f"Primary: {dominant} ({types[dominant]}x)."
                        ),
                        "entities": [airline_name],
                        "evidence": {"types": dict(types), "total": total},
                        "confidence": min(0.85, 0.4 + total * 0.02),
                    }
                )
        return signals
