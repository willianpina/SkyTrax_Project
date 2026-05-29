"""Canonical pipeline operational status enum."""

from __future__ import annotations

from enum import Enum


class PipelineStatus(str, Enum):
    """Formal pipeline status labels exposed to API/UI."""

    STARTING = "starting"
    RUNNING = "running"
    RUNNING_DEGRADED = "running_degraded"
    RUNNING_SLOW = "running_slow"
    FINALIZING = "finalizing"
    PERSISTING = "persisting"
    STALLED = "stalled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    COMPLETED_DEGRADED = "completed_degraded"
    RECOVERING = "recovering"
    IDLE = "idle"
    BUSY_WITHOUT_HEARTBEAT = "busy_without_heartbeat"


TERMINAL_PIPELINE_STATUSES = frozenset(
    {
        PipelineStatus.STALLED,
        PipelineStatus.FAILED,
        PipelineStatus.CANCELLED,
        PipelineStatus.COMPLETED,
        PipelineStatus.COMPLETED_DEGRADED,
        PipelineStatus.IDLE,
    }
)

ACTIVE_PIPELINE_STATUSES = frozenset(
    {
        PipelineStatus.STARTING,
        PipelineStatus.RUNNING,
        PipelineStatus.RUNNING_DEGRADED,
        PipelineStatus.RUNNING_SLOW,
        PipelineStatus.FINALIZING,
        PipelineStatus.PERSISTING,
        PipelineStatus.RECOVERING,
        PipelineStatus.BUSY_WITHOUT_HEARTBEAT,
    }
)
