from __future__ import annotations

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.logging_config import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue("default", connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
