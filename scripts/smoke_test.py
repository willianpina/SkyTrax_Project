from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from database.session import engine


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"{url} returned {response.status}")
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    settings = get_settings()
    api_base = os.getenv("API_BASE", "http://localhost:8000")
    checks = {
        "api_health": lambda: _get_json(f"{api_base}/health")["status"] == "online",
        "db": lambda: engine.connect().execute(text("select 1")).scalar_one() == 1,
        "redis": lambda: Redis.from_url(settings.redis_url).ping(),
        "scrapy_spider_registered": lambda: (
            "airlinequality_reviews" in subprocess.check_output(["scrapy", "list"], text=True)
        ),
    }
    failed: list[str] = []
    for name, check in checks.items():
        try:
            if not check():
                failed.append(name)
        except Exception as exc:
            print(f"{name}: FAIL ({exc})")
            failed.append(name)
        else:
            print(f"{name}: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
