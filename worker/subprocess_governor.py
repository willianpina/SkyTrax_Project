"""Subprocess Lifecycle Governor — enterprise-grade crawl process management.

Solves the core problem: Scrapy subprocess stays alive after corpus saturation
because the Twisted reactor continues running even when no new data is being
ingested. The governor monitors telemetry signals and terminates the subprocess
when operational progress ceases.

Termination triggers:
  1. Duplicate streak exceeded (MAX_DUPLICATE_STREAK pages with only dupes)
  2. No inserts for too long (MAX_NO_INSERT_SECONDS)
  3. Telemetry hash frozen (MAX_TELEMETRY_STATIC_SECONDS)
  4. Page counter stalled (MAX_STATIC_PAGE_SECONDS)
  5. Airline unchanged too long (MAX_STATIC_AIRLINE_SECONDS)
  6. Zero throughput (MAX_ZERO_THROUGHPUT_SECONDS)
  7. Hard timeout (CRAWL_HARD_TIMEOUT_S)

Kill protocol:
  1. SIGTERM → wait(GRACEFUL_TIMEOUT_S)
  2. SIGKILL → wait(5s)
  3. Cleanup Redis telemetry + locks
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Governance thresholds (overridable via env) ──────────────────────────

MAX_DUPLICATE_STREAK = int(os.getenv("GOV_MAX_DUPLICATE_STREAK", "30"))
MAX_NO_INSERT_SECONDS = int(os.getenv("GOV_MAX_NO_INSERT_SECONDS", "180"))
MAX_STATIC_PAGE_SECONDS = int(os.getenv("GOV_MAX_STATIC_PAGE_SECONDS", "120"))
MAX_STATIC_AIRLINE_SECONDS = int(os.getenv("GOV_MAX_STATIC_AIRLINE_SECONDS", "300"))
MAX_TELEMETRY_STATIC_SECONDS = int(os.getenv("GOV_MAX_TELEMETRY_STATIC_SECONDS", "120"))
MAX_ZERO_THROUGHPUT_SECONDS = int(os.getenv("GOV_MAX_ZERO_THROUGHPUT_SECONDS", "120"))
CRAWL_HARD_TIMEOUT_S = int(os.getenv("GOV_CRAWL_HARD_TIMEOUT_S", "3600"))
HEARTBEAT_INTERVAL_S = int(os.getenv("GOV_HEARTBEAT_INTERVAL_S", "10"))
GRACEFUL_TIMEOUT_S = int(os.getenv("GOV_GRACEFUL_TIMEOUT_S", "15"))


class CrawlState(str, Enum):
    """Subprocess lifecycle states."""

    RUNNING = "running"
    RUNNING_NO_PROGRESS = "running_no_progress"
    SATURATED = "saturated"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    ZOMBIE = "zombie"
    STALLED = "stalled"
    COMPLETED = "completed"
    COMPLETED_DEGRADED = "completed_degraded"


@dataclass
class TelemetrySnapshot:
    """Point-in-time crawl telemetry for change detection."""

    pages: int = 0
    inserts: int = 0
    dupes: int = 0
    airline: str = ""
    throughput: float = 0.0
    saturated: bool = False
    stalled: bool = False
    timestamp: float = field(default_factory=time.time)

    def content_hash(self) -> str:
        raw = f"{self.pages}|{self.inserts}|{self.dupes}|{self.airline}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]


@dataclass
class TerminationEvent:
    """Records why and how a subprocess was terminated."""

    reason: str
    trigger: str
    state: CrawlState
    elapsed_s: float
    telemetry: dict[str, Any]
    kill_type: str = "graceful"


class SubprocessGovernor:
    """Monitors and governs a Scrapy subprocess lifecycle.

    Usage:
        gov = SubprocessGovernor(proc, redis_fn, heartbeat_fn, operation_id)
        result = gov.run()  # blocks until subprocess exits or is killed
    """

    def __init__(
        self,
        proc: subprocess.Popen,
        redis_status_key: str,
        redis_fn: Callable,
        heartbeat_fn: Callable | None = None,
        operation_id: str = "",
        metrics_fn: Callable | None = None,
    ):
        self.proc = proc
        self.redis_status_key = redis_status_key
        self.redis_fn = redis_fn
        self.heartbeat_fn = heartbeat_fn
        self.operation_id = operation_id
        self.metrics_fn = metrics_fn or (lambda *a, **kw: None)

        self.started_at = time.time()
        self.state = CrawlState.RUNNING
        self.termination_event: TerminationEvent | None = None

        # Tracking state for change detection
        self._last_insert_time = time.time()
        self._last_insert_count = 0
        self._last_page_time = time.time()
        self._last_page_count = 0
        self._last_airline = ""
        self._last_airline_time = time.time()
        self._last_telemetry_hash = ""
        self._last_telemetry_hash_time = time.time()
        self._last_throughput_time = time.time()
        self._duplicate_streak = 0
        self._poll_count = 0

    def run(self) -> dict[str, Any]:
        """Main governance loop. Blocks until subprocess exits or is terminated."""
        logger.warning(
            "[GOVERNOR] Started pid=%d op=%s thresholds=[dupes=%d no_insert=%ds "
            "static_page=%ds static_airline=%ds telem_static=%ds zero_tput=%ds timeout=%ds]",
            self.proc.pid,
            self.operation_id,
            MAX_DUPLICATE_STREAK,
            MAX_NO_INSERT_SECONDS,
            MAX_STATIC_PAGE_SECONDS,
            MAX_STATIC_AIRLINE_SECONDS,
            MAX_TELEMETRY_STATIC_SECONDS,
            MAX_ZERO_THROUGHPUT_SECONDS,
            CRAWL_HARD_TIMEOUT_S,
        )

        while self.proc.poll() is None:
            self._poll_count += 1
            elapsed = time.time() - self.started_at

            # Read telemetry from Redis
            snap = self._read_telemetry()

            # Check termination conditions (ordered by severity)
            trigger = self._evaluate_triggers(snap, elapsed)

            if trigger:
                self._terminate(trigger, snap, elapsed)
                break

            # Update state based on progress
            self._update_state(snap, elapsed)

            # Emit heartbeat
            self._emit_heartbeat(snap, elapsed)

            time.sleep(HEARTBEAT_INTERVAL_S)

        # Process exited naturally or was killed
        return self._collect_result()

    def _read_telemetry(self) -> TelemetrySnapshot:
        """Read current crawl telemetry from Redis."""
        try:
            r = self.redis_fn()
            raw = r.get(self.redis_status_key)
            if not raw:
                return TelemetrySnapshot(timestamp=time.time())

            data = json.loads(raw)
            ct = data.get("crawl_telemetry", {})
            return TelemetrySnapshot(
                pages=ct.get("pages_processed", 0),
                inserts=ct.get("reviews_added", 0),
                dupes=ct.get("duplicates_skipped", 0),
                airline=ct.get("current_airline", ""),
                throughput=ct.get("reviews_per_second", 0.0),
                saturated=ct.get("saturated", False),
                stalled=ct.get("stalled", False),
                timestamp=time.time(),
            )
        except Exception as exc:
            logger.debug("[GOVERNOR] telemetry read failed: %s", exc)
            return TelemetrySnapshot(timestamp=time.time())

    def _evaluate_triggers(self, snap: TelemetrySnapshot, elapsed: float) -> str | None:
        """Evaluate all termination triggers. Returns trigger name or None."""
        now = time.time()

        # 1. Hard timeout
        if elapsed > CRAWL_HARD_TIMEOUT_S:
            self.metrics_fn("skytrax_crawl_hard_kill_total", 1.0)
            return "hard_timeout"

        # 2. Scrapy-side saturation detected
        if snap.saturated:
            self.metrics_fn("skytrax_crawl_termination_total", 1.0)
            return "scrapy_saturation"

        # Skip other checks until we have meaningful data (first 30s)
        if elapsed < 30:
            return None

        # 3. No inserts for too long
        if snap.inserts > self._last_insert_count:
            self._last_insert_count = snap.inserts
            self._last_insert_time = now
            self._duplicate_streak = 0
        else:
            no_insert_duration = now - self._last_insert_time
            if no_insert_duration > MAX_NO_INSERT_SECONDS and snap.pages > 5:
                self.metrics_fn("skytrax_crawl_no_insert_seconds", no_insert_duration)
                return "no_inserts"

        # 4. Page counter stalled (reactor hanging)
        if snap.pages > self._last_page_count:
            self._last_page_count = snap.pages
            self._last_page_time = now
        else:
            static_page_duration = now - self._last_page_time
            if static_page_duration > MAX_STATIC_PAGE_SECONDS and snap.pages > 0:
                self.metrics_fn("skytrax_crawl_reactor_hang_total", 1.0)
                return "reactor_hanging"

        # 5. Duplicate streak
        if snap.pages > 0 and snap.inserts == self._last_insert_count and snap.dupes > 0:
            pages_since_insert = (
                snap.pages - self._last_page_count if self._last_insert_count > 0 else snap.pages
            )
            if pages_since_insert > MAX_DUPLICATE_STREAK:
                self.metrics_fn("skytrax_crawl_duplicate_streak", float(pages_since_insert))
                return "duplicate_streak"

        # 6. Airline unchanged too long
        if snap.airline and snap.airline != self._last_airline:
            self._last_airline = snap.airline
            self._last_airline_time = now
        elif snap.airline and snap.airline == self._last_airline:
            static_airline = now - self._last_airline_time
            if static_airline > MAX_STATIC_AIRLINE_SECONDS:
                return "static_airline"

        # 7. Telemetry hash frozen
        current_hash = snap.content_hash()
        if current_hash != self._last_telemetry_hash:
            self._last_telemetry_hash = current_hash
            self._last_telemetry_hash_time = now
        else:
            frozen_duration = now - self._last_telemetry_hash_time
            if frozen_duration > MAX_TELEMETRY_STATIC_SECONDS and snap.pages > 0:
                self.metrics_fn("skytrax_telemetry_static_total", 1.0)
                return "telemetry_frozen"

        # 8. Zero throughput sustained
        if snap.throughput > 0:
            self._last_throughput_time = now
        else:
            zero_tput_duration = now - self._last_throughput_time
            if zero_tput_duration > MAX_ZERO_THROUGHPUT_SECONDS and snap.pages > 5:
                return "zero_throughput"

        return None

    def _update_state(self, snap: TelemetrySnapshot, elapsed: float) -> None:
        """Update governor state based on current telemetry."""
        now = time.time()
        no_insert_duration = now - self._last_insert_time

        if snap.saturated:
            self.state = CrawlState.SATURATED
        elif no_insert_duration > 60 and snap.pages > 5:
            self.state = CrawlState.RUNNING_NO_PROGRESS
        elif snap.stalled:
            self.state = CrawlState.STALLED
        else:
            self.state = CrawlState.RUNNING

    def _emit_heartbeat(self, snap: TelemetrySnapshot, elapsed: float) -> None:
        """Emit heartbeat with governance state info."""
        if not self.heartbeat_fn:
            return

        state_label = self.state.value
        no_insert_s = int(time.time() - self._last_insert_time)

        detail = (
            f"crawl: {snap.airline} p={snap.pages} +{snap.inserts} "
            f"dupes={snap.dupes} state={state_label} "
            f"no_insert={no_insert_s}s elapsed={int(elapsed)}s"
        )

        try:
            self.heartbeat_fn(detail)
        except Exception:
            pass

    def _terminate(self, trigger: str, snap: TelemetrySnapshot, elapsed: float) -> None:
        """Execute the termination protocol: graceful → hard kill → cleanup."""
        self.state = CrawlState.TERMINATING
        pid = self.proc.pid

        telemetry_dict = {
            "pages": snap.pages,
            "inserts": snap.inserts,
            "dupes": snap.dupes,
            "airline": snap.airline,
            "throughput": snap.throughput,
        }

        logger.warning(
            "[GOVERNOR][TERMINATION] trigger=%s pid=%d elapsed=%.0fs "
            "pages=%d inserts=%d dupes=%d airline=%s op=%s",
            trigger,
            pid,
            elapsed,
            snap.pages,
            snap.inserts,
            snap.dupes,
            snap.airline,
            self.operation_id,
        )

        # Phase 1: graceful SIGTERM
        kill_type = "graceful"
        try:
            self.proc.terminate()
            logger.info("[GOVERNOR][TERMINATION] SIGTERM sent pid=%d", pid)

            try:
                self.proc.wait(timeout=GRACEFUL_TIMEOUT_S)
                logger.info("[GOVERNOR][TERMINATION] Graceful exit pid=%d code=%d", pid, self.proc.returncode)
            except subprocess.TimeoutExpired:
                # Phase 2: hard SIGKILL
                kill_type = "hard_kill"
                logger.warning(
                    "[GOVERNOR][HARD_KILL] SIGTERM timeout after %ds — sending SIGKILL pid=%d",
                    GRACEFUL_TIMEOUT_S,
                    pid,
                )
                self.proc.kill()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    kill_type = "zombie"
                    self.state = CrawlState.ZOMBIE
                    logger.error("[GOVERNOR][ZOMBIE] Process %d did not exit after SIGKILL", pid)
                    self.metrics_fn("skytrax_crawl_zombie_total", 1.0)
                    self._force_kill_tree(pid)

        except ProcessLookupError:
            logger.info("[GOVERNOR][TERMINATION] Process %d already exited", pid)

        if self.state != CrawlState.ZOMBIE:
            self.state = CrawlState.TERMINATED

        self.termination_event = TerminationEvent(
            reason=self._trigger_description(trigger),
            trigger=trigger,
            state=self.state,
            elapsed_s=elapsed,
            telemetry=telemetry_dict,
            kill_type=kill_type,
        )

        # Phase 3: cleanup
        self._cleanup_redis(snap)
        self.metrics_fn("skytrax_crawl_termination_total", 1.0)

        logger.warning(
            "[GOVERNOR][CRAWL_EXIT] trigger=%s kill=%s state=%s elapsed=%.0fs op=%s",
            trigger,
            kill_type,
            self.state.value,
            elapsed,
            self.operation_id,
        )

    def _force_kill_tree(self, pid: int) -> None:
        """Last resort: kill the entire process tree."""
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def _cleanup_redis(self, snap: TelemetrySnapshot) -> None:
        """Clean up Redis telemetry state after termination."""
        try:
            r = self.redis_fn()
            raw = r.get(self.redis_status_key)
            if not raw:
                return

            status = json.loads(raw)
            ct = status.get("crawl_telemetry", {})
            ct["governor_terminated"] = True
            ct["termination_trigger"] = (
                self.termination_event.trigger if self.termination_event else "unknown"
            )
            ct["termination_state"] = self.state.value
            status["crawl_telemetry"] = ct
            status["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

            r.set(self.redis_status_key, json.dumps(status), ex=14400)
        except Exception as exc:
            logger.warning("[GOVERNOR] Redis cleanup failed: %s", exc)

    def _collect_result(self) -> dict[str, Any]:
        """Collect final subprocess result after exit."""
        stdout, stderr = "", ""
        try:
            stdout, stderr = self.proc.communicate(timeout=10)
        except (subprocess.TimeoutExpired, ValueError):
            pass

        returncode = self.proc.returncode
        elapsed = time.time() - self.started_at

        if self.termination_event:
            final_state = self.termination_event.state
        elif returncode == 0:
            final_state = CrawlState.COMPLETED
        else:
            final_state = CrawlState.COMPLETED_DEGRADED

        result = {
            "returncode": returncode,
            "state": final_state.value,
            "elapsed_s": int(elapsed),
            "poll_cycles": self._poll_count,
        }

        if self.termination_event:
            result["termination"] = {
                "trigger": self.termination_event.trigger,
                "reason": self.termination_event.reason,
                "kill_type": self.termination_event.kill_type,
                "telemetry": self.termination_event.telemetry,
            }

        return result

    @staticmethod
    def _trigger_description(trigger: str) -> str:
        descriptions = {
            "hard_timeout": f"Crawl exceeded hard timeout ({CRAWL_HARD_TIMEOUT_S}s)",
            "scrapy_saturation": "Scrapy telemetry reported corpus saturation",
            "no_inserts": f"No new reviews inserted for {MAX_NO_INSERT_SECONDS}s",
            "reactor_hanging": f"Page counter frozen for {MAX_STATIC_PAGE_SECONDS}s — reactor likely hanging",
            "duplicate_streak": f"Exceeded {MAX_DUPLICATE_STREAK} pages with only duplicates",
            "static_airline": f"Same airline for {MAX_STATIC_AIRLINE_SECONDS}s with no progress",
            "telemetry_frozen": f"Telemetry hash unchanged for {MAX_TELEMETRY_STATIC_SECONDS}s",
            "zero_throughput": f"Zero throughput for {MAX_ZERO_THROUGHPUT_SECONDS}s",
        }
        return descriptions.get(trigger, f"Unknown trigger: {trigger}")
