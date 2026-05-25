from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.request_context import current_request_id, current_trace_id


class RequestContextFilter(logging.Filter):
    """Inject correlation fields into every structured log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or current_request_id()
        record.trace_id = getattr(record, "trace_id", None) or current_trace_id()
        record.service = getattr(record, "service", None)
        record.spider = getattr(record, "spider", None)
        record.airline = getattr(record, "airline", None)
        record.duration_ms = getattr(record, "duration_ms", None)
        record.retries = getattr(record, "retries", None)
        record.error_type = getattr(record, "error_type", None)
        record.module = getattr(record, "module", None)
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for application and workers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s %(service)s %(spider)s "
        "%(airline)s %(duration_ms)s %(request_id)s %(trace_id)s %(retries)s %(error_type)s "
        "%(pathname)s %(lineno)d"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
