from __future__ import annotations

from redis import Redis
from rq import Queue

from app.config import get_settings
from worker.jobs import run_scrapy_airlinequality


def enqueue_all(max_pages: int = 3) -> None:
    settings = get_settings()
    queue = Queue("default", connection=Redis.from_url(settings.redis_url))
    for slug in ("british-airways", "lufthansa", "emirates", "latam"):
        queue.enqueue(run_scrapy_airlinequality, slug, max_pages)


if __name__ == "__main__":
    enqueue_all()
