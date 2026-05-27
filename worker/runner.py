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
            from database.schema_health import log_schema_startup
            from database.session import engine

            auto = settings.schema_auto_migrate_dev and settings.environment == "development"
            log_schema_startup(engine, auto_migrate_dev=auto)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("[SCHEMA] Worker startup validation failed: %s", exc)

    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue("default", connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
