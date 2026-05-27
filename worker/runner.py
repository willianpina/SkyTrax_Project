from __future__ import annotations

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.logging_config import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.schema_validate_on_startup:
        try:
            from app.startup_governance import (
                StartupBlockedError,
                log_startup_summary,
                run_startup_governance,
            )
            from database.session import engine

            report = run_startup_governance(engine, service="worker")
            log_startup_summary(report)
        except StartupBlockedError as exc:
            import logging
            logging.getLogger(__name__).critical("[SCHEMA] Worker startup blocked: %s", exc)
            raise SystemExit(1) from exc
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("[SCHEMA] Worker startup validation failed: %s", exc)

    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue("default", connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
