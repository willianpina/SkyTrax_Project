from __future__ import annotations

import json
from logging import getLogger
from urllib.request import Request, urlopen

from app.config import get_settings

logger = getLogger(__name__)


def emit_alert(event: str, payload: dict, severity: str = "warning") -> None:
    """Webhook-ready alert dispatcher for operational events."""
    settings = get_settings()
    body = {"event": event, "severity": severity, "payload": payload}
    logger.warning("operational_alert", extra=body)
    if not settings.alert_webhook_url:
        return
    try:
        request = Request(
            settings.alert_webhook_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(request, timeout=5)
    except Exception as exc:
        logger.error("alert_webhook_failed", extra={"error": str(exc), "event": event})
