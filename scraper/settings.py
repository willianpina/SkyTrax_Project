from __future__ import annotations

import os

BOT_NAME = "airline_review_intelligence"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = int(os.getenv("SCRAPY_CONCURRENT_REQUESTS", "8"))
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv("SCRAPY_CONCURRENT_REQUESTS_PER_DOMAIN", "4"))
DOWNLOAD_DELAY = float(os.getenv("SCRAPY_DOWNLOAD_DELAY", "1.5"))
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "20"))
COOKIES_ENABLED = False
CLOSESPIDER_PAGECOUNT = int(os.getenv("SCRAPY_CLOSESPIDER_PAGECOUNT", "2000"))
CLOSESPIDER_ERRORCOUNT = int(os.getenv("SCRAPY_CLOSESPIDER_ERRORCOUNT", "50"))
CLOSESPIDER_TIMEOUT = int(os.getenv("SCRAPY_CLOSESPIDER_TIMEOUT", "600"))
DEPTH_LIMIT = int(os.getenv("SCRAPY_DEPTH_LIMIT", "25"))

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 12.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

RETRY_ENABLED = True
RETRY_TIMES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0 Safari/537.36",
]

DOWNLOADER_MIDDLEWARES = {
    "scraper.middlewares.RotatingUserAgentMiddleware": 400,
    "scraper.middlewares.AntiBanHeadersMiddleware": 410,
    "scraper.middlewares.SmartRetryMiddleware": 540,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
}

ITEM_PIPELINES = {
    "scraper.pipelines.scrapy_pipeline.FingerprintPipeline": 100,
    "scraper.pipelines.scrapy_pipeline.ValidationPipeline": 200,
    "scraper.pipelines.scrapy_pipeline.PostgresPersistencePipeline": 300,
}

EXTENSIONS = {
    "scraper.middlewares.SpiderStatsExtension": 500,
    "scraper.extensions.telemetry.LiveTelemetryExtension": 600,
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
FEEDS = {
    "exports/%(name)s/%(time)s.jsonl": {
        "format": "jsonlines",
        "encoding": "utf8",
        "overwrite": True,
    }
}
