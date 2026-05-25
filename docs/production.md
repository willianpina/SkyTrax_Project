# Production Hardening

## Runtime

- Use `docker-compose.prod.yml` for production-like deployments.
- Provide `DATABASE_URL_SECRET_FILE=./secrets/database_url.txt`.
- Set `POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `API_TRUSTED_HOSTS` and `API_CORS_ORIGINS` explicitly.
- Keep `NLP_ENABLE_EMBEDDINGS=false` unless the host has enough CPU/RAM for embedding generation.

## Security

- FastAPI enables trusted host checks, restrictive CORS via environment, GZip, request size limits, timeout middleware, rate limiting and security headers.
- Logs expose correlation IDs without leaking stack traces to API consumers.
- Scrapy uses randomized delay, AutoThrottle, retry handling, browser-like headers and close-spider limits.
- Do not expose PostgreSQL or Redis ports in a public environment.

## Database Operations

- Run `alembic upgrade head` before app rollout.
- Keep `ENABLE_POSTGIS=false` on `pgvector/pgvector` images unless PostGIS is installed. Migrations continue in lightweight geospatial mode (lat/lon only). Set `ENABLE_POSTGIS=true` only when using a PostGIS-enabled PostgreSQL image.
- Run `alembic check` in CI to detect SQLAlchemy/migration drift.
- Schedule daily PostgreSQL backups with `pg_dump`.
- Run periodic `VACUUM ANALYZE` for `reviews`, `nlp_results`, `topic_snapshots` and `spider_runs`.
- Monitor index bloat and query plans for `ix_reviews_airline_date`, `ix_reviews_rating`, `ix_nlp_results_sentiment_label` and `ix_nlp_results_embedding_hnsw`.

## AI / Semantic Readiness

- `nlp_results.embedding` is pgvector-backed and has an HNSW cosine index.
- `/api/semantic-search` provides retrieval fallback without requiring embeddings.
- `/api/rag/context` returns source-grounded chunks for future LLM context builders.
- Rule-based `/api/insights` can be replaced or augmented by LLM generation later.

## Release Gate

- CI lint, tests, coverage, migration validation and Docker builds must pass.
- Smoke tests must confirm API health, DB connection, Redis ping and Scrapy registration.
- Prometheus targets must be `up` for API, PostgreSQL and Redis.
