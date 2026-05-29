"""Isolated forecasting execution — prevents native segfaults from killing the RQ worker.

RQ workers fork after loading heavy libs (sklearn/spacy). OpenBLAS + fork on Apple Silicon
often causes SIGSEGV (signal 11) during forecasting. This module runs forecasting in a
spawned child process and falls back to SafeTrendForecastingService on failure.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

FORECAST_SUBPROCESS_TIMEOUT_S = int(os.getenv("FORECAST_SUBPROCESS_TIMEOUT_S", "600"))


def _exit_signal(exitcode: int | None) -> int | None:
    if exitcode is None:
        return None
    if exitcode < 0:
        return -exitcode
    if exitcode > 128:
        return exitcode - 128
    return None


def _forecast_worker(result_queue: multiprocessing.Queue, safe_mode: bool) -> None:
    """Child entrypoint — must not import heavy libs before this process starts."""
    try:
        from database.session import SessionLocal

        session = SessionLocal()
        try:
            if safe_mode:
                from analytics.forecasting.safe_service import SafeTrendForecastingService

                svc = SafeTrendForecastingService(session)
            else:
                from analytics.forecasting import TrendForecastingService

                svc = TrendForecastingService(session)
            result = svc.generate_and_persist()
            result_queue.put({"status": "ok", "result": result})
        finally:
            session.close()
    except Exception as exc:
        result_queue.put({"status": "error", "error": str(exc), "error_type": type(exc).__name__})


def run_forecasting_isolated(
    *,
    safe_mode: bool | None = None,
    heartbeat_fn: Callable | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Run forecasting in an isolated subprocess; never raises to caller."""
    from app.runtime_state import (
        activate_forecast_safe_mode,
        is_forecast_safe_mode,
        is_subprocess_cooldown_active,
        record_subprocess_crash,
    )

    if is_subprocess_cooldown_active():
        logger.warning("[FORECAST_NATIVE] Subprocess cooldown active — safe mode in-process")
        return _run_forecasting_inprocess(safe_mode=True, heartbeat_fn=heartbeat_fn)

    if safe_mode is None:
        safe_mode = is_forecast_safe_mode()

    isolated = os.getenv("FORECAST_ISOLATED", "1").lower() in ("1", "true", "yes")
    timeout = timeout_s or FORECAST_SUBPROCESS_TIMEOUT_S

    if heartbeat_fn:
        try:
            heartbeat_fn("forecasting: preparing isolated run")
        except Exception:
            pass

    if not isolated:
        return _run_forecasting_inprocess(safe_mode=safe_mode, heartbeat_fn=heartbeat_fn)

    logger.warning(
        "[FORECAST_NATIVE] Isolated subprocess safe_mode=%s timeout=%ds",
        safe_mode,
        timeout,
    )

    ctx = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue = ctx.Queue()
    proc = ctx.Process(target=_forecast_worker, args=(result_queue, safe_mode), daemon=True)
    proc.start()
    proc.join(timeout)

    if proc.is_alive():
        logger.error("[FORECAST_NATIVE] Subprocess timeout after %ds — terminating", timeout)
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join(2)
        return _fallback_safe("subprocess_timeout", heartbeat_fn=heartbeat_fn)

    signal = _exit_signal(proc.exitcode)
    if signal == 11:
        logger.error(
            "[SEGFAULT] [WORKHORSE_CRASH] Forecasting child SIGSEGV (signal 11) exitcode=%s",
            proc.exitcode,
        )
        record_subprocess_crash("forecasting")
        activate_forecast_safe_mode("segfault_signal_11")
        return _fallback_safe("segfault_signal_11", heartbeat_fn=heartbeat_fn, native_crash=True)

    if proc.exitcode not in (0, None) and signal:
        logger.error(
            "[WORKHORSE_CRASH] Forecasting child killed signal=%s exitcode=%s",
            signal,
            proc.exitcode,
        )
        record_subprocess_crash("forecasting")
        return _fallback_safe(f"signal_{signal}", heartbeat_fn=heartbeat_fn, native_crash=True)

    if proc.exitcode != 0:
        logger.error("[FORECAST_NATIVE] Subprocess failed exitcode=%s", proc.exitcode)
        return _fallback_safe(f"exit_{proc.exitcode}", heartbeat_fn=heartbeat_fn)

    try:
        payload = result_queue.get_nowait()
    except Exception:
        logger.error("[FORECAST_NATIVE] No result from child queue")
        return _fallback_safe("empty_result", heartbeat_fn=heartbeat_fn)

    if payload.get("status") == "ok":
        result = payload.get("result") or {}
        result["isolation"] = "subprocess"
        result["safe_mode"] = safe_mode
        return result

    logger.warning(
        "[FORECAST_NATIVE] Child error: %s",
        payload.get("error"),
    )
    return _fallback_safe(
        payload.get("error_type", "child_error"),
        heartbeat_fn=heartbeat_fn,
        child_error=payload.get("error"),
    )


def _run_forecasting_inprocess(
    *,
    safe_mode: bool,
    heartbeat_fn: Callable | None,
) -> dict[str, Any]:
    """In-process forecasting with exception shielding."""
    try:
        from database.session import SessionLocal

        session = SessionLocal()
        try:
            if safe_mode:
                from analytics.forecasting.safe_service import SafeTrendForecastingService

                svc = SafeTrendForecastingService(session)
            else:
                from analytics.forecasting import TrendForecastingService

                svc = TrendForecastingService(session)
            if heartbeat_fn:
                heartbeat_fn("forecasting: in-process run")
            result = svc.generate_and_persist(heartbeat_fn=heartbeat_fn)
            result["isolation"] = "inprocess"
            result["safe_mode"] = safe_mode
            return result
        finally:
            session.close()
    except Exception as exc:
        logger.exception("[FORECAST_NATIVE] In-process forecasting failed: %s", exc)
        return _fallback_safe(str(exc), heartbeat_fn=heartbeat_fn)


def _fallback_safe(
    reason: str,
    *,
    heartbeat_fn: Callable | None,
    native_crash: bool = False,
    child_error: str | None = None,
) -> dict[str, Any]:
    """Last-resort safe mode in parent process (stdlib-only path)."""
    logger.warning(
        "[FORECAST_NATIVE] Falling back to safe mode reason=%s native_crash=%s",
        reason,
        native_crash,
    )
    if native_crash:
        try:
            from app.observability import record_worker_metric

            record_worker_metric("skytrax_forecast_segfault_total", 1.0)
            record_worker_metric("skytrax_forecast_native_crash_total", 1.0)
        except Exception:
            pass

    try:
        result = _run_forecasting_inprocess(safe_mode=True, heartbeat_fn=heartbeat_fn)
        result["fallback_reason"] = reason
        result["native_crash"] = native_crash
        if child_error:
            result["child_error"] = child_error[:200]
        if native_crash:
            result["error"] = f"native_crash:{reason}"
        return result
    except Exception as exc:
        logger.exception("[FORECAST_NATIVE] Safe fallback also failed: %s", exc)
        return {
            "forecasts_persisted": 0,
            "error": str(exc),
            "fallback_reason": reason,
            "native_crash": native_crash,
            "mode": "failed",
        }


def run_forecasting_stage(heartbeat_fn: Callable | None = None) -> dict[str, Any]:
    """Pipeline entry — always returns a dict (fail-soft)."""
    return run_forecasting_isolated(heartbeat_fn=heartbeat_fn)
