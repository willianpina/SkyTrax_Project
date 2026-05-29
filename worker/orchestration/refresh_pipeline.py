"""Aviation Intelligence Fusion Pipeline — orchestrates the full intelligence cycle.

Stages:
  1. discovery        -- discover new airline review URLs
  2. crawl            -- incremental review ingestion with saturation detection
  3. metadata         -- extract structured intelligence from review text
  4. semantic         -- NLP enrichment + semantic clustering
  5. knowledge_graph  -- build/update aviation knowledge graph
  6. forecasting      -- regenerate trend forecasts
  7. anomalies        -- detect operational anomalies
  8. insights         -- generate executive intelligence
  9. fusion           -- strategic cross-correlation signals
 10. snapshots        -- persist metric snapshots
"""

from __future__ import annotations

import inspect
import json
import os
import time
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from redis import Redis

from app.config import get_settings
from app.observability import record_worker_metric
from app.timezone import format_operational_time, now_utc, operational_timestamp
from database.session import SessionLocal

logger = logging.getLogger(__name__)


class _SafeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, "__str__"):
            return str(o)
        return super().default(o)


STAGES = [
    "discovery",
    "crawl",
    "metadata",
    "semantic",
    "knowledge_graph",
    "forecasting",
    "anomalies",
    "insights",
    "aviation_master",
    "fusion",
    "snapshots",
]

AVIATION_STAGES = [
    "aviation_master",
    "airport_discovery",
    "aviation_metadata",
    "hub_intelligence",
]

REDIS_STATUS_KEY = "skytrax:ops:refresh:status"
REDIS_LOCK_KEY = "skytrax:ops:refresh:lock"

_STATUS_TTL = 14400

_TERMINAL_STAGES = frozenset(
    {
        "idle",
        "completed",
        "completed_degraded",
        "failed",
    }
)

_RUNNING_STAGES = frozenset(
    {
        "running",
        "running_degraded",
        "starting",
    }
)

# ── KPI accumulation map: stage → keys that carry KPI values ─────────
_KPI_EXTRACTION_MAP: dict[str, list[tuple[str, str]]] = {
    "crawl": [("total_reviews_in_db", "reviews"), ("total_airlines_in_db", "airlines")],
    "metadata": [("metadata_total", "metadata"), ("reviews_analyzed", "metadata_delta")],
    "semantic": [("clusters_created", "clusters"), ("enriched", "enriched")],
    "knowledge_graph": [("total_nodes", "graph_nodes"), ("total_edges", "graph_edges")],
    "forecasting": [("forecasts_persisted", "forecasts")],
    "anomalies": [("anomalies_created", "anomalies")],
    "insights": [("insights_created", "insights")],
    "fusion": [("signals_total", "signals"), ("signals_generated", "signals_delta")],
    "aviation_master": [
        ("airlines_total", "aviation_metadata_total"),
        ("airlines_linked_total", "aviation_linked_total"),
        ("airlines_processed_this_run", "aviation_processed_this_run"),
    ],
}

# Stages skipped when upstream dependency contract fails (explicit degraded reason).
_DEPENDENCY_SKIP_STAGES = frozenset(
    {
        "knowledge_graph",
        "fusion",
        "anomalies",
        "insights",
        "snapshots",
    }
)


_REDIS_SOCKET_TIMEOUT_S = 2.0


def _redis() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=_REDIS_SOCKET_TIMEOUT_S,
        socket_timeout=_REDIS_SOCKET_TIMEOUT_S,
    )


def _sanitize_stage_results(raw: dict) -> dict:
    """Flatten stage results to shallow dicts of scalars for safe Redis serialization."""
    clean: dict[str, Any] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            clean[key] = {"_raw": str(val)[:200]}
            continue
        stage_clean: dict[str, Any] = {}
        for k, v in val.items():
            if isinstance(v, (int, float, bool)):
                stage_clean[k] = v
            elif isinstance(v, str):
                stage_clean[k] = v[:200]
            elif isinstance(v, dict):
                for sk, sv in v.items():
                    if isinstance(sv, (int, float, bool, str)):
                        stage_clean[f"{k}.{sk}"] = sv
            elif isinstance(v, list):
                stage_clean[k] = len(v)
            else:
                stage_clean[k] = str(v)[:200]
        clean[key] = stage_clean
    return clean


_STALE_SOFT_S = 90
_STALE_DEFAULT_S = 180
_STALE_FINAL_STAGE_S = 420
_HEARTBEAT_FRESH_S = 45
_FINAL_PIPELINE_STAGES = frozenset({"fusion", "snapshots"})
_STAGE_STALE_THRESHOLDS = {
    "fusion": int(os.getenv("FUSION_STALE_THRESHOLD_S", "360")),
    "aviation_master": int(os.getenv("AVIATION_MASTER_STALE_THRESHOLD_S", "240")),
}
_SLOW_OK_STATUSES = frozenset(
    {
        "running",
        "running_degraded",
        "running_slow",
        "busy_without_heartbeat",
        "finalizing",
        "persisting",
    }
)
_WATCHDOG_NO_PROGRESS_S = int(os.getenv("PIPELINE_NO_PROGRESS_THRESHOLD_S", "240"))


def _set_status(r: Redis, op_id: str, stage: str, progress: int, **extra: Any) -> None:
    if "stage_results" in extra:
        extra["stage_results"] = _sanitize_stage_results(extra["stage_results"])
    is_terminal = stage in _TERMINAL_STAGES
    payload = {
        "operation_id": op_id,
        "running": not is_terminal,
        "stage": stage,
        "progress": max(0, min(progress, 100)),
        "updated_at": operational_timestamp(),
        **extra,
    }
    payload.setdefault("active_layers", [])
    payload.setdefault("pipeline_type", "full")
    payload.setdefault("started_at", payload["updated_at"])

    # ── Snapshot consistency: merge accumulated KPIs ──────────────────
    # Never let a new write clobber a valid KPI with 0 / None.
    if "kpis" in extra:
        try:
            prev_raw = r.get(REDIS_STATUS_KEY)
            if prev_raw:
                prev_kpis = json.loads(prev_raw).get("kpis", {})
                merged = {**prev_kpis}
                for k, v in extra["kpis"].items():
                    if isinstance(v, (int, float)) and v > 0:
                        merged[k] = v
                    elif k not in merged:
                        merged[k] = v
                payload["kpis"] = merged
                record_worker_metric("skytrax_snapshot_merge_protected", 1.0)
        except Exception:
            pass

    r.set(REDIS_STATUS_KEY, json.dumps(payload, cls=_SafeEncoder), ex=_STATUS_TTL)
    _sync_lifecycle(op_id, stage, extra.get("pipeline_status"))
    logger.info("[PIPELINE] status_set stage=%s progress=%d op=%s", stage, progress, op_id)


def set_initial_status(op_id: str, triggered_by: str = "manual") -> None:
    """Write queued status to Redis BEFORE the RQ worker picks up the job."""
    try:
        from worker.orchestration.operation_lifecycle import OperationLifecycleManager

        OperationLifecycleManager(_redis()).transition(op_id, "queued")
        r = _redis()
        _set_status(
            r,
            op_id,
            "queued",
            0,
            triggered_by=triggered_by,
            events=[],
            pipeline_status="queued",
        )
    except Exception as exc:
        logger.warning("set_initial_status_failed: %s", exc)


def _sync_lifecycle(op_id: str, stage: str, pipeline_status: str | None = None) -> None:
    if not op_id:
        return
    try:
        from worker.orchestration.operation_lifecycle import (
            OperationLifecycleManager,
            lifecycle_from_stage,
        )

        state = lifecycle_from_stage(stage, pipeline_status)
        if state:
            OperationLifecycleManager(_redis()).transition(op_id, state)
    except Exception:
        pass


def get_live_status(*, include_integrity: bool = True) -> dict[str, Any]:
    try:
        r = _redis()
        raw = r.get(REDIS_STATUS_KEY)
        if raw:
            data = json.loads(raw)
            data.setdefault(
                "running", data.get("stage") not in _TERMINAL_STAGES and data.get("stage") is not None
            )
            data = _detect_stale(r, data)
            if include_integrity:
                try:
                    from worker.orchestration.operational_reconciliation import reconcile_live_status_payload

                    data = reconcile_live_status_payload(data)
                except Exception as exc:
                    logger.warning("[UI_STATE] live status reconcile skipped: %s", exc)
                try:
                    from analytics.pipeline_integrity import (
                        build_authoritative_integrity,
                        load_authoritative_integrity_snapshot,
                        reconcile_integrity_metrics,
                    )
                    from database.session import SessionLocal

                    kpis = data.get("kpis") or {}
                    cached = load_authoritative_integrity_snapshot()
                    if kpis or cached:
                        if cached and cached.get("table_counts"):
                            merged = reconcile_integrity_metrics(
                                table_counts=cached.get("table_counts"),
                                coverage=cached.get("coverage"),
                                live_kpis=kpis,
                                stage_results=data.get("stage_results"),
                            )
                            data["integrity"] = {**cached, **merged}
                        else:
                            with SessionLocal() as sess:
                                data["integrity"] = build_authoritative_integrity(
                                    sess,
                                    live_kpis=kpis,
                                    stage_results=data.get("stage_results"),
                                )
                                sess.rollback()
                except Exception as exc:
                    logger.warning("[PIPELINE_INTEGRITY] live status integrity attach skipped: %s", exc)
            return data
    except Exception:
        pass
    return {"running": False, "stage": "idle", "progress": 0}


