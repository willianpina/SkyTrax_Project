# Observability

The current platform emits structured JSON logs, exposes Prometheus metrics and persists Scrapy run summaries in `spider_runs`.

## Current Signals

- API logs include `service`, `level`, `path`, `error_type` and source location.
- Scrapy logs include `service`, `spider`, `airline`, `duration_ms`, retries and error counters when available.
- `spider_runs` stores spider name, status, pages crawled, items scraped, errors, start time and finish time.
- Docker healthchecks cover app, worker, PostgreSQL, Redis and frontend.
- `/metrics` exposes API latency/throughput, DB query timing, Redis availability, RQ queue size, review counts and latest spider run metrics.
- Prometheus scrapes API, PostgreSQL exporter and Redis exporter.
- Grafana provisions the `SkyTrax Enterprise Operations` dashboard.

## Recommended Next Layer

- OpenTelemetry: distributed traces across API requests, RQ jobs and database calls.
- Alerting: trigger reputation and operations alerts when crawl failure rate, negative sentiment or API latency crosses thresholds.

## Production Metrics To Add

- `scrapy_items_scraped_total`
- `scrapy_spider_duration_seconds`
- `scrapy_spider_errors_total`
- `rq_queue_depth`
- `rq_job_failures_total`
- `api_request_duration_seconds`
- `database_pool_checked_out`
- `nlp_reviews_processed_total`
