from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger


logger = getLogger(__name__)


@dataclass(frozen=True)
class TracingStatus:
    enabled: bool
    provider: str


def configure_tracing(service_name: str = "skytrax-api") -> TracingStatus:
    """Prepare optional OpenTelemetry wiring without making it a runtime requirement."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        trace.set_tracer_provider(provider)
        return TracingStatus(enabled=True, provider="opentelemetry")
    except Exception as exc:
        logger.info(
            "opentelemetry_unavailable",
            extra={"service": service_name, "error_type": exc.__class__.__name__},
        )
        return TracingStatus(enabled=False, provider="noop")
