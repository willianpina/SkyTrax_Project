"""analytics.forecasting -- trend forecasting sub-package.

Re-exports preserve ``from analytics.forecasting import X`` compatibility.
"""

from analytics.forecasting.service import (  # noqa: F401
    METRICS,
    TrendForecastingService,
)

__all__ = ["METRICS", "TrendForecastingService"]
