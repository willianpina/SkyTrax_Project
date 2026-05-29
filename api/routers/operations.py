"""Operational Intelligence Refresh API endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.operations_dispatch import accept_and_dispatch_refresh, get_redis_and_queue, queue_depth
from database.models.operations import OperationalRefreshRun
from database.session import get_session
from app.response_contract import fallback_operational_response, safe_json_response
from worker.orchestration.refresh_pipeline import clear_status, get_live_status, get_live_status_fast

_STATUS_BUDGET_S = 0.28

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operations", tags=["operations"])

_DISPATCH_TIMEOUT_S = 5.0


async def _dispatch_in_thread(**kwargs) -> dict:
    return await asyncio.wait_for(
        asyncio.to_thread(accept_and_dispatch_refresh, **kwargs),
        timeout=_DISPATCH_TIMEOUT_S,
    )


def _json_from_dispatch(result: dict) -> JSONResponse:
    return JSONResponse(status_code=result["http_status"], content=result["body"])


@router.post("/refresh/metadata", status_code=202)
async def trigger_metadata_backfill():
    """Backfill review_intelligence from existing reviews (async queue only)."""
    from rq import Retry
    from worker.jobs import run_metadata_backfill

    operation_id = str(uuid4())[:12]
    try:
        conn, queue = await asyncio.wait_for(
            asyncio.to_thread(get_redis_and_queue),
            timeout=_DISPATCH_TIMEOUT_S,
        )
        job = await asyncio.to_thread(
            queue.enqueue,
            run_metadata_backfill,
            kwargs={"batch_size": 1000, "max_batches": 100},
            job_timeout=7200,
            result_ttl=86400,
            retry=Retry(max=1, interval=[30]),
        )
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "queued": True,
                "operation_id": operation_id,
                "job_id": job.id,
                "queue": queue.name,
            },
        )
    except Exception as exc:
        logger.exception("[OPS] metadata backfill enqueue failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "dispatch_failed", "queued": False, "detail": str(exc)[:300]},
        )


@router.post("/refresh", status_code=202)
async def trigger_refresh(
    force: bool = Query(False, description="Release stalled state and enqueue fresh run"),
):
    """Accept full operational refresh — enqueue worker, return immediately (202)."""
    try:
        result = await _dispatch_in_thread(
            triggered_by="manual",
            pipeline_type="full",
            force=force,
        )
        return _json_from_dispatch(result)
    except asyncio.TimeoutError:
        logger.error("[ASYNC_REFRESH] dispatch thread timed out")
        return JSONResponse(
            status_code=503,
            content={"status": "dispatch_failed", "queued": False, "detail": "Dispatch timed out."},
        )


@router.post("/refresh/aviation", status_code=202)
async def trigger_aviation_sync():
    """Accept aviation-only sync (async queue — non-blocking)."""
    try:
        result = await _dispatch_in_thread(
            triggered_by="aviation_sync",
            pipeline_type="aviation",
        )
        return _json_from_dispatch(result)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=503,
            content={"status": "dispatch_failed", "queued": False, "detail": "Dispatch timed out."},
        )


@router.post("/refresh/aviation-master", status_code=202)
async def trigger_aviation_master_sync():
    """Accept canonical aviation master sync via queue (no inline spider)."""
    operation_id = str(uuid4())[:12]

    def _enqueue():
        from worker.jobs import run_aviation_bootstrap

        conn, queue = get_redis_and_queue()
        job = queue.enqueue(run_aviation_bootstrap, job_timeout=7200, result_ttl=86400)
        return {"job_id": job.id, "queue": queue.name}

    try:
        rq = await asyncio.wait_for(asyncio.to_thread(_enqueue), timeout=_DISPATCH_TIMEOUT_S)
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "queued": True,
                "running": True,
                "operation_id": operation_id,
                "pipeline_type": "aviation_master",
                **rq,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "dispatch_failed", "queued": False, "detail": str(exc)[:300]},
        )


@router.post("/refresh/airline/{slug}", status_code=202)
async def trigger_airline_refresh(slug: str):
    try:
        result = await _dispatch_in_thread(
            airline_slug=slug,
            triggered_by=f"airline:{slug}",
            pipeline_type="full",
        )
        return _json_from_dispatch(result)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=503,
            content={"status": "dispatch_failed", "queued": False, "detail": "Dispatch timed out."},
        )


@router.get("/status")
async def current_status(
    full: bool = Query(False, description="Attach DB integrity reconciliation (slower)"),
):
    """Redis-first pipeline status; optional full integrity via ?full=1."""
    if not full:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(get_live_status_fast),
                timeout=_STATUS_BUDGET_S,
            )
        except asyncio.TimeoutError:
            logger.warning("[ENDPOINT_TIMEOUT] /operations/status")
            return fallback_operational_response(
                path="/operations/status",
                reason="status_timeout",
                extra={"running": False, "stage": "idle", "progress": 0},
            )
        except Exception as exc:
            logger.warning("[SAFE_RESPONSE] status fast failed: %s", exc)
            return fallback_operational_response(path="/operations/status", reason=str(exc)[:120])

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(lambda: get_live_status(include_integrity=True)),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        logger.warning("[ENDPOINT_TIMEOUT] /operations/status?full=1 — falling back to fast")
        return get_live_status_fast()
    except Exception as exc:
        return safe_json_response(
            {"running": False, "stage": "idle", "error": str(exc)[:200]},
            path="/operations/status",
        )


@router.get("/live")
async def live_status(full: bool = Query(False)):
    return await current_status(full=full)


@router.post("/reconcile")
async def reconcile_pipeline():
    """Force pipeline watchdog reconciliation (orphan/zombie cleanup)."""
    try:
        from worker.orchestration.pipeline_watchdog import reconcile_pipeline_state

        result = await asyncio.wait_for(
            asyncio.to_thread(reconcile_pipeline_state, persist=True),
            timeout=5.0,
        )
        return result
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=503,
            content={"action": "skipped", "detail": "reconcile timed out"},
        )


@router.post("/reset")
def reset_pipeline_status():
    """Force-clear stale pipeline status. Safe to call when pipeline is stuck."""
    from app.runtime_state import runtime_state_reset
    from worker.orchestration.pipeline_watchdog import release_stalled_state

    live = get_live_status_fast()
    release_stalled_state(operation_id=live.get("operation_id"))
    clear_status()
    runtime_state_reset(operation_id="", clear_degraded_history=False)
    logger.info("[OPS] Pipeline status force-reset by user")
    return {
        "status": "reset",
        "stage": "idle",
        "running": False,
        "previous_operation_id": live.get("operation_id"),
    }


@router.get("/history")
def refresh_history(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    rows = (
        session.query(OperationalRefreshRun)
        .order_by(OperationalRefreshRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "operation_id": r.operation_id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_ms": r.duration_ms,
            "status": r.status,
            "reviews_processed": r.reviews_processed,
            "anomalies_generated": r.anomalies_generated,
            "forecasts_generated": r.forecasts_generated,
            "semantic_updates": r.semantic_updates,
            "error_count": r.error_count,
            "triggered_by": r.triggered_by,
        }
        for r in rows
    ]


@router.get("/jobs")
def list_jobs():
    try:
        _, queue = get_redis_and_queue()
        jobs = queue.jobs[:20]
        return [
            {
                "id": j.id,
                "func_name": j.func_name,
                "status": j.get_status(),
                "enqueued_at": j.enqueued_at.isoformat() if j.enqueued_at else None,
            }
            for j in jobs
        ]
    except Exception:
        return []


@router.get("/metrics")
def operations_metrics(session: Session = Depends(get_session)):
    from sqlalchemy import func

    total = session.query(func.count(OperationalRefreshRun.id)).scalar() or 0
    avg_duration = session.query(func.avg(OperationalRefreshRun.duration_ms)).scalar() or 0
    total_reviews = session.query(func.sum(OperationalRefreshRun.reviews_processed)).scalar() or 0
    total_errors = session.query(func.sum(OperationalRefreshRun.error_count)).scalar() or 0
    return {
        "total_runs": total,
        "avg_duration_ms": round(float(avg_duration), 0),
        "total_reviews_processed": total_reviews,
        "total_errors": total_errors,
        "refresh_queue_depth": queue_depth(),
    }


@router.get("/health")
def operations_health():
    """Diagnostic endpoint for operational pipeline health."""
    result = {
        "redis_connected": False,
        "queue_name": "default",
        "queue_count": 0,
        "workers_count": 0,
        "workers_names": [],
        "pipeline_running": False,
        "last_status": {},
        "failed_jobs": 0,
        "active_operation_id": None,
        "lifecycle_state": None,
    }

    try:
        from rq import Worker

        conn, queue = get_redis_and_queue()
        result["redis_connected"] = True
        result["queue_count"] = queue.count
        result["failed_jobs"] = queue.failed_job_registry.count

        workers = Worker.all(connection=conn)
        result["workers_count"] = len(workers)
        result["workers_names"] = [w.name for w in workers]
    except Exception as exc:
        result["redis_error"] = str(exc)

    try:
        live = get_live_status_fast()
        result["pipeline_running"] = live.get("running", False)
        result["last_status"] = live
        result["active_operation_id"] = live.get("operation_id")
        result["lifecycle_state"] = live.get("pipeline_status") or live.get("stage")
    except Exception:
        pass

    try:
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        active = OperationLifecycleManager().get_active_operation()
        if active:
            result["active_operation_id"] = active.get("operation_id")
            result["lifecycle_state"] = active.get("lifecycle_state")
    except Exception:
        pass

    return result


@router.get("/health/pipeline/runtime")
def pipeline_health_diagnostics():
    """Runtime diagnostics: live Redis status, heartbeat, KPIs, and worker state."""
    diag: dict[str, Any] = {
        "status": "unknown",
        "active_stage": None,
        "last_heartbeat_s": None,
        "last_successful_stage": None,
        "soft_failures": [],
        "worker_alive": False,
        "queue_depth": queue_depth(),
        "pipeline_duration_s": None,
        "operation_id": None,
        "lifecycle_state": None,
        "kpis": {},
        "stage_timings": {},
        "completed_stages": [],
        "failed_stages": [],
    }

    try:
        live = get_live_status_fast()
        diag["status"] = live.get("pipeline_status") or live.get("stage", "idle")
        diag["active_stage"] = live.get("stage")
        diag["operation_id"] = live.get("operation_id")
        diag["lifecycle_state"] = live.get("pipeline_status") or live.get("stage")
        diag["completed_stages"] = live.get("completed_stages", [])
        diag["failed_stages"] = live.get("failed_stages", [])
        diag["soft_failures"] = live.get("failed_stages", [])
        diag["kpis"] = live.get("kpis", {})
        diag["stage_timings"] = live.get("stage_timings", {})

        hb = live.get("heartbeat") or {}
        diag["last_successful_stage"] = hb.get("last_successful_stage", "")
        diag["heartbeat_seq"] = hb.get("heartbeat_seq", 0)

        updated_at = live.get("updated_at")
        if updated_at:
            from datetime import datetime, timezone as tz

            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                diag["last_heartbeat_s"] = int((datetime.now(tz.utc) - dt).total_seconds())
            except (ValueError, TypeError):
                pass

        started_at = live.get("started_at")
        if started_at:
            from datetime import datetime, timezone as tz

            try:
                dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                diag["pipeline_duration_s"] = int((datetime.now(tz.utc) - dt).total_seconds())
            except (ValueError, TypeError):
                pass

    except Exception as exc:
        diag["error"] = str(exc)

    try:
        from rq import Worker

        conn, queue = get_redis_and_queue()
        diag["queue_depth"] = queue.count
        workers = Worker.all(connection=conn)
        diag["worker_alive"] = len(workers) > 0
        diag["workers"] = [{"name": w.name, "state": w.get_state()} for w in workers]
    except Exception:
        pass

    return diag


@router.get("/health/ingestion")
def ingestion_health_diagnostics():
    """Live ingestion diagnostics: current crawl state, saturation, heartbeat age."""
    diag: dict[str, Any] = {
        "active_airline": None,
        "current_page": 0,
        "elapsed_s": 0,
        "insert_rate": 0,
        "reviews_added": 0,
        "duplicates": 0,
        "saturation_status": "none",
        "heartbeat_age_s": None,
        "worker_alive": False,
        "pages_since_last_insert": 0,
        "stalled": False,
        "saturated": False,
        "loop_suspected": False,
    }

    try:
        live = get_live_status_fast()
        ct = live.get("crawl_telemetry") or {}
        diag["active_airline"] = ct.get("current_airline")
        diag["current_page"] = ct.get("pages_processed", 0)
        diag["elapsed_s"] = ct.get("elapsed_seconds", 0)
        diag["reviews_added"] = ct.get("reviews_added", 0)
        diag["duplicates"] = ct.get("duplicates_skipped", 0)
        diag["insert_rate"] = ct.get("reviews_per_second", 0)
        diag["stalled"] = ct.get("stalled", False)
        diag["saturated"] = ct.get("saturated", False)
        diag["pages_since_last_insert"] = ct.get("pages_since_last_insert", 0)
        diag["airlines_queued"] = ct.get("airlines_queued", 0)

        if diag["saturated"]:
            diag["saturation_status"] = "saturated"
        elif diag["pages_since_last_insert"] > 10:
            diag["saturation_status"] = "drying"
        elif diag["stalled"]:
            diag["saturation_status"] = "stalled"

        if diag["current_page"] > 20 and diag["reviews_added"] == 0:
            diag["loop_suspected"] = True

        updated_at = live.get("updated_at")
        if updated_at:
            from datetime import datetime, timezone as tz

            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                diag["heartbeat_age_s"] = int((datetime.now(tz.utc) - dt).total_seconds())
            except (ValueError, TypeError):
                pass

        diag["pipeline_stage"] = live.get("stage")
        diag["pipeline_status"] = live.get("pipeline_status")
        diag["operation_id"] = live.get("operation_id")

    except Exception as exc:
        diag["error"] = str(exc)

    try:
        from rq import Worker

        conn, _ = get_redis_and_queue()
        workers = Worker.all(connection=conn)
        diag["worker_alive"] = len(workers) > 0
    except Exception:
        pass

    return diag


@router.get("/enrichment/audit")
def enrichment_audit(session: Session = Depends(get_session)):
    """Comprehensive enrichment diagnostics: coverage, linking, source validation."""
    from sqlalchemy import func
    from database.models.core import Airline
    from database.models.aviation import (
        AirlineMetadata,
        AirportMetadata,
        Alliance,
        AirlineAirport,
    )

    core_total = session.query(func.count(Airline.id)).scalar() or 0
    core_active = session.query(func.count(Airline.id)).filter(Airline.is_active.is_(True)).scalar() or 0
    core_with_country = (
        session.query(func.count(Airline.id))
        .filter(Airline.country.isnot(None), Airline.country != "")
        .scalar()
        or 0
    )

    meta_total = session.query(func.count(AirlineMetadata.id)).scalar() or 0
    meta_linked = (
        session.query(func.count(AirlineMetadata.id)).filter(AirlineMetadata.airline_id.isnot(None)).scalar()
        or 0
    )
    meta_with_country = (
        session.query(func.count(AirlineMetadata.id))
        .filter(AirlineMetadata.country.isnot(None), AirlineMetadata.country != "")
        .scalar()
        or 0
    )
    meta_with_iata = (
        session.query(func.count(AirlineMetadata.id)).filter(AirlineMetadata.iata_code.isnot(None)).scalar()
        or 0
    )
    meta_with_icao = (
        session.query(func.count(AirlineMetadata.id)).filter(AirlineMetadata.icao_code.isnot(None)).scalar()
        or 0
    )
    meta_with_alliance = (
        session.query(func.count(AirlineMetadata.id)).filter(AirlineMetadata.alliance_id.isnot(None)).scalar()
        or 0
    )
    meta_with_hubs = (
        session.query(func.count(AirlineMetadata.id)).filter(AirlineMetadata.primary_hub.isnot(None)).scalar()
        or 0
    )

    airports_total = session.query(func.count(AirportMetadata.id)).scalar() or 0
    airports_with_coords = (
        session.query(func.count(AirportMetadata.id)).filter(AirportMetadata.latitude.isnot(None)).scalar()
        or 0
    )
    hubs_total = (
        session.query(func.count(AirportMetadata.id)).filter(AirportMetadata.hub_level.isnot(None)).scalar()
        or 0
    )
    alliances_total = session.query(func.count(Alliance.id)).scalar() or 0
    links_total = session.query(func.count(AirlineAirport.id)).scalar() or 0

    core_slugs = {a.slug for a in session.query(Airline.slug).filter(Airline.is_active.is_(True)).all()}
    meta_slugs = {m.slug for m in session.query(AirlineMetadata.slug).all()}
    unlinked_core = sorted(core_slugs - meta_slugs)[:50]
    orphan_meta = sorted(meta_slugs - core_slugs)[:50]

    last_enriched = session.query(func.max(AirlineMetadata.last_enriched_at)).scalar()

    def pct(n: int, d: int) -> float:
        return round(n / d * 100, 1) if d else 0.0

    coverage_score = round(
        sum(
            [
                pct(meta_with_country, meta_total) * 0.25,
                pct(meta_with_iata, meta_total) * 0.20,
                pct(meta_with_icao, meta_total) * 0.15,
                pct(meta_with_alliance, meta_total) * 0.15,
                pct(airports_total, max(airports_total, 1)) * 0.10,
                pct(meta_linked, meta_total) * 0.15,
            ]
        ),
        1,
    )

    return {
        "core_airlines_total": core_total,
        "core_airlines_active": core_active,
        "core_airlines_with_country": core_with_country,
        "airline_metadata_total": meta_total,
        "airline_metadata_linked": meta_linked,
        "airline_metadata_unlinked": meta_total - meta_linked,
        "airlines_with_country": meta_with_country,
        "airlines_with_iata": meta_with_iata,
        "airlines_with_icao": meta_with_icao,
        "airlines_with_alliance": meta_with_alliance,
        "airlines_with_hubs": meta_with_hubs,
        "airports_total": airports_total,
        "airports_with_coordinates": airports_with_coords,
        "hubs_total": hubs_total,
        "alliances_total": alliances_total,
        "airline_airport_links": links_total,
        "last_enrichment_run": last_enriched.isoformat() if last_enriched else None,
        "coverage_percentages": {
            "country": pct(meta_with_country, meta_total),
            "iata": pct(meta_with_iata, meta_total),
            "icao": pct(meta_with_icao, meta_total),
            "alliance": pct(meta_with_alliance, meta_total),
            "hubs": pct(meta_with_hubs, meta_total),
            "linked_to_core": pct(meta_linked, meta_total),
            "airports_geocoded": pct(airports_with_coords, airports_total),
        },
        "coverage_score": coverage_score,
        "linking_diagnostics": {
            "core_without_metadata": len(unlinked_core),
            "metadata_without_core": len(orphan_meta),
            "unlinked_core_slugs": unlinked_core,
            "orphan_metadata_slugs": orphan_meta[:20],
        },
        "root_cause_indicators": {
            "metadata_table_empty": meta_total == 0,
            "enrichment_never_ran": last_enriched is None,
            "linking_gap": len(unlinked_core) > 0,
            "country_source_missing": core_with_country == 0 and meta_with_country == 0,
            "airports_not_loaded": airports_total == 0,
            "alliances_not_seeded": alliances_total == 0,
        },
    }


@router.get("/enrichment/linking")
def enrichment_linking_diagnostics(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    """Detailed airline linking diagnostics: matched, unresolved, candidates."""
    from database.models.core import Airline
    from database.models.aviation import AirlineMetadata
    from aviation.master_data.normalize import normalize_airline_slug

    core_airlines = session.query(Airline).filter(Airline.is_active.is_(True)).all()
    meta_by_slug = {m.slug: m for m in session.query(AirlineMetadata).all()}
    meta_by_iata = {}
    for m in meta_by_slug.values():
        if m.iata_code:
            meta_by_iata[m.iata_code.upper()] = m

    matched = []
    unresolved = []

    for airline in core_airlines[:limit]:
        meta = meta_by_slug.get(airline.slug)
        match_method = None

        if meta:
            match_method = "slug"
        else:
            norm = normalize_airline_slug(airline.name)
            meta = meta_by_slug.get(norm)
            if meta:
                match_method = "normalized_name"

        if meta:
            matched.append(
                {
                    "core_slug": airline.slug,
                    "core_name": airline.name,
                    "meta_slug": meta.slug,
                    "match_method": match_method,
                    "country": meta.country,
                    "iata": meta.iata_code,
                    "alliance": meta.alliance_rel.name if meta.alliance_rel else None,
                }
            )
        else:
            candidates = []
            name_lower = airline.name.lower()
            for ms, m in meta_by_slug.items():
                if name_lower in m.airline_name.lower() or m.airline_name.lower() in name_lower:
                    candidates.append({"meta_slug": ms, "meta_name": m.airline_name, "iata": m.iata_code})
            unresolved.append(
                {
                    "core_slug": airline.slug,
                    "core_name": airline.name,
                    "core_country": airline.country,
                    "candidates": candidates[:3],
                }
            )

    return {
        "total_core_airlines": len(core_airlines),
        "matched": len(matched),
        "unresolved": len(unresolved),
        "match_details": matched[:30],
        "unresolved_details": unresolved[:30],
    }


@router.get("/enrichment/sources")
def enrichment_source_validation():
    """Validate that external data sources are accessible and returning data."""
    results = {}

    try:
        from aviation.master_data.sources import fetch_openflights_airlines

        airlines = fetch_openflights_airlines(timeout=15.0)
        active = [a for a in airlines if a.active]
        with_country = [a for a in active if a.country]
        with_iata = [a for a in active if a.iata]
        results["openflights_airlines"] = {
            "status": "ok",
            "total_parsed": len(airlines),
            "active": len(active),
            "with_country": len(with_country),
            "with_iata": len(with_iata),
            "sample": [{"name": a.name, "iata": a.iata, "country": a.country} for a in active[:5]],
        }
    except Exception as e:
        results["openflights_airlines"] = {"status": "error", "error": str(e)}

    try:
        from aviation.master_data.sources import fetch_openflights_airports

        airports = fetch_openflights_airports(timeout=15.0)
        with_iata = [a for a in airports if a.iata]
        with_coords = [a for a in airports if a.latitude is not None]
        results["openflights_airports"] = {
            "status": "ok",
            "total_parsed": len(airports),
            "with_iata": len(with_iata),
            "with_coordinates": len(with_coords),
            "sample": [
                {"name": a.name, "iata": a.iata, "country": a.country, "city": a.city} for a in with_iata[:5]
            ],
        }
    except Exception as e:
        results["openflights_airports"] = {"status": "error", "error": str(e)}

    try:
        from aviation.master_data.sources import fetch_ourairports

        oa = fetch_ourairports(timeout=30.0)
        results["ourairports"] = {
            "status": "ok",
            "total_parsed": len(oa),
            "with_iata": sum(1 for a in oa if a.iata_code),
            "sample": [
                {"name": a.name, "iata": a.iata_code, "country": a.iso_country, "type": a.type}
                for a in oa[:5]
            ],
        }
    except Exception as e:
        results["ourairports"] = {"status": "error", "error": str(e)}

    results["wikidata"] = {"status": "not_implemented", "note": "Wikidata SPARQL resolver not yet integrated"}

    return results


@router.get("/debug")
def operations_debug():
    """Deep diagnostic: test actual enqueue + worker detection."""
    diag = {
        "redis_connected": False,
        "redis_ping": False,
        "queue_name": "default",
        "queue_count": 0,
        "worker_detected": False,
        "worker_queues": [],
        "enqueue_test": False,
        "enqueue_error": None,
    }

    try:
        from rq import Worker

        conn, queue = get_redis_and_queue()
        diag["redis_connected"] = True
        diag["redis_ping"] = conn.ping()
        diag["queue_count"] = queue.count

        workers = Worker.all(connection=conn)
        diag["worker_detected"] = len(workers) > 0
        diag["worker_queues"] = []
        for w in workers:
            diag["worker_queues"].append(
                {
                    "name": w.name,
                    "state": w.get_state(),
                    "queues": [q.name for q in w.queues],
                }
            )
    except Exception as exc:
        diag["enqueue_error"] = f"Redis/Queue setup: {exc}"
        return diag

    try:
        from worker.jobs import run_operational_refresh

        test_job = queue.enqueue(
            run_operational_refresh,
            kwargs={
                "operation_id": "__diag_test__",
                "triggered_by": "diagnostic",
            },
            job_timeout=5,
            result_ttl=60,
        )
        diag["enqueue_test"] = True
        diag["test_job_id"] = test_job.id
        test_job.cancel()
    except Exception as exc:
        diag["enqueue_test"] = False
        diag["enqueue_error"] = str(exc)

    return diag
