from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any


class TimedHeartbeat:
    """Emit heartbeat by wall-clock interval with semantic progress."""

    def __init__(
        self,
        heartbeat_fn: Callable[[str | dict[str, Any]], None] | None,
        *,
        stage: str,
        substage: str = "",
        interval_s: float = 25.0,
    ) -> None:
        self.heartbeat_fn = heartbeat_fn
        self.stage = stage
        self.substage = substage or stage
        self.interval_s = max(1.0, float(interval_s))
        self.started_at = time.perf_counter()
        self.last_pulse_at = 0.0
        self.pulse_count = 0

    def pulse_if_needed(
        self,
        *,
        detail: str | None = None,
        processed: int | None = None,
        total: int | None = None,
        current_substage: str | None = None,
        force: bool = False,
    ) -> bool:
        if not self.heartbeat_fn:
            return False
        now = time.perf_counter()
        if not force and self.last_pulse_at and (now - self.last_pulse_at) < self.interval_s:
            return False
        elapsed = max(now - self.started_at, 0.001)
        remaining = None
        if isinstance(total, int) and isinstance(processed, int):
            remaining = max(total - processed, 0)
        throughput = None
        if isinstance(processed, int):
            throughput = round(processed / elapsed, 2)
        payload = {
            "stage": self.stage,
            "detail": (detail or self.substage)[:120],
            "processed": processed,
            "remaining": remaining,
            "throughput_per_sec": throughput,
            "elapsed_s": int(elapsed),
            "current_substage": (current_substage or self.substage)[:80],
        }
        self.pulse_count += 1
        self.last_pulse_at = now
        self.heartbeat_fn(payload)
        return True


def heartbeat_guard(interval_s: float = 25.0):
    """Decorator that injects TimedHeartbeat in heavy stages."""

    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            hb_fn = kwargs.get("heartbeat_fn") or kwargs.get("heartbeat")
            stage = kwargs.get("stage", fn.__name__)
            timer = TimedHeartbeat(hb_fn, stage=stage, substage=fn.__name__, interval_s=interval_s)
            timer.pulse_if_needed(detail=f"{fn.__name__} started", force=True)
            result = fn(*args, **kwargs)
            timer.pulse_if_needed(detail=f"{fn.__name__} done", force=True)
            return result

        return _wrapped

    return _decorator