def get_live_status_fast() -> dict[str, Any]:
    """Redis-only status for hot paths (refresh accept, health probes)."""
    return get_live_status(include_integrity=False)


def is_running_fast() -> bool:
    status = get_live_status_fast()
    return bool(status.get("running", False))


def _last_activity_timestamp(data: dict) -> datetime | None:
    """Use the most recent of last_heartbeat_at (top-level or heartbeat blob) and updated_at."""
    from datetime import datetime

    hb = data.get("heartbeat") or {}
    candidates = [
        data.get("last_heartbeat_at"),
        hb.get("last_heartbeat_at"),
        data.get("updated_at"),
    ]
    best: datetime | None = None
    for raw in candidates:
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if best is None or ts > best:
                best = ts
        except (ValueError, TypeError):
            continue
    return best


def _stale_threshold_for(data: dict) -> int:
    stage = data.get("stage", "")
    ps = data.get("pipeline_status", "")
    if stage in _STAGE_STALE_THRESHOLDS:
        return _STAGE_STALE_THRESHOLDS[stage]
    if stage in _FINAL_PIPELINE_STAGES or ps in ("finalizing", "persisting"):
        return _STALE_FINAL_STAGE_S
    return _STALE_DEFAULT_S


def _detect_stale(r: Redis, data: dict) -> dict:
    """Heartbeat-based stall detection — delegates to pipeline_watchdog (enterprise)."""
    from worker.orchestration.pipeline_watchdog import enrich_live_status

    return enrich_live_status(data, r)


def is_running() -> bool:
    status = get_live_status_fast()
    if status.get("stage") in ("stalled", "failed", "idle") or status.get("pipeline_status") == "stalled":
        return False
    return bool(status.get("running", False))


def clear_status() -> None:
    """Reset status to idle (used on completion/failure)."""
    try:
        r = _redis()
        _set_status(r, "", "idle", 0, running=False)
    except Exception:
        pass


def _classify_degraded(stage: str, result: dict[str, Any]) -> str:
    if result.get("degraded_classification") == "aviation_enrichment_partial":
        return "aviation_enrichment_partial"
    if result.get("reconciled") or result.get("degraded_classification") == "false_degraded_stale_status":
        return "false_degraded_stale_status"
    if result.get("timeout"):
        return "real_degraded_timeout"
    if result.get("dependency_contract_failed"):
        return "real_degraded_dependency"
    return "real_degraded_runtime_failure"


