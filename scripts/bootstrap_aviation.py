#!/usr/bin/env python3
"""Aviation metadata bootstrap -- full crawl, enrichment, and coverage validation.

Usage:
    python scripts/bootstrap_aviation.py              # full bootstrap
    python scripts/bootstrap_aviation.py --spiders    # crawl only
    python scripts/bootstrap_aviation.py --enrich     # enrichment only
    python scripts/bootstrap_aviation.py --validate   # coverage validation only
    python scripts/bootstrap_aviation.py --report     # generate coverage report
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Callable

from app.heartbeat import TimedHeartbeat, heartbeat_guard

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aviation_bootstrap")

_SAFE_TRUTHY = {"1", "true", "yes", "on"}
_MAX_ENRICH_SECONDS = int(os.getenv("FUSION_MAX_ENRICH_SECONDS", "120"))


def _env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in _SAFE_TRUTHY


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def run_spider(
    spider_name: str,
    *,
    timeout_s: int | None = None,
    heartbeat_fn: Callable[[str], None] | None = None,
) -> dict:
    logger.info("[FUSION] Starting spider=%s timeout_s=%s", spider_name, timeout_s)
    started = time.perf_counter()
    if heartbeat_fn:
        heartbeat_fn(f"fusion: spider {spider_name} started")
    try:
        result = subprocess.run(
            ["scrapy", "crawl", spider_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
        elapsed = round(time.perf_counter() - started, 2)
        success = result.returncode == 0
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 2)
        logger.warning(
            "[FUSION_TIMEOUT] spider=%s timeout_s=%s elapsed=%.2fs", spider_name, timeout_s, elapsed
        )
        if heartbeat_fn:
            heartbeat_fn(f"fusion timeout: spider {spider_name}")
        return {
            "spider": spider_name,
            "success": False,
            "timeout": True,
            "elapsed_s": elapsed,
            "error": f"spider timeout after {timeout_s}s",
            "stderr_tail": (exc.stderr or "")[-1000:],
        }
    logger.info(
        "[FUSION] Spider finished spider=%s success=%s elapsed=%.2fs",
        spider_name,
        success,
        elapsed,
    )
    if not success:
        logger.error("Spider %s stderr: %s", spider_name, result.stderr[-1500:])
    if heartbeat_fn:
        heartbeat_fn(f"fusion: spider {spider_name} finished success={success}")
    return {"spider": spider_name, "success": success, "elapsed_s": elapsed}


def run_spiders() -> list[dict]:
    results = []
    for spider in ["airline_metadata", "airport_metadata"]:
        results.append(run_spider(spider))
    return results


KNOWN_ALLIANCES = {
    "Star Alliance": {"slug": "star-alliance", "founded_year": 1997, "headquarters": "Frankfurt, Germany"},
    "Oneworld": {"slug": "oneworld", "founded_year": 1999, "headquarters": "New York, USA"},
    "SkyTeam": {"slug": "skyteam", "founded_year": 2000, "headquarters": "Amsterdam, Netherlands"},
}

AIRLINE_ALLIANCE_MAP = {
    "lufthansa": "Star Alliance",
    "british-airways": "Oneworld",
    "emirates": None,
    "latam": None,
    "qatar-airways": "Oneworld",
    "singapore-airlines": "Star Alliance",
    "turkish-airlines": "Star Alliance",
    "delta-air-lines": "SkyTeam",
    "united-airlines": "Star Alliance",
    "air-france": "SkyTeam",
    "klm": "SkyTeam",
    "american-airlines": "Oneworld",
    "cathay-pacific": "Oneworld",
    "ana": "Star Alliance",
    "swiss": "Star Alliance",
    "air-canada": "Star Alliance",
    "iberia": "Oneworld",
    "tap-portugal": "Star Alliance",
    "etihad-airways": None,
    "japan-airlines": "Oneworld",
}

AIRLINE_HUBS = {
    "lufthansa": ["FRA", "MUC"],
    "british-airways": ["LHR", "LGW"],
    "emirates": ["DXB"],
    "latam": ["GRU", "SCL"],
    "qatar-airways": ["DOH"],
    "singapore-airlines": ["SIN"],
    "turkish-airlines": ["IST"],
}


def seed_alliances(session) -> dict:
    """Ensure the three major alliances exist in the DB."""
    from database.models.aviation import Alliance

    created = 0
    for name, info in KNOWN_ALLIANCES.items():
        existing = session.query(Alliance).filter_by(slug=info["slug"]).first()
        if not existing:
            session.add(
                Alliance(
                    name=name,
                    slug=info["slug"],
                    founded_year=info.get("founded_year"),
                    headquarters=info.get("headquarters"),
                )
            )
            created += 1
    session.flush()
    logger.info("[SYNC] Alliances seeded: %d new", created)
    return {"alliances_created": created}


def sync_airlines_to_metadata(
    session,
    heartbeat_fn: Callable[[str | dict], None] | None = None,
) -> dict:
    """Sync core airlines table into airline_metadata for intelligence layer."""
    from database.models.core import Airline
    from database.models.aviation import AirlineMetadata, Alliance

    now = datetime.now(timezone.utc)
    airlines = session.query(Airline).filter(Airline.is_active.is_(True)).all()
    existing_meta = {m.slug: m for m in session.query(AirlineMetadata).all()}
    alliances_by_slug = {a.slug: a.id for a in session.query(Alliance).all()}
    timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="sync_airlines_to_metadata", interval_s=25)
    created = 0
    updated = 0

    for idx, airline in enumerate(airlines):
        timer.pulse_if_needed(
            detail=f"sync airlines metadata {idx}/{len(airlines)}",
            processed=idx,
            total=len(airlines),
            current_substage="sync_airlines_to_metadata",
        )
        existing = existing_meta.get(airline.slug)

        alliance_name = AIRLINE_ALLIANCE_MAP.get(airline.slug)
        alliance_id = None
        if alliance_name:
            alliance_slug = KNOWN_ALLIANCES[alliance_name]["slug"]
            alliance_id = alliances_by_slug.get(alliance_slug)

        hubs = AIRLINE_HUBS.get(airline.slug, [])

        if existing:
            existing.airline_id = airline.id
            existing.airline_name = airline.name
            existing.country = existing.country or airline.country
            existing.canonical_country = existing.canonical_country or airline.country
            existing.normalized_name = existing.normalized_name or airline.slug
            if alliance_id and not existing.alliance_id:
                existing.alliance_id = alliance_id
            if alliance_name and not existing.alliance_code:
                existing.alliance_code = alliance_name
            if hubs and not existing.hub_airports:
                existing.hub_airports = hubs
            existing.last_seen_at = now
            updated += 1
        else:
            rec = AirlineMetadata(
                airline_id=airline.id,
                airline_name=airline.name,
                slug=airline.slug,
                country=airline.country,
                canonical_country=airline.country,
                normalized_name=airline.slug,
                alliance_id=alliance_id,
                alliance_code=alliance_name,
                airline_type="full_service",
                hub_airports=hubs,
                enrichment_confidence=0.6,
                normalization_confidence=0.7,
                metadata_quality_score=0.5,
                enrichment_status="synced",
                coverage_status="partial",
                source_confidence=0.8,
                last_enriched_at=now,
                last_seen_at=now,
            )
            session.add(rec)
            existing_meta[airline.slug] = rec
            created += 1

    session.flush()
    timer.pulse_if_needed(
        detail="sync airlines metadata complete",
        processed=len(airlines),
        total=len(airlines),
        force=True,
    )
    logger.info(
        "[SYNC] Airlines synced: %d created, %d updated (from %d active)", created, updated, len(airlines)
    )
    return {"airlines_created": created, "airlines_updated": updated, "total_active": len(airlines)}


@heartbeat_guard(interval_s=25)
def run_enrichment_pass(
    heartbeat_fn: Callable[[str], None] | None = None,
    max_seconds: int | None = None,
) -> dict:
    logger.info("[FUSION] Running enrichment pass...")
    from database.session import SessionLocal
    from database.models.aviation import AirlineMetadata, AirportMetadata, AirlineAirport

    session = SessionLocal()
    started = time.perf_counter()
    max_seconds = max_seconds or _MAX_ENRICH_SECONDS
    safe_mode = _env_enabled("FUSION_SAFE_MODE")
    safe_limit = _safe_int_env("FUSION_SAFE_INTEL_LIMIT", 4000)
    deep_match_disabled = _env_enabled("AVIATION_ENRICHMENT_DISABLE_DEEP_MATCH", "1")

    timer = TimedHeartbeat(heartbeat_fn, stage="fusion", substage="aviation_enrichment", interval_s=25)

    def _emit_hb(detail: str) -> None:
        if heartbeat_fn:
            heartbeat_fn(detail)

    def _timed_out() -> bool:
        elapsed = time.perf_counter() - started
        return elapsed >= max_seconds

    def _check_timeout(detail: str) -> dict | None:
        if not _timed_out():
            return None
        elapsed = int(time.perf_counter() - started)
        logger.warning("[FUSION_TIMEOUT] %s elapsed_s=%d limit_s=%d", detail, elapsed, max_seconds)
        _emit_hb(f"fusion timeout: {detail}")
        return {
            "degraded": True,
            "timeout": True,
            "error": f"enrichment timeout after {elapsed}s",
            "elapsed_s": elapsed,
            "safe_mode": safe_mode,
            "deep_match_disabled": deep_match_disabled,
        }

    try:
        timer.pulse_if_needed(detail="aviation enrichment bootstrap", force=True, processed=0, total=0)
        try:
            from database.runtime_schema import ensure_aviation_runtime_ready
            from database.session import engine

            bind = session.get_bind() or engine
            runtime = ensure_aviation_runtime_ready(bind)
            if not runtime.get("iata_code_ready"):
                logger.warning(
                    "[FUSION_DEGRADED] Aviation master degraded: airline_metadata.iata_code missing "
                    "(physical=%s stale_reflection=%s)",
                    runtime.get("physical_columns", [])[:8],
                    runtime.get("stale_reflection_detected"),
                )
                _emit_hb("fusion degraded: aviation master missing iata_code")
                seed = seed_alliances(session)
                session.commit()
                return {
                    **seed,
                    "degraded": True,
                    "error": "aviation master degraded — coluna airline_metadata.iata_code ausente",
                    "airline_airport_links": 0,
                    "airlines_metadata": 0,
                    "airports_metadata": 0,
                    "runtime_schema": runtime,
                }
        except Exception as exc:
            logger.warning("[AVIATION_RUNTIME] Preflight skipped: %s", exc)

        seed_alliances(session)
        sync_result = (
            {"skipped": True, "reason": "safe_mode_skip_sync"}
            if safe_mode
            else sync_airlines_to_metadata(session, heartbeat_fn)
        )
        session.commit()
        timer.pulse_if_needed(detail="aviation enrichment sync complete", processed=0, total=0)
        timeout_payload = _check_timeout("post-sync")
        if timeout_payload:
            return {**sync_result, **timeout_payload}

        spider_timeout = min(max_seconds, 60) if safe_mode else max_seconds
        airport_spider_result = run_spider(
            "airport_metadata",
            timeout_s=spider_timeout,
            heartbeat_fn=heartbeat_fn,
        )
        logger.info("[FUSION] Airport discovery result=%s", airport_spider_result)
        timer.pulse_if_needed(detail="airport discovery complete", processed=0, total=0)
        timeout_payload = _check_timeout("post-airport-spider")
        if timeout_payload:
            return {**sync_result, "airport_discovery": airport_spider_result, **timeout_payload}

        airline_query = session.query(AirlineMetadata).order_by(AirlineMetadata.id.asc())
        if safe_mode:
            airline_query = airline_query.limit(safe_limit)
            logger.warning("[FUSION_DEGRADED] FUSION_SAFE_MODE active, limiting airlines=%d", safe_limit)
        airlines = airline_query.all()
        airports = session.query(AirportMetadata.id, AirportMetadata.iata).all()
        airport_by_iata = {(iata or "").upper(): airport_id for airport_id, iata in airports if iata}
        airline_ids = [am.id for am in airlines]
        existing_pairs = (
            set(
                session.query(AirlineAirport.airline_metadata_id, AirlineAirport.airport_metadata_id)
                .filter(AirlineAirport.airline_metadata_id.in_(airline_ids))
                .all()
            )
            if airline_ids
            else set()
        )

        linked = 0
        total = len(airlines)
        for idx, am in enumerate(airlines):
            timer.pulse_if_needed(
                detail=f"aviation enrichment {idx}/{total}",
                processed=idx,
                total=total,
                current_substage="airline_airport_linking",
            )
            timeout_payload = _check_timeout(f"linking-loop idx={idx}")
            if timeout_payload:
                session.commit()
                return {
                    **sync_result,
                    "airline_airport_links": linked,
                    "airlines_metadata": total,
                    "airports_metadata": len(airports),
                    "partial": True,
                    **timeout_payload,
                }
            for hub_code in am.hub_airports or []:
                code = (hub_code or "").upper().strip()
                if not code:
                    continue
                airport_id = airport_by_iata.get(code)
                if not airport_id:
                    continue
                pair = (am.id, airport_id)
                if pair in existing_pairs:
                    continue
                existing_pairs.add(pair)
                session.add(
                    AirlineAirport(
                        airline_metadata_id=am.id,
                        airport_metadata_id=airport_id,
                        relationship_type="hub",
                    )
                )
                linked += 1
            if deep_match_disabled and safe_mode:
                # Explicit short-circuit in safe mode to avoid expensive expansion logic.
                continue

        session.commit()
        elapsed = int(time.perf_counter() - started)
        throughput = round((total / max(elapsed, 1)), 2)
        logger.info(
            "[FUSION] Linked relationships linked=%d airlines=%d airports=%d elapsed_s=%d throughput=%s/s safe_mode=%s",
            linked,
            total,
            len(airports),
            elapsed,
            throughput,
            safe_mode,
        )
        timer.pulse_if_needed(
            detail="aviation enrichment complete",
            processed=total,
            total=total,
            current_substage="done",
            force=True,
        )
        return {
            **sync_result,
            "safe_mode": safe_mode,
            "deep_match_disabled": deep_match_disabled,
            "airline_airport_links": linked,
            "airlines_metadata": total,
            "airports_metadata": len(airports),
            "elapsed_s": elapsed,
            "throughput_airlines_s": throughput,
            "airport_discovery": airport_spider_result,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_coverage_validation() -> dict:
    logger.info("Running coverage validation...")
    from database.session import SessionLocal
    from aviation.coverage.engine import CoverageAuditEngine

    session = SessionLocal()
    try:
        engine = CoverageAuditEngine(session)
        report = engine.generate_report()
        logger.info(
            "Coverage: airlines=%d airports=%d score=%.1f%%",
            report["total_airlines"],
            report["total_airports"],
            report["coverage_score"],
        )
        return report
    finally:
        session.close()


def persist_coverage_report(report: dict) -> None:
    logger.info("Persisting coverage report...")
    from database.session import SessionLocal
    from database.models.aviation import AviationCoverageReport

    session = SessionLocal()
    try:
        rec = AviationCoverageReport(
            total_airlines=report.get("total_airlines", 0),
            total_airports=report.get("total_airports", 0),
            total_alliances=report.get("total_alliances", 0),
            missing_iata=report.get("missing_iata", 0),
            missing_icao=report.get("missing_icao", 0),
            missing_country=report.get("missing_country", 0),
            missing_coordinates=report.get("missing_coordinates", 0),
            duplicate_entities=report.get("duplicate_entities", 0),
            orphan_airports=report.get("orphan_airports", 0),
            orphan_airlines=report.get("orphan_airlines", 0),
            normalization_failures=report.get("normalization_failures", 0),
            coverage_score=report.get("coverage_score", 0.0),
            metadata_completeness=report.get("metadata_completeness", 0.0),
            enrichment_score=report.get("enrichment_score", 0.0),
            graph_readiness=report.get("graph_readiness", 0.0),
            report_data=report,
        )
        session.add(rec)
        session.commit()
        logger.info("Coverage report persisted: id=%s", rec.id)
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Aviation metadata bootstrap pipeline")
    parser.add_argument("--spiders", action="store_true", help="Run spiders only")
    parser.add_argument("--enrich", action="store_true", help="Run enrichment only")
    parser.add_argument("--validate", action="store_true", help="Run coverage validation only")
    parser.add_argument("--report", action="store_true", help="Generate and persist coverage report")
    args = parser.parse_args()

    run_all = not any([args.spiders, args.enrich, args.validate, args.report])

    started = time.perf_counter()
    results = {}

    if run_all or args.spiders:
        results["spiders"] = run_spiders()

    if run_all or args.enrich:
        results["enrichment"] = run_enrichment_pass()

    if run_all or args.validate or args.report:
        report = run_coverage_validation()
        results["coverage"] = report
        if run_all or args.report:
            persist_coverage_report(report)

    elapsed = round(time.perf_counter() - started, 2)
    logger.info("Bootstrap complete in %.2fs", elapsed)
    results["total_elapsed_s"] = elapsed
    return results


if __name__ == "__main__":
    main()
