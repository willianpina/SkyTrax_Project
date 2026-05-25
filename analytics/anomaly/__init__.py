"""analytics.anomaly -- anomaly detection sub-package.

Re-exports preserve ``from analytics.anomaly import X`` compatibility.
"""

from analytics.anomaly.detector import AnomalyDetectionService  # noqa: F401

__all__ = ["AnomalyDetectionService"]