def reconcile_pipeline_soft_failures(
    *,
    errors: list[dict[str, Any]],
    results: dict[str, Any],
    events: list[dict[str, str]],
    operation_id: str,
    kpis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Remove impossible/stale degraded states (delegates to operational_reconciliation)."""
    from worker.orchestration.operational_reconciliation import reconcile_pipeline_events

    out = reconcile_pipeline_events(
        operation_id=operation_id,
        errors=errors,
        results=results,
        events=events,
        kpis=kpis,
    )
    # Copy before clear — out["results"] is the same dict as `results`.
    merged_results = dict(out["results"])
    results.clear()
    results.update(merged_results)
    events[:] = out["events"]
    return out["errors"]


class OperationalRefreshPipeline:
    """Full operational refresh orchestrator."""

    def __init__(
        self,
        airline_slug: str | None = None,
        triggered_by: str = "manual",
        operation_id: str | None = None,
    ):
        self.operation_id = operation_id or str(uuid4())[:12]
        self.airline_slug = airline_slug
        self.triggered_by = triggered_by
        self.results: dict[str, Any] = {}
        self.errors: list[dict[str, str]] = []
        self.events: list[dict[str, str]] = []
        self.started_at = now_utc()
        self._kpis: dict[str, int | float] = {}
        self._last_successful_stage: str = ""
        self._stage_timings: dict[str, int] = {}
        self._heartbeat_count: int = 0
        self._redis: Redis | None = None
        self._finalization_started: float | None = None

    def _add_event(self, message: str) -> None:
        self.events.append(
            {
                "time": format_operational_time(),
                "message": message,
                "operation_id": self.operation_id,
            }
        )

    def _accumulate_kpis(self, stage: str, result: dict) -> None:
        """Extract and accumulate KPI values from a stage result.

        Valid (>0) values are always kept; zeros never overwrite existing positives.
        """
        if not isinstance(result, dict) or "error" in result:
            return
        mappings = _KPI_EXTRACTION_MAP.get(stage, [])
        for src_key, kpi_key in mappings:
            val = result.get(src_key)
            if isinstance(val, (int, float)) and val > 0:
                self._kpis[kpi_key] = val
            elif kpi_key not in self._kpis:
                self._kpis[kpi_key] = val if isinstance(val, (int, float)) else 0
        logger.info("[SNAPSHOT] kpis_accumulated stage=%s kpis=%s", stage, self._kpis)

    def _refresh_kpis_from_db(self) -> None:
        """Authoritative KPI totals from Postgres (not incremental stage deltas)."""
        from analytics.pipeline_integrity import (
            build_authoritative_integrity,
            kpi_totals_from_db,
            persist_authoritative_integrity_snapshot,
            record_integrity_metrics,
        )

        session = SessionLocal()
        try:
            totals = kpi_totals_from_db(session)
            for key, val in totals.items():
                if isinstance(val, (int, float)):
                    self._kpis[key] = val
            record_integrity_metrics(session)
            integrity = build_authoritative_integrity(
                session,
                live_kpis=self._kpis,
                stage_results=self.results,
            )
            acc = integrity.get("accumulated_kpis") or integrity.get("canonical_kpis") or {}
            counts = integrity.get("table_counts") or {}
            for key in (
                "reviews",
                "metadata",
                "graph_nodes",
                "graph_edges",
                "signals",
                "anomalies",
                "clusters",
                "snapshots",
                "aviation_metadata_total",
                "aviation_linked_total",
            ):
                val = acc.get(key)
                if val is None and key == "metadata":
                    val = counts.get("review_intelligence")
                elif val is None and key == "signals":
                    val = counts.get("fusion_signals")
                elif val is None:
                    val = counts.get(key)
                if isinstance(val, (int, float)) and val >= 0:
                    self._kpis[key] = int(val)
            persist_authoritative_integrity_snapshot(integrity, redis_client=self._redis)
            logger.info(
                "[INTEGRITY][AUTHORITATIVE_KPI] kpis_refreshed_from_db reconciled=%s %s",
                integrity.get("integrity_reconciled"),
                self._kpis,
            )
        except Exception as exc:
            logger.warning("[INTEGRITY] kpi refresh failed: %s", exc)
        finally:
            session.close()

    def _blocking_errors(self) -> list[dict[str, Any]]:
        """Errors that should degrade the pipeline — excludes optional aviation enrichment warnings."""
        fusion = self.results.get("fusion") if isinstance(self.results.get("fusion"), dict) else {}
        fusion_ok = (
            fusion.get("fusion_status") == "completed" and int(fusion.get("signals_generated") or 0) > 0
        )
        if fusion_ok:
            return [e for e in self.errors if e.get("stage") != "fusion"]
        return list(self.errors)

    def _live_status_label(self) -> str:
        """Return the current pipeline status label considering blocking errors only."""
        if self._blocking_errors():
            return "running_degraded"
        return "running"

    def execute(self) -> dict[str, Any]:
        logger.warning(
            "[%s][OPS] Pipeline.execute() called op=%s trigger=%s",
            format_operational_time(),
            self.operation_id,
            self.triggered_by,
        )
        r = _redis()
        self._redis = r

        lock_acquired = r.set(REDIS_LOCK_KEY, self.operation_id, nx=True, ex=14400)
        if not lock_acquired:
            existing = r.get(REDIS_LOCK_KEY)
            if existing != self.operation_id:
                logger.warning("[OPS] Skipped — lock held by %s, we are %s", existing, self.operation_id)
                return {"status": "skipped", "reason": "already_running"}

        logger.warning(
            "[OPS] Lock acquired, pipeline starting op=%s trigger=%s", self.operation_id, self.triggered_by
        )
        try:
            from app.runtime_state import reconcile_schema_blocks, runtime_state_reset
            from database.session import engine as db_engine

            runtime_state_reset(operation_id=self.operation_id, clear_degraded_history=True)
            reconcile_schema_blocks(db_engine)
        except Exception as exc:
            logger.warning("[SCHEMA] Pipeline reconcile skipped: %s", exc)
        self._add_event("Pipeline started")
        _set_status(
            r,
            self.operation_id,
            "crawl",
            5,
            triggered_by=self.triggered_by,
            events=self.events,
            active_layers=list(STAGES),
            pipeline_type="full",
            started_at=self.started_at.isoformat(),
        )

        try:
            self._run_stage(r, "discovery", 1, self._stage_discovery)
            self._run_stage(r, "crawl", 2, self._stage_crawl)
            self._run_stage(r, "metadata", 3, self._stage_metadata)
            self._run_stage(r, "semantic", 4, self._stage_semantic)
            self._run_stage(r, "knowledge_graph", 5, self._stage_knowledge_graph)
            self._run_stage(r, "forecasting", 6, self._stage_forecasting)
            self._run_stage(r, "anomalies", 7, self._stage_anomalies)
            self._run_stage(r, "insights", 8, self._stage_insights)
            self._run_stage(r, "aviation_master", 9, self._stage_aviation_master)
            self._run_stage(r, "fusion", 10, self._stage_fusion)
            self._run_stage(r, "snapshots", 11, self._stage_snapshots)

            fin_started = time.perf_counter()
            self._finalization_started = fin_started
            self._emit_finalization_heartbeat(r, "finalizing", "Refreshing KPI totals from database", 92)
            self._refresh_kpis_from_db()
            self._propagate_aviation_domains()
            self._reconcile_operational_state(r)
            self._emit_finalization_heartbeat(r, "finalizing", "Writing pipeline lineage report", 95)
            try:
                from analytics.pipeline_integrity import write_lineage_report

                write_lineage_report()
            except Exception as exc:
                logger.warning("[INTEGRITY] lineage report write failed: %s", exc)

            self._emit_finalization_heartbeat(r, "persisting", "Persisting operational run record", 98)
            blocking = self._blocking_errors()
            terminal = "completed_degraded" if blocking else "completed"
            self._add_event(f"Pipeline {terminal}")
            fin_ms = int((time.perf_counter() - fin_started) * 1000)
            record_worker_metric("skytrax_finalization_duration_ms", float(fin_ms))
            record_worker_metric("skytrax_final_heartbeat", 1.0)
            logger.warning(
                "[PIPELINE] %s — blocking_errors=%d total_errors=%d kpis=%s finalization_ms=%d op=%s",
                terminal,
                len(blocking),
                len(self.errors),
                self._kpis,
                fin_ms,
                self.operation_id,
            )
            _set_status(
                r,
                self.operation_id,
                terminal,
                100,
                running=False,
                events=self.events,
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
                kpis=self._kpis,
                stage_timings=self._stage_timings,
                pipeline_status=terminal,
            )
        except Exception as exc:
            self.errors.append({"stage": "pipeline", "error": str(exc)})
            self._add_event(f"Pipeline failed: {exc}")
            _set_status(
                r,
                self.operation_id,
                "failed",
                0,
                running=False,
                error=str(exc),
                events=self.events,
                stage_results=self.results,
                kpis=self._kpis,
                pipeline_status="failed",
            )
            logger.exception("[PIPELINE] FAILED op=%s", self.operation_id)
        finally:
            r.delete(REDIS_LOCK_KEY)

        elapsed_ms = int((now_utc() - self.started_at).total_seconds() * 1000)
        record_worker_metric("skytrax_operations_refresh", 1.0)
        record_worker_metric("skytrax_operations_duration_ms", float(elapsed_ms))
        record_worker_metric("skytrax_operations_failures", float(len(self._blocking_errors())))
        if self._blocking_errors():
            record_worker_metric("skytrax_pipeline_degraded", 1.0)

        self._persist_run(elapsed_ms)

        return {
            "operation_id": self.operation_id,
            "status": "completed" if not self._blocking_errors() else "partial",
            "elapsed_ms": elapsed_ms,
            "stages": self.results,
            "errors": self.errors,
            "blocking_errors": self._blocking_errors(),
        }

    def _reconcile_operational_state(self, r: Redis | None = None) -> None:
        from worker.orchestration.operational_reconciliation import reconcile_pipeline_events

        out = reconcile_pipeline_events(
            operation_id=self.operation_id,
            errors=self.errors,
            results=self.results,
            events=self.events,
            kpis=self._kpis,
        )
        self.errors = out["errors"]
        self.results = out["results"]
        self.events = out["events"]
        if r is not None:
            _set_status(
                r,
                self.operation_id,
                self._last_successful_stage or "snapshots",
                90,
                triggered_by=self.triggered_by,
                events=self.events,
                active_layers=list(STAGES),
                pipeline_type="full",
                completed_stages=self._completed_stage_keys(),
                failed_stages=out["failed_stages"],
                stage_results=self.results,
                kpis=self._kpis,
                operational_consistency=out.get("operational_consistency"),
                reconciled_stages=out.get("reconciled_stages", []),
                pipeline_status=self._live_status_label(),
            )

    def _completed_stage_keys(self) -> list[str]:
        failed_keys = set(self._failed_stage_keys())
        return [
            k
            for k in self.results
            if k not in failed_keys
            and not (
                isinstance(self.results[k], dict)
                and self.results[k].get("error")
                and not self.results[k].get("reconciled")
            )
        ]

    def _failed_stage_keys(self) -> list[str]:
        from worker.orchestration.operational_reconciliation import derive_failed_stages

        return derive_failed_stages(self.errors, self.results)

    def _pipeline_status_for_heartbeat(self, stage: str, detail: str) -> str:
        base = self._live_status_label()
        if base == "running_degraded":
            return base
        d = detail.lower()
        if stage in _FINAL_PIPELINE_STAGES or "fusion" in d or "signal" in d or "snapshot" in d:
            if "persist" in d or "commit" in d:
                return "persisting"
            if "finaliz" in d or "kpi" in d or "lineage" in d:
                return "finalizing"
        return base if base != "running" else "running"

    def _emit_finalization_heartbeat(
        self,
        r: Redis,
        pipeline_status: str,
        detail: str,
        progress: int,
    ) -> None:
        """Keep Redis status fresh while post-stage finalization runs."""
        self._heartbeat_count += 1
        now_iso = operational_timestamp()
        heartbeat_payload = {
            "current_stage": self._last_successful_stage or "snapshots",
            "stage_detail": detail[:120],
            "pipeline_elapsed_ms": int((now_utc() - self.started_at).total_seconds() * 1000),
            "last_successful_stage": self._last_successful_stage,
            "heartbeat_seq": self._heartbeat_count,
            "last_heartbeat_at": now_iso,
            "soft_failures": [e["stage"] for e in self.errors],
        }
        _set_status(
            r,
            self.operation_id,
            self._last_successful_stage or "snapshots",
            progress,
            triggered_by=self.triggered_by,
            events=self.events,
            active_layers=list(STAGES),
            pipeline_type="full",
            completed_stages=self._completed_stage_keys(),
            failed_stages=self._failed_stage_keys(),
            stage_results=self.results,
            kpis=self._kpis,
            heartbeat=heartbeat_payload,
            pipeline_status=pipeline_status,
            last_heartbeat_at=now_iso,
        )
        logger.info("[FUSION_HEARTBEAT] finalization detail=%s op=%s", detail, self.operation_id)
        record_worker_metric("skytrax_final_heartbeat", 1.0)

    def _make_heartbeat(
        self, r: Redis, stage: str, progress: int, layers: list, pipeline_type: str, stage_started: float
    ):
        """Return a callable that produces a rich heartbeat payload."""
        tag = "FUSION_HEARTBEAT" if stage in _FINAL_PIPELINE_STAGES else "HEARTBEAT"

        def heartbeat(detail: str | dict[str, Any] = "") -> None:
            self._heartbeat_count += 1
            try:
                now_iso = operational_timestamp()
                stage_elapsed_ms = int((time.perf_counter() - stage_started) * 1000)
                pipeline_elapsed_ms = int((now_utc() - self.started_at).total_seconds() * 1000)
                semantic = detail if isinstance(detail, dict) else {}
                detail_text = str(semantic.get("detail", detail if isinstance(detail, str) else ""))[:120]
                pipeline_status = self._pipeline_status_for_heartbeat(stage, detail_text)
                heartbeat_payload = {
                    "current_stage": stage,
                    "stage_detail": detail_text,
                    "stage_elapsed_ms": stage_elapsed_ms,
                    "pipeline_elapsed_ms": pipeline_elapsed_ms,
                    "last_successful_stage": self._last_successful_stage,
                    "heartbeat_seq": self._heartbeat_count,
                    "last_heartbeat_at": now_iso,
                    "soft_failures": [e["stage"] for e in self.errors],
                    "worker_alive": True,
                    "processed": semantic.get("processed"),
                    "remaining": semantic.get("remaining"),
                    "throughput_per_sec": semantic.get("throughput_per_sec"),
                    "elapsed_s": semantic.get("elapsed_s"),
                    "current_substage": semantic.get("current_substage"),
                }
                _set_status(
                    r,
                    self.operation_id,
                    stage,
                    progress,
                    triggered_by=self.triggered_by,
                    events=self.events,
                    active_layers=layers,
                    pipeline_type=pipeline_type,
                    completed_stages=self._completed_stage_keys(),
                    failed_stages=self._failed_stage_keys(),
                    stage_results=self.results,
                    kpis=self._kpis,
                    heartbeat=heartbeat_payload,
                    pipeline_status=pipeline_status,
                    last_heartbeat_at=now_iso,
                    worker_alive=True,
                    heartbeat_seq=self._heartbeat_count,
                    last_progress=progress,
                    last_progress_at=now_iso,
                )
                if detail_text:
                    logger.info(
                        "[%s] stage=%s detail=%s elapsed=%dms throughput=%s processed=%s remaining=%s op=%s",
                        tag,
                        stage,
                        detail_text,
                        stage_elapsed_ms,
                        heartbeat_payload.get("throughput_per_sec"),
                        heartbeat_payload.get("processed"),
                        heartbeat_payload.get("remaining"),
                        self.operation_id,
                    )
                record_worker_metric("skytrax_heartbeat_refresh", 1.0)
                hb_age_s = 0.0
                record_worker_metric("skytrax_heartbeat_age_s", hb_age_s)
                if pipeline_elapsed_ms > 0:
                    hb_freq = round(self._heartbeat_count / max(pipeline_elapsed_ms / 1000.0, 1.0), 4)
                    record_worker_metric("skytrax_heartbeat_frequency", hb_freq)
                if heartbeat_payload.get("throughput_per_sec") is not None:
                    record_worker_metric(
                        "skytrax_stage_throughput", float(heartbeat_payload.get("throughput_per_sec") or 0.0)
                    )
                if heartbeat_payload.get("processed") is not None:
                    record_worker_metric(
                        "skytrax_stage_processed", float(heartbeat_payload.get("processed") or 0.0)
                    )
                if heartbeat_payload.get("remaining") is not None:
                    record_worker_metric(
                        "skytrax_stage_remaining", float(heartbeat_payload.get("remaining") or 0.0)
                    )
            except Exception:
                pass

        return heartbeat

    def _run_stage(
        self,
        r: Redis,
        stage: str,
        index: int,
        fn,
        total_stages: int | None = None,
        active_layers: list | None = None,
        pipeline_type: str = "full",
    ) -> None:
        from app.runtime_state import is_stage_blocked, record_degraded_stage

        if is_stage_blocked(stage):
            msg = f"Stage '{stage}' skipped — schema incomplete (blocked)"
            self._add_event(msg)
            self.errors.append({"stage": stage, "error": "schema_blocked", "soft": True})
            self.results[stage] = {"error": "schema_blocked", "skipped": True}
            record_degraded_stage(stage, operation_id=self.operation_id, error="schema_blocked")
            logger.warning("[SCHEMA] %s op=%s", msg, self.operation_id)
            record_worker_metric("skytrax_pipeline_soft_failures", 1.0)
            return

        contract_skip = self._check_dependency_contract(stage)
        if contract_skip:
            self.results[stage] = contract_skip
            self.errors.append(
                {
                    "stage": stage,
                    "error": contract_skip.get("reason", "dependency_contract_failed"),
                    "soft": True,
                }
            )
            self._add_event(contract_skip.get("reason", f"Stage '{stage}' skipped — upstream empty"))
            record_degraded_stage(
                stage,
                operation_id=self.operation_id,
                error=contract_skip.get("reason", "dependency"),
            )
            record_worker_metric("skytrax_stage_dependency_failures", 1.0)
            record_worker_metric("skytrax_pipeline_soft_failures", 1.0)
            logger.warning("[DEPENDENCY] %s op=%s", contract_skip.get("reason"), self.operation_id)
            return

        total = total_stages or (len(STAGES) + 1)
        progress = int((index / total) * 100)
        layers = active_layers or list(STAGES)
        self._add_event(f"Stage '{stage}' started")
        logger.warning("[STAGE] '%s' starting (%d%%) op=%s", stage, progress, self.operation_id)
        _set_status(
            r,
            self.operation_id,
            stage,
            progress,
            triggered_by=self.triggered_by,
            events=self.events,
            active_layers=layers,
            pipeline_type=pipeline_type,
            completed_stages=self._completed_stage_keys(),
            failed_stages=self._failed_stage_keys(),
            stage_results=self.results,
            kpis=self._kpis,
            pipeline_status=self._live_status_label(),
        )
        started = time.perf_counter()
        heartbeat = self._make_heartbeat(r, stage, progress, layers, pipeline_type, started)
        try:
            if "heartbeat" in inspect.signature(fn).parameters:
                result = fn(heartbeat=heartbeat)
            else:
                result = fn()
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.results[stage] = result or {}
            self._stage_timings[stage] = duration_ms

            is_soft_failure = isinstance(result, dict) and "error" in result
            if (
                is_soft_failure
                and result.get("fusion_status") == "completed"
                and int(result.get("signals_generated") or 0) > 0
            ):
                is_soft_failure = False
            if is_soft_failure:
                degraded_classification = _classify_degraded(stage, result)
                result["degraded_classification"] = degraded_classification
                self.errors.append(
                    {
                        "stage": stage,
                        "error": str(result["error"]),
                        "soft": True,
                        "degraded_classification": degraded_classification,
                    }
                )
                self._add_event(f"Stage '{stage}' degraded ({duration_ms}ms): {str(result['error'])[:120]}")
                logger.warning(
                    "[AVIATION_STATUS] stage=%s classification=%s error=%s op=%s",
                    stage,
                    degraded_classification,
                    str(result["error"])[:180],
                    self.operation_id,
                )
                record_worker_metric("skytrax_pipeline_soft_failures", 1.0)
                try:
                    from app.runtime_state import record_degraded_stage

                    record_degraded_stage(
                        stage,
                        operation_id=self.operation_id,
                        error=str(result.get("error", "")),
                    )
                except Exception:
                    pass
            else:
                self._last_successful_stage = stage
                self._accumulate_kpis(stage, result or {})
                if stage == "fusion" and result.get("enrichment_warning"):
                    self._add_event(
                        f"Stage '{stage}' completed ({duration_ms}ms) — optional aviation enrichment warning",
                    )
                    logger.info(
                        "[SEMANTIC_CORRELATION] stage_completed_with_enrichment_warning reason=%s op=%s",
                        result.get("warning_reason"),
                        self.operation_id,
                    )
                else:
                    self._add_event(f"Stage '{stage}' completed ({duration_ms}ms)")
                logger.warning("[STAGE] '%s' completed (%dms) op=%s", stage, duration_ms, self.operation_id)

            record_worker_metric(f"skytrax_stage_{stage}_duration_ms", float(duration_ms))
            if stage == "fusion":
                record_worker_metric("skytrax_fusion_duration_ms", float(duration_ms))
            if stage == "snapshots":
                record_worker_metric("skytrax_snapshot_duration_ms", float(duration_ms))
            try:
                heartbeat("stage complete")
            except Exception:
                pass
            _set_status(
                r,
                self.operation_id,
                stage,
                progress,
                triggered_by=self.triggered_by,
                events=self.events,
                active_layers=layers,
                pipeline_type=pipeline_type,
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
                kpis=self._kpis,
                pipeline_status=self._live_status_label(),
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._stage_timings[stage] = duration_ms
            self.errors.append({"stage": stage, "error": str(exc)})
            self.results[stage] = {"error": str(exc)}
            self._add_event(f"Stage '{stage}' failed: {exc}")
            logger.warning("[STAGE] '%s' FAILED: %s (%dms) op=%s", stage, exc, duration_ms, self.operation_id)
            record_worker_metric("skytrax_pipeline_soft_failures", 1.0)
            record_worker_metric(f"skytrax_stage_{stage}_duration_ms", float(duration_ms))
            _set_status(
                r,
                self.operation_id,
                stage,
                progress,
                triggered_by=self.triggered_by,
                events=self.events,
                active_layers=layers,
                pipeline_type=pipeline_type,
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
                kpis=self._kpis,
                pipeline_status=self._live_status_label(),
            )

    def _stage_discovery(self, heartbeat=None) -> dict:
        """Run airline_discovery spider to find all airline review URLs."""
        import subprocess

        if heartbeat:
            heartbeat("discovering airlines")
        logger.warning("[STAGE] [DISCOVERY] Running airline discovery spider op=%s", self.operation_id)
        result = subprocess.run(
            ["scrapy", "crawl", "airline_discovery"],
            check=False,
            capture_output=True,
            text=True,
        )
        success = result.returncode == 0
        discovered = 0
        for line in result.stdout.splitlines():
            if "airline_discovery_closed" in line or "discovered=" in line:
                import re

                m = re.search(r"discovered=(\d+)", line)
                if m:
                    discovered = int(m.group(1))
        if not success:
            logger.warning("[OPS] [DISCOVERY] Spider failed: %s", result.stderr[-1000:])
        else:
            logger.warning("[OPS] [DISCOVERY] Discovered %d airlines op=%s", discovered, self.operation_id)

        session = SessionLocal()
        try:
            from database.models.core import Airline

            total = session.query(Airline).filter(Airline.is_active.is_(True)).count()
        finally:
            session.close()

        return {"success": success, "airlines_discovered": discovered, "total_airlines_in_db": total}

    def _stage_crawl(self, heartbeat=None) -> dict:
        """Deep review scraping with subprocess lifecycle governance.

        Uses SubprocessGovernor for automatic termination on:
        - corpus saturation
        - duplicate streaks
        - frozen telemetry / reactor hanging
        - zero throughput
        - hard timeout
        """
        import subprocess
        from app.config import get_settings
        from worker.subprocess_governor import SubprocessGovernor, CrawlState

        settings = get_settings()
        max_pages = settings.crawl_deep_max_pages
        skip_hours = settings.crawl_skip_recent_hours

        effective_max = max_pages if max_pages > 0 else 50

        cmd = [
            "scrapy",
            "crawl",
            "airlinequality_reviews",
            "-a",
            f"max_pages={effective_max}",
            "-a",
            f"operation_id={self.operation_id}",
        ]

        if self.airline_slug:
            cmd.extend(["-a", f"airline={self.airline_slug}"])
            logger.warning(
                "[CRAWL] Single airline=%s max_pages=%d op=%s",
                self.airline_slug,
                effective_max,
                self.operation_id,
            )
        else:
            cmd.extend(["-a", "mode=all", "-a", f"skip_recent_hours={skip_hours}"])
            logger.warning(
                "[CRAWL] Full ingestion mode=all max_pages=%d skip_recent=%dh op=%s",
                effective_max,
                skip_hours,
                self.operation_id,
            )

        crawl_started = time.time()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # ── Subprocess lifecycle governance ──────────────────────
        governor = SubprocessGovernor(
            proc=proc,
            redis_status_key=REDIS_STATUS_KEY,
            redis_fn=_redis,
            heartbeat_fn=heartbeat,
            operation_id=self.operation_id,
            metrics_fn=record_worker_metric,
        )

        gov_result = governor.run()

        # ── Collect final telemetry ──────────────────────────────
        r = _redis()
        raw = r.get(REDIS_STATUS_KEY)
        telemetry = {}
        if raw:
            try:
                telemetry = json.loads(raw).get("crawl_telemetry", {})
            except Exception:
                pass

        session = SessionLocal()
        try:
            from database.models.core import Review, Airline

            total_reviews = session.query(Review).count()
            total_airlines = session.query(Airline).filter(Airline.is_active.is_(True)).count()
        finally:
            session.close()

        reviews_added = telemetry.get("reviews_added", 0)
        pages_processed = telemetry.get("pages_processed", 0)
        duplicates = telemetry.get("duplicates_skipped", 0)
        saturated = telemetry.get("saturated", False)
        governor_terminated = telemetry.get("governor_terminated", False)
        termination_trigger = telemetry.get("termination_trigger", "")

        record_worker_metric("skytrax_reviews_total", float(total_reviews))
        record_worker_metric("skytrax_reviews_added_total", float(reviews_added))
        record_worker_metric("skytrax_crawler_pages_processed", float(pages_processed))
        record_worker_metric("skytrax_crawler_duplicates_skipped", float(duplicates))
        record_worker_metric("skytrax_crawl_requests_total", float(pages_processed))
        if saturated or governor_terminated:
            record_worker_metric("skytrax_crawl_saturation_total", 1.0)

        crawl_elapsed = int(time.time() - crawl_started)
        insert_rate = round(reviews_added / max(crawl_elapsed, 1), 2)
        record_worker_metric("skytrax_crawl_insert_rate", insert_rate)

        success = gov_result.get("returncode") == 0 or gov_result.get("state") in (
            CrawlState.COMPLETED.value,
            CrawlState.TERMINATED.value,
            CrawlState.SATURATED.value,
        )

        logger.warning(
            "[CRAWL] Done: reviews_total=%d added=%d dupes=%d pages=%d airlines=%d "
            "saturated=%s governor_state=%s trigger=%s elapsed=%ds rate=%.2f/s op=%s",
            total_reviews,
            reviews_added,
            duplicates,
            pages_processed,
            total_airlines,
            saturated,
            gov_result.get("state", "unknown"),
            termination_trigger,
            crawl_elapsed,
            insert_rate,
            self.operation_id,
        )
        return {
            "success": success,
            "mode": "all" if not self.airline_slug else "single",
            "max_pages": effective_max,
            "total_reviews_in_db": total_reviews,
            "total_airlines_in_db": total_airlines,
            "reviews_added": reviews_added,
            "duplicates_skipped": duplicates,
            "pages_processed": pages_processed,
            "saturated": saturated or governor_terminated,
            "crawl_elapsed_s": crawl_elapsed,
            "insert_rate": insert_rate,
            "governor": gov_result,
        }

    def _check_dependency_contract(self, stage: str) -> dict | None:
        """Return skip payload when upstream data contract is not satisfied."""
        if stage not in _DEPENDENCY_SKIP_STAGES:
            return None

        if stage == "fusion":
            from analytics.semantic_correlation_upstream import validate_semantic_correlation_upstream

            session = SessionLocal()
            try:
                validation = validate_semantic_correlation_upstream(
                    session,
                    stage_results=self.results,
                    pipeline_kpis=self._kpis,
                    operation_id=self.operation_id,
                )
                if validation.get("ready"):
                    return None
                contract = validation.get("contract") or {}
                failures = contract.get("failures") or validation.get("blockers") or []
                reason = contract.get("skip_message") or (
                    f"{stage} skipped — upstream contract failed: " + "; ".join(failures)
                )
                logger.warning(
                    "[UPSTREAM_VALIDATION] fusion_contract_failed failures=%s counts=%s op=%s",
                    failures,
                    validation.get("counts"),
                    self.operation_id,
                )
                return {
                    "skipped": True,
                    "dependency_contract_failed": True,
                    "reason": reason,
                    "failures": failures,
                    "upstream_validation": {
                        "graph_nodes_loaded": validation.get("graph_nodes_loaded"),
                        "metadata_loaded": validation.get("metadata_loaded"),
                        "false_empty_prevented": validation.get("false_empty_prevented"),
                    },
                }
            finally:
                session.close()

        from analytics.pipeline_integrity import check_stage_contract, collect_table_counts
        from analytics.semantic_correlation_upstream import merge_upstream_counts

        session = SessionLocal()
        try:
            counts = merge_upstream_counts(
                collect_table_counts(session),
                stage_results=self.results,
                pipeline_kpis=self._kpis,
            )
            contract = check_stage_contract(stage, counts)
            if contract.get("satisfied"):
                return None
            reason = contract.get("skip_message") or (
                f"{stage} skipped — upstream contract failed: " + "; ".join(contract.get("failures", []))
            )
            return {
                "skipped": True,
                "dependency_contract_failed": True,
                "reason": reason,
                "failures": contract.get("failures", []),
            }
        finally:
            session.close()

    def _stage_metadata(self) -> dict:
        """Extract structured intelligence (disruptions, quality, routes) from reviews."""
        from analytics.metadata_extractor import run_metadata_extraction_until_done
        from analytics.pipeline_integrity import collect_table_counts

        session = SessionLocal()
        try:
            before = collect_table_counts(session)
            reviews_total = max(before.get("reviews", 0), 0)
            meta_before = before.get("review_intelligence", 0)

            if meta_before < 0:
                from analytics.pipeline_integrity import collect_count_errors

                return {
                    "error": "review_intelligence_table_unreadable",
                    "hint": "Check review_intelligence schema vs ORM (migrations 0009+)",
                    "count_errors": collect_count_errors(before),
                }

            last = run_metadata_extraction_until_done(session, batch_size=1000, max_batches=50)
            after = collect_table_counts(session)
            meta_after = max(after.get("review_intelligence", 0), 0)
            last["metadata_total"] = meta_after
            last["reviews_total"] = reviews_total

            record_worker_metric("skytrax_metadata_extracted_total", float(last.get("reviews_analyzed", 0)))
            record_worker_metric("skytrax_metadata_records", float(meta_after))

            if "error" not in last and reviews_total > 0 and meta_after == 0:
                last["error"] = "metadata_persistence_empty"
                last["hint"] = (
                    f"{reviews_total} reviews in corpus but review_intelligence count is 0 after extraction"
                )
                logger.error(
                    "[OPS][METADATA] Persistence gap reviews=%d op=%s", reviews_total, self.operation_id
                )
            elif "error" not in last and last.get("remaining", 0) > 0:
                logger.warning(
                    "[OPS][METADATA] Partial backfill remaining=%d analyzed=%d op=%s",
                    last.get("remaining"),
                    last.get("reviews_analyzed"),
                    self.operation_id,
                )
            return last
        except Exception as exc:
            logger.exception("[OPS][METADATA] Failed op=%s", self.operation_id)
            return {"error": str(exc), "error_type": type(exc).__name__}
        finally:
            session.close()

    def _stage_semantic(self) -> dict:
        """NLP enrichment + semantic clustering (combined)."""
        from worker.jobs import _enrich_pending, _refresh_clusters

        nlp = _enrich_pending(500)
        clusters = _refresh_clusters()
        return {**nlp, **clusters}

    def _stage_knowledge_graph(self) -> dict:
        """Build/update aviation knowledge graph from corpus and metadata."""
        from analytics.knowledge_graph import AviationKnowledgeGraph

        session = SessionLocal()
        try:
            graph = AviationKnowledgeGraph(session)
            result = graph.update_from_corpus()
            record_worker_metric("skytrax_graph_nodes_total", float(result.get("total_nodes", 0)))
            record_worker_metric("skytrax_graph_edges_total", float(result.get("total_edges", 0)))
            return result
        except Exception as exc:
            logger.warning("[OPS][GRAPH] Failed: %s op=%s", exc, self.operation_id)
            return {"error": str(exc)}
        finally:
            session.close()

    def _stage_forecasting(self, heartbeat=None) -> dict:
        from worker.forecasting_isolation import run_forecasting_stage

        try:
            result = run_forecasting_stage(heartbeat_fn=heartbeat)
            record_worker_metric("skytrax_forecasting_jobs_total", 1.0)
            record_worker_metric(
                "skytrax_forecasts_persisted",
                float(result.get("forecasts_persisted", 0)),
            )
            if result.get("native_crash"):
                record_worker_metric("skytrax_forecast_segfault_total", 1.0)
            if result.get("mode") == "safe" or result.get("safe_mode"):
                record_worker_metric("skytrax_forecast_safe_mode_total", 1.0)
            if "error" in result and result.get("forecasts_persisted", 0) == 0:
                logger.warning(
                    "[OPS][FORECASTING] Stage degraded: %s op=%s",
                    result.get("error", result.get("fallback_reason")),
                    self.operation_id,
                )
                return {
                    "error": str(result.get("error", result.get("fallback_reason", "forecast_failed"))),
                    "forecasts_persisted": 0,
                    **{k: v for k, v in result.items() if k not in ("error",)},
                }
            return result
        except Exception as exc:
            logger.exception(
                "[OPS][FORECASTING] Stage shield caught: %s op=%s",
                exc,
                self.operation_id,
            )
            record_worker_metric("skytrax_forecasting_jobs_total", 1.0)
            return {"error": str(exc), "forecasts_persisted": 0}

    def _stage_anomalies(self, heartbeat=None) -> dict:
        from analytics.anomaly import AnomalyDetectionService

        session = SessionLocal()
        try:
            svc = AnomalyDetectionService(session)
            result = svc.detect_and_persist(heartbeat_fn=heartbeat)
            record_worker_metric("skytrax_anomalies_total", float(result.get("anomalies_created", 0)))
            return result
        except Exception as exc:
            session.rollback()
            logger.warning("[OPS][ANOMALIES] Stage failed: %s op=%s", exc, self.operation_id)
            return {"error": str(exc), "anomalies_created": 0}
        finally:
            session.close()

    def _stage_insights(self, heartbeat=None) -> dict:
        if heartbeat:
            heartbeat("generating insights")
        try:
            from worker.jobs import _generate_insights

            return _generate_insights()
        except Exception as exc:
            logger.warning("[OPS][INSIGHTS] Failed: %s op=%s", exc, self.operation_id)
            return {"error": str(exc), "insights_created": 0}

    def _stage_aviation_master(self) -> dict:
        """Canonical aviation data sync from OpenFlights + OurAirports."""
        from aviation.master_data.sync import AviationMasterSync
        from database.runtime_schema import ensure_aviation_runtime_ready, is_stale_schema_error
        from database.session import SessionLocal, engine

        ensure_aviation_runtime_ready(engine)
        session = SessionLocal()
        try:
            sync = AviationMasterSync(session)
            result = sync.run()
            if not result.get("error"):
                try:
                    from aviation.operational_propagation import propagate_operational_domains

                    propagate = propagate_operational_domains(session, commit=True)
                    result["operational_propagation"] = propagate
                except Exception as prop_exc:
                    session.rollback()
                    logger.warning(
                        "[OPS][AVIATION_MASTER] operational propagation failed: %s op=%s",
                        prop_exc,
                        self.operation_id,
                    )
                    result["operational_propagation_error"] = str(prop_exc)[:200]
            record_worker_metric(
                "skytrax_aviation_master_airlines",
                float(result.get("airlines_created", 0) + result.get("airlines_updated", 0)),
            )
            return result
        except Exception as exc:
            session.rollback()
            err = str(exc)
            if is_stale_schema_error(exc):
                logger.warning(
                    "[OPS][AVIATION_MASTER] Stale schema — refreshing runtime once op=%s", self.operation_id
                )
                ensure_aviation_runtime_ready(engine, allow_retry=True)
                session.close()
                session = SessionLocal()
                try:
                    sync = AviationMasterSync(session)
                    result = sync.run()
                    record_worker_metric(
                        "skytrax_aviation_master_airlines",
                        float(result.get("airlines_created", 0) + result.get("airlines_updated", 0)),
                    )
                    return result
                except Exception as retry_exc:
                    session.rollback()
                    err = str(retry_exc)
                    exc = retry_exc
            if "iata_code" in err and "does not exist" in err:
                err = "airline_metadata.iata_code missing — schema drift; run: alembic upgrade head"
            logger.warning("[OPS][AVIATION_MASTER] Failed: %s op=%s", err, self.operation_id)
            return {"error": err, "schema_drift": "iata_code" in str(exc)}
        finally:
            session.close()

    def _stage_fusion(self, heartbeat=None) -> dict:
        """Semantic correlation: validate upstream → generate signals → optional aviation enrichment."""
        results: dict[str, Any] = {}
        fusion_started = time.perf_counter()
        max_enrich_seconds = int(os.getenv("FUSION_MAX_ENRICH_SECONDS", "90"))

        logger.info("[SEMANTIC_CORRELATION] stage_start op=%s", self.operation_id)
        if heartbeat:
            heartbeat("semantic correlation: upstream validation")

        session = SessionLocal()
        try:
            from analytics.semantic_correlation_upstream import (
                should_skip_aviation_enrichment,
                validate_semantic_correlation_upstream,
            )

            validation = validate_semantic_correlation_upstream(
                session,
                stage_results=self.results,
                pipeline_kpis=self._kpis,
                operation_id=self.operation_id,
            )
            results["upstream_validation"] = {
                "ready": validation.get("ready"),
                "graph_nodes_loaded": validation.get("graph_nodes_loaded"),
                "graph_edges_loaded": validation.get("graph_edges_loaded"),
                "metadata_loaded": validation.get("metadata_loaded"),
                "validation_ms": validation.get("validation_ms"),
                "false_empty_prevented": validation.get("false_empty_prevented"),
            }
            if not validation.get("ready"):
                failures = (validation.get("contract") or {}).get("failures") or validation.get("blockers")
                return {
                    "error": f"upstream_not_ready: {'; '.join(failures or ['unknown'])}",
                    "dependency_contract_failed": True,
                    "skipped": True,
                    "upstream_validation": results["upstream_validation"],
                }
        finally:
            session.close()

        if heartbeat:
            heartbeat("semantic correlation: generating signals")
        correlation_started = time.perf_counter()
        try:
            from analytics.fusion_intelligence import FusionIntelligenceEngine

            session = SessionLocal()
            try:
                fusion = FusionIntelligenceEngine(session).generate_and_persist(
                    heartbeat_fn=heartbeat,
                    operation_id=self.operation_id,
                )
                results["fusion"] = fusion
                results["signals_generated"] = fusion.get("signals_generated", 0)
                record_worker_metric(
                    "skytrax_fusion_signals_total",
                    float(fusion.get("signals_generated", 0)),
                )
                logger.info(
                    "[SEMANTIC_CORRELATION] stage_finish signals=%d pairs_categories=%s ms=%d op=%s",
                    fusion.get("signals_generated", 0),
                    list((fusion.get("categories") or {}).keys())[:8],
                    fusion.get("duration_ms", 0),
                    self.operation_id,
                )
            finally:
                session.close()
        except Exception as exc:
            logger.exception(
                "[SEMANTIC_CORRELATION] signal generation failed: %s op=%s", exc, self.operation_id
            )
            results["fusion"] = {"error": str(exc)}
            fusion_ms = int((time.perf_counter() - fusion_started) * 1000)
            record_worker_metric("skytrax_fusion_duration_ms", float(fusion_ms))
            return {
                **results,
                "error": str(exc),
                "correlation_failed": True,
                "signals_generated": 0,
            }

        correlation_ms = int((time.perf_counter() - correlation_started) * 1000)
        results["correlation_ms"] = correlation_ms

        skip_aviation, skip_reason = False, ""
        session = SessionLocal()
        try:
            from analytics.semantic_correlation_upstream import should_skip_aviation_enrichment

            skip_aviation, skip_reason = should_skip_aviation_enrichment(
                session,
                validation=validation,
            )
        finally:
            session.close()

        if skip_aviation:
            results["aviation"] = {"skipped": True, "reason": skip_reason}
            logger.info(
                "[SEMANTIC_CORRELATION] aviation_enrichment_skipped reason=%s op=%s",
                skip_reason,
                self.operation_id,
            )
        else:
            if heartbeat:
                heartbeat("semantic correlation: aviation enrichment (optional)")
            try:
                from scripts.bootstrap_aviation import run_enrichment_pass

                aviation_result = run_enrichment_pass(
                    heartbeat_fn=heartbeat,
                    max_seconds=max_enrich_seconds,
                )
                results["aviation"] = aviation_result
                if isinstance(aviation_result, dict) and aviation_result.get("timeout"):
                    logger.warning(
                        "[SEMANTIC_CORRELATION] aviation_enrichment_timeout elapsed_s=%s limit_s=%d op=%s",
                        aviation_result.get("elapsed_s"),
                        max_enrich_seconds,
                        self.operation_id,
                    )
                    results["enrichment_warning"] = True
                    results["warning_reason"] = "aviation_enrichment_timeout"
                    results["warning_type"] = "optional_enrichment_timeout"
            except Exception as exc:
                logger.warning("[SEMANTIC_CORRELATION] aviation enrichment failed (non-fatal): %s", exc)
                results["aviation"] = {"error": str(exc), "degraded": True}
                results["enrichment_warning"] = True
                results["warning_reason"] = "aviation_enrichment_failed"
                results["warning_type"] = "optional_enrichment_timeout"

        if heartbeat:
            heartbeat("semantic correlation complete")
        fusion_ms = int((time.perf_counter() - fusion_started) * 1000)
        record_worker_metric("skytrax_fusion_duration_ms", float(fusion_ms))
        fusion_blob = results.get("fusion") or {}
        persistence_ok = (
            isinstance(fusion_blob, dict)
            and (fusion_blob.get("persistence_validation") or {}).get("committed", True) is not False
        )
        signals = int(results.get("signals_generated") or 0)
        upstream_ready = bool((results.get("upstream_validation") or {}).get("ready"))

        if isinstance(fusion_blob, dict) and fusion_blob.get("error"):
            return {
                **results,
                "error": str(fusion_blob["error"]),
                "correlation_failed": True,
                "fusion_status": "failed",
            }

        if signals > 0 and upstream_ready and persistence_ok:
            results["fusion_status"] = "completed"
            results["correlation_completed"] = True
            if results.get("enrichment_warning"):
                results["stage_warning"] = True
                results.setdefault("warning_type", "optional_enrichment_timeout")
                results.setdefault("warning_reason", "aviation_enrichment_timeout")
                logger.warning(
                    "[SEMANTIC_CORRELATION] enrichment_warning reason=%s signals=%d op=%s",
                    results.get("warning_reason"),
                    signals,
                    self.operation_id,
                )
            else:
                results["enrichment_warning"] = False
        else:
            results["fusion_status"] = "failed"
            return {
                **results,
                "error": "semantic_correlation_incomplete",
                "correlation_failed": True,
            }

        logger.info(
            "[SEMANTIC_CORRELATION] stage_done total_ms=%d correlation_ms=%d signals=%d "
            "fusion_status=%s enrichment_warning=%s op=%s",
            fusion_ms,
            correlation_ms,
            signals,
            results.get("fusion_status"),
            results.get("enrichment_warning"),
            self.operation_id,
        )
        return results

    def _stage_snapshots(self, heartbeat=None) -> dict:
        snap_started = time.perf_counter()
        if heartbeat:
            heartbeat("metric snapshots started")
        logger.info("[SNAPSHOT] stage_start op=%s", self.operation_id)
        try:
            from worker.jobs import _generate_snapshots

            result = _generate_snapshots("hourly", heartbeat_fn=heartbeat)
            if isinstance(result, dict) and "error" in result:
                record_worker_metric("skytrax_snapshot_failures", 1.0)
            snap_ms = int((time.perf_counter() - snap_started) * 1000)
            record_worker_metric("skytrax_snapshot_duration_ms", float(snap_ms))
            if heartbeat:
                heartbeat("metric snapshots complete")
            logger.info(
                "[SNAPSHOT] stage_done ms=%d created=%s op=%s",
                snap_ms,
                result.get("created"),
                self.operation_id,
            )
            return result
        except Exception as exc:
            logger.exception("[SNAPSHOT] persistence failed: %s op=%s", exc, self.operation_id)
            record_worker_metric("skytrax_snapshot_failures", 1.0)
            return {"error": str(exc), "created": 0}

    def _propagate_aviation_domains(self) -> dict[str, Any]:
        """Ensure aviation / hubs / alliances / coverage tables reflect core airline corpus."""
        from aviation.operational_propagation import propagate_operational_domains

        session = SessionLocal()
        try:
            stats = propagate_operational_domains(session, commit=True)
            self._add_event(
                f"Aviation domains propagated: {stats.get('airlines_metadata_total', 0)} airlines, "
                f"{stats.get('hubs_with_level', 0)} hubs"
            )
            return stats
        except Exception as exc:
            session.rollback()
            logger.warning("[OPS][AVIATION_PROPAGATE] failed: %s op=%s", exc, self.operation_id)
            return {"error": str(exc)[:200]}
        finally:
            session.close()

    def _persist_run(self, elapsed_ms: int) -> None:
        from app.payload_serialization import safe_json_value
        from database.models.operations import OperationalRefreshRun

        session = SessionLocal()
        try:
            stage_results = safe_json_value(self.results)
            run = OperationalRefreshRun(
                operation_id=self.operation_id,
                started_at=self.started_at,
                finished_at=now_utc(),
                duration_ms=elapsed_ms,
                status="completed" if not self._blocking_errors() else "partial",
                reviews_processed=self.results.get("semantic", {}).get("enriched", 0),
                airlines_updated=self.results.get("crawl", {}).get("total_airlines_in_db", 0),
                anomalies_generated=self.results.get("anomalies", {}).get("anomalies_created", 0),
                forecasts_generated=self.results.get("forecasting", {}).get("forecasts_persisted", 0),
                semantic_updates=self.results.get("semantic", {}).get("clusters_created", 0),
                error_count=len(self.errors),
                warnings=[],
                triggered_by=self.triggered_by,
                stage_results=stage_results,
            )
            session.add(run)
            session.commit()
            logger.info("persist_run_ok op=%s", self.operation_id)
        except Exception as exc:
            logger.warning("persist_run_failed: %s", exc)
            session.rollback()
        finally:
            session.close()


class AviationSyncPipeline:
    """Aviation-only operational sync: airports, metadata, hub intelligence.

    Reuses the same Redis status key, lock, and operation_id ecosystem
    so the TopCommandBar and modal reflect activity.
    """

    def __init__(
        self,
        triggered_by: str = "aviation_sync",
        operation_id: str | None = None,
    ):
        self.operation_id = operation_id or str(uuid4())[:12]
        self.triggered_by = triggered_by
        self.results: dict[str, Any] = {}
        self.errors: list[dict[str, str]] = []
        self.events: list[dict[str, str]] = []
        self.started_at = now_utc()

    def _add_event(self, message: str) -> None:
        self.events.append(
            {
                "time": format_operational_time(),
                "message": message,
                "operation_id": self.operation_id,
            }
        )

    def _reconcile_operational_state(self, r: Redis) -> None:
        from worker.orchestration.operational_reconciliation import reconcile_pipeline_events

        out = reconcile_pipeline_events(
            operation_id=self.operation_id,
            errors=self.errors,
            results=self.results,
            events=self.events,
            kpis={},
        )
        self.errors = out["errors"]
        self.results = out["results"]
        self.events = out["events"]

    def execute(self) -> dict[str, Any]:
        logger.warning("[%s][OPS] AviationSync.execute() op=%s", format_operational_time(), self.operation_id)
        r = _redis()

        lock_acquired = r.set(REDIS_LOCK_KEY, self.operation_id, nx=True, ex=3600)
        if not lock_acquired:
            existing = r.get(REDIS_LOCK_KEY)
            if existing != self.operation_id:
                logger.warning("[OPS] Aviation sync skipped — lock held by %s", existing)
                return {"status": "skipped", "reason": "already_running"}

        layers = list(AVIATION_STAGES)
        try:
            from app.runtime_state import runtime_state_reset

            runtime_state_reset(operation_id=self.operation_id, clear_degraded_history=True)
        except Exception as exc:
            logger.warning("[SOFT_FAILURE_CLEANUP] Aviation reset skipped: %s", exc)
        self._add_event("Aviation sync started")
        _set_status(
            r,
            self.operation_id,
            "airport_discovery",
            5,
            triggered_by=self.triggered_by,
            events=self.events,
            active_layers=layers,
            pipeline_type="aviation",
        )

        try:
            self._run_stage(r, "aviation_master", 1, self._stage_aviation_master, layers)
            self._run_stage(r, "airport_discovery", 2, self._stage_airport_discovery, layers)
            self._run_stage(r, "aviation_metadata", 3, self._stage_aviation_metadata, layers)
            self._run_stage(r, "hub_intelligence", 4, self._stage_hub_intelligence, layers)
            self._run_aviation_propagate_final()
            self._reconcile_operational_state(r)

            terminal = "completed_degraded" if self.errors else "completed"
            self._add_event(f"Aviation sync {terminal}")
            _set_status(
                r,
                self.operation_id,
                terminal,
                100,
                running=False,
                events=self.events,
                active_layers=layers,
                pipeline_type="aviation",
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
                pipeline_status=terminal,
            )
        except Exception as exc:
            self.errors.append({"stage": "aviation_pipeline", "error": str(exc)})
            self._add_event(f"Aviation sync failed: {exc}")
            _set_status(
                r,
                self.operation_id,
                "failed",
                0,
                running=False,
                error=str(exc),
                events=self.events,
                active_layers=layers,
                pipeline_type="aviation",
                stage_results=self.results,
            )
            logger.exception("aviation_sync_failed op=%s", self.operation_id)
        finally:
            r.delete(REDIS_LOCK_KEY)

        elapsed_ms = int((now_utc() - self.started_at).total_seconds() * 1000)
        record_worker_metric("skytrax_aviation_sync_runs", 1.0)
        record_worker_metric("skytrax_aviation_sync_duration_ms", float(elapsed_ms))

        self._persist_run(elapsed_ms)

        return {
            "operation_id": self.operation_id,
            "status": "completed" if not self.errors else "partial",
            "pipeline_type": "aviation",
            "elapsed_ms": elapsed_ms,
            "stages": self.results,
            "errors": self.errors,
        }

    def _completed_stage_keys(self) -> list[str]:
        failed_keys = set(self._failed_stage_keys())
        return [
            k
            for k in self.results
            if k not in failed_keys
            and not (
                isinstance(self.results[k], dict)
                and self.results[k].get("error")
                and not self.results[k].get("reconciled")
            )
        ]

    def _failed_stage_keys(self) -> list[str]:
        from worker.orchestration.operational_reconciliation import derive_failed_stages

        return derive_failed_stages(self.errors, self.results)

    def _run_stage(self, r: Redis, stage: str, index: int, fn, layers: list) -> None:
        total = len(AVIATION_STAGES) + 1
        progress = int((index / total) * 100)
        self._add_event(f"Stage '{stage}' started")
        logger.warning(
            "[OPS] [AVIATION] Stage '%s' starting (%d%%) op=%s", stage, progress, self.operation_id
        )
        _set_status(
            r,
            self.operation_id,
            stage,
            progress,
            triggered_by=self.triggered_by,
            events=self.events,
            active_layers=layers,
            pipeline_type="aviation",
            completed_stages=self._completed_stage_keys(),
            failed_stages=self._failed_stage_keys(),
            stage_results=self.results,
        )
        started = time.perf_counter()
        try:
            result = fn()
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.results[stage] = result or {}
            self._add_event(f"Stage '{stage}' completed ({duration_ms}ms)")
            logger.warning(
                "[OPS] [AVIATION] Stage '%s' done (%dms) op=%s", stage, duration_ms, self.operation_id
            )
            _set_status(
                r,
                self.operation_id,
                stage,
                progress,
                triggered_by=self.triggered_by,
                events=self.events,
                active_layers=layers,
                pipeline_type="aviation",
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.errors.append({"stage": stage, "error": str(exc)})
            self.results[stage] = {"error": str(exc)}
            self._add_event(f"Stage '{stage}' failed: {exc}")
            logger.warning("[OPS] [AVIATION] Stage '%s' FAILED: %s (%dms)", stage, exc, duration_ms)
            _set_status(
                r,
                self.operation_id,
                stage,
                progress,
                triggered_by=self.triggered_by,
                events=self.events,
                active_layers=layers,
                pipeline_type="aviation",
                completed_stages=self._completed_stage_keys(),
                failed_stages=self._failed_stage_keys(),
                stage_results=self.results,
            )

    def _stage_aviation_master(self) -> dict:
        """Canonical aviation data sync from OpenFlights + OurAirports."""
        from aviation.master_data.sync import AviationMasterSync
        from database.runtime_schema import ensure_aviation_runtime_ready
        from database.session import SessionLocal, engine

        ensure_aviation_runtime_ready(engine)
        session = SessionLocal()
        try:
            sync = AviationMasterSync(session)
            result = sync.run()
            if not result.get("error"):
                try:
                    from aviation.operational_propagation import propagate_operational_domains

                    result["operational_propagation"] = propagate_operational_domains(session, commit=True)
                except Exception as prop_exc:
                    session.rollback()
                    result["operational_propagation_error"] = str(prop_exc)[:200]
            return result
        except Exception as exc:
            session.rollback()
            logger.warning("[OPS][AVIATION_MASTER] Failed: %s op=%s", exc, self.operation_id)
            return {"error": str(exc)}
        finally:
            session.close()

    def _run_aviation_propagate_final(self) -> None:
        from aviation.operational_propagation import propagate_operational_domains

        session = SessionLocal()
        try:
            stats = propagate_operational_domains(session, commit=True)
            self.results["aviation_propagation"] = stats
            self._add_event(
                f"Operational domains refreshed: {stats.get('airlines_metadata_total', 0)} airlines"
            )
        except Exception as exc:
            session.rollback()
            logger.warning("[OPS][AVIATION_PROPAGATE] final pass failed: %s", exc)
        finally:
            session.close()

    def _stage_airport_discovery(self) -> dict:
        """Run airport_metadata spider to discover all airports."""
        import subprocess

        result = subprocess.run(
            ["scrapy", "crawl", "airport_metadata"],
            check=False,
            capture_output=True,
            text=True,
        )
        success = result.returncode == 0

        session = SessionLocal()
        try:
            from database.models.aviation import AirportMetadata

            total = session.query(AirportMetadata).count()
        finally:
            session.close()

        if not success:
            logger.warning("[OPS] [AIRPORT_DISCOVERY] Failed: %s", result.stderr[-1000:])
        else:
            logger.warning(
                "[OPS] [AIRPORT_DISCOVERY] Done: total_airports=%d op=%s", total, self.operation_id
            )

        return {"success": success, "airports_in_db": total}

    def _stage_aviation_metadata(self) -> dict:
        """Run enrichment pass: alliances, airline sync, airport linking."""
        from scripts.bootstrap_aviation import seed_alliances, sync_airlines_to_metadata
        from database.models.aviation import AirlineMetadata, AirportMetadata, AirlineAirport

        session = SessionLocal()
        try:
            seed_alliances(session)
            sync_result = sync_airlines_to_metadata(session)

            airlines = session.query(AirlineMetadata).all()
            airports = session.query(AirportMetadata).all()

            linked = 0
            for am in airlines:
                for hub_code in am.hub_airports or []:
                    ap = session.query(AirportMetadata).filter_by(iata=hub_code.upper()).first()
                    if ap:
                        exists = (
                            session.query(AirlineAirport)
                            .filter_by(
                                airline_metadata_id=am.id,
                                airport_metadata_id=ap.id,
                            )
                            .first()
                        )
                        if not exists:
                            session.add(
                                AirlineAirport(
                                    airline_metadata_id=am.id,
                                    airport_metadata_id=ap.id,
                                    relationship_type="hub",
                                )
                            )
                            linked += 1

            session.commit()
            return {
                **sync_result,
                "airline_airport_links": linked,
                "airlines_total": len(airlines),
                "airports_total": len(airports),
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _stage_hub_intelligence(self) -> dict:
        """Compute hub intelligence from existing data."""
        from analytics.hub_intelligence import HubIntelligenceService

        session = SessionLocal()
        try:
            svc = HubIntelligenceService(session)
            dashboard = svc.hub_dashboard()
            rankings_count = len(svc.hub_rankings())
            risk_count = len(svc.hub_risk_matrix())
            incidents_count = len(svc.airport_incidents())

            return {
                "airports_monitored": dashboard.get("airports_monitored", 0),
                "active_hubs": dashboard.get("active_hubs", 0),
                "critical_hubs": dashboard.get("critical_hubs", 0),
                "rankings_computed": rankings_count,
                "risk_entries": risk_count,
                "incidents_detected": incidents_count,
            }
        finally:
            session.close()

    def _persist_run(self, elapsed_ms: int) -> None:
        from app.payload_serialization import safe_json_value
        from database.models.operations import OperationalRefreshRun

        session = SessionLocal()
        try:
            stage_results = safe_json_value(self.results)
            run = OperationalRefreshRun(
                operation_id=self.operation_id,
                started_at=self.started_at,
                finished_at=now_utc(),
                duration_ms=elapsed_ms,
                status="completed" if not self._blocking_errors() else "partial",
                reviews_processed=0,
                airlines_updated=self.results.get("aviation_metadata", {}).get("airlines_total", 0),
                anomalies_generated=0,
                forecasts_generated=0,
                semantic_updates=0,
                error_count=len(self.errors),
                warnings=[],
                triggered_by=self.triggered_by,
                stage_results=stage_results,
            )
            session.add(run)
            session.commit()
        except Exception as exc:
            logger.warning("persist_aviation_run_failed: %s", exc)
            session.rollback()
        finally:
            session.close()
