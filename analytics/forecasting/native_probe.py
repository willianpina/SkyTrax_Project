"""Re-export for backwards compatibility — use app.native_health in new code."""

from app.native_health import (  # noqa: F401
    collect_native_health,
    probe_numpy_operation,
    probe_pandas_rolling,
    probe_scipy_operation,
)
