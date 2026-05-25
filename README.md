# SkyTrax Airline Intelligence Platform

Enterprise analytics platform for airline customer experience, built around Scrapy-first data collection, NLP-powered intelligence pipelines, and a FastAPI analytical backend.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Architecture Overview

```text
+----------------+     +---------------------+     +----------------------+
|   Scrapy       |     |   PostgreSQL        |     |   NLP Pipeline       |
|   Spiders      +---->|   + pgvector        +---->|   sentiment, topics, |
|   (SkyTrax)    |     |   + Alembic         |     |   entities, embed.   |
+----------------+     +----------+----------+     +-----------+----------+
                                  |                             |
                                  v                             v
                       +----------+-----------------------------+----------+
                       |              Analytics / Intelligence              |
                       |  reputation | anomaly | forecast | benchmarking    |
                       |  insights   | trends  | clusters | data quality   |
                       +----------------------------+----------------------+
                                                    |
                                              +-----v------+
                                              |  FastAPI    |
                                              |  REST API   |
                                              +-----+------+
                                                    |
                                              +-----v------+
                                              |  React 18  |
                                              |  Dashboard |
                                              +------------+

Workers: Redis + RQ (crawl scheduling, NLP enrichment, snapshot generation)
Observability: Prometheus + Grafana + structured logging
```

## Key Features

- **Reputation Scoring** -- Composite Airline Reputation Score (ARS) with component breakdown
- **Anomaly Detection** -- Statistical detection of sentiment shifts and volume spikes
- **Trend Forecasting** -- EWMA and rolling-average forecasts with configurable horizons
- **Semantic Search** -- pgvector cosine similarity over sentence-transformer embeddings
- **Executive Intelligence** -- Auto-generated insight signals with severity and confidence
- **Competitive Benchmarking** -- Cross-airline metric comparison and ranking
- **Topic Trend Analysis** -- Temporal topic evolution tracking
- **RAG Context** -- Retrieval-augmented context endpoint for LLM integration
- **Data Quality Monitoring** -- Automated quality scans and reporting
- **Internationalization** -- English and Portuguese via i18next

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Frontend | React 18, Vite, ECharts, Tailwind CSS, i18next |
| Database | PostgreSQL + pgvector, HNSW indexing |
| Queue | Redis, RQ, scheduler with overlap locks |
| Collection | Scrapy, scrapy-playwright, BeautifulSoup4, trafilatura |
| NLP | spaCy, scikit-learn TF-IDF, sentence-transformers |
| Observability | Prometheus, Grafana, structured JSON logging |
| Infrastructure | Docker Compose, multi-stage Dockerfile, GitHub Actions CI |

## Quick Start

```bash
docker compose up --build
```

In another terminal, initialize the database and seed data:

```bash
docker compose exec app alembic upgrade head
docker compose exec app python scripts/seed_airlines.py
docker compose exec app scrapy crawl airlinequality_reviews -a max_pages=3
docker compose exec worker python -c \
  "from worker.jobs import enrich_pending_reviews; print(enrich_pending_reviews())"
```

### Services

| Service | URL |
|---|---|
| API root | `http://localhost:8000/` |
| API docs (Swagger) | `http://localhost:8000/docs` |
| Health check | `http://localhost:8000/health` |
| Prometheus metrics | `http://localhost:8000/metrics` |
| Dashboard | `http://localhost:5173` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

### Environment Variables

Runtime configuration is loaded from environment variables. Key settings:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://skytrax:skytrax@localhost:5432/skytrax` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `NLP_ENABLE_EMBEDDINGS` | `false` | Enable sentence-transformer embeddings |
| `NLP_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `SCHEDULER_ENABLED` | `true` | Enable background job scheduler |
| `CRAWL_MAX_PAGES` | `5` | Max pages per airline crawl |
| `API_RATE_LIMIT_PER_MINUTE` | `120` | API rate limit |
| `PRIORITY_AIRLINES` | `british-airways,emirates,...` | Comma-separated airline slugs |

See `app/config.py` for the full list of configuration options. Secrets can be provided through `_FILE` suffixed variables (e.g. `DATABASE_URL_FILE`) for Docker secrets support.

## Project Structure

```text
api/                  FastAPI application and route definitions
  routers/            Domain-specific route modules (reviews, analytics, intelligence, search, admin)
app/                  Application config, middleware, observability, tracing
analytics/            Analytics and intelligence engine layer
  intelligence/       Reputation scoring, benchmarking, topic trends
  forecasting/        Trend forecasting (EWMA, rolling averages)
  anomaly/            Statistical anomaly detection
  semantic/           Semantic search and review clustering
  quality/            Data quality monitoring, lineage, geospatial
  explainability/     Executive insights, copilot, explainability, snapshots
database/             SQLAlchemy models and session management
  models/             ORM models (core, analytics, intelligence, geo)
  migrations/         Alembic migration versions
nlp/                  NLP pipeline (sentiment, topics, entities, embeddings)
scraper/              Scrapy spiders, middlewares, airline seeds
  pipelines/          Scrapy item pipelines (validation, dedup, persistence)
  spiders/            Spider implementations
worker/               RQ job definitions, scheduler, runner
frontend/             React 18 + Vite dashboard
  src/components/     UI components (charts, command, panels, ui)
  src/hooks/          Data hooks (analytics, forecasting, anomalies, intelligence, benchmarking)
  src/lib/            Shared utilities (API client, chart configs, chart theme, metrics, feed)
  src/i18n/           Internationalization (en, pt -- 7 namespaces)
tests/                Pytest test suite
  unit/               Unit tests (fingerprinting, intelligence, forecasting)
  integration/        Integration tests (operational, PostGIS, scraping)
  api/                API contract tests
scripts/              Operational scripts (seed, enqueue, smoke test)
docs/                 Architecture, development, database, observability, production, roadmap
ops/                  Grafana dashboards, Prometheus config, alerting rules
```

## Development

```bash
make help              # Show all available targets
make dev               # Start all services (docker compose up --build)
make dev-down          # Stop all services
make test              # Run pytest with coverage
make lint              # Run ruff linter and format check
make format            # Auto-format with ruff
make migrate           # Apply pending Alembic migrations
make migrate-check     # Detect migration drift
make crawl             # Enqueue a scraping job
make seed              # Seed airline reference data
make smoke             # Run smoke tests against live env
make clean             # Remove caches and build artifacts
```

## Scrapy Operations

Run all seeded airlines:

```bash
scrapy crawl airlinequality_reviews -a max_pages=3
```

Run one airline:

```bash
scrapy crawl airlinequality_reviews -a airline=british-airways -a max_pages=5
```

Enable Playwright for dynamic pages:

```bash
scrapy crawl airlinequality_reviews -a airline=emirates -a use_playwright=true
```

The scraper includes auto-throttle, retry middleware, rotating user agents, structured item export, fingerprint deduplication, and PostgreSQL persistence. Local Scrapy exports are isolated by spider and run timestamp under `exports/%(name)s/%(time)s.jsonl`. Operational run metrics are persisted in `spider_runs`.

## API Endpoints

### Reviews and Data

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/airlines` | List all tracked airlines |
| `GET` | `/api/reviews` | Paginated reviews with NLP enrichment |
| `GET` | `/api/topics` | Topic snapshots by polarity and weight |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analytics` | Executive analytics summary |
| `GET` | `/api/rankings` | Airline rankings |
| `GET` | `/api/sentiment` | Sentiment distribution summary |
| `GET` | `/api/topic-trends` | Topic evolution over time |

### Intelligence

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/reputation` | Reputation scores for all airlines |
| `GET` | `/api/reputation/{slug}` | Single airline reputation score |
| `GET` | `/api/benchmarking` | Cross-airline benchmarking comparison |
| `GET` | `/api/insights` | Executive intelligence signals |
| `POST` | `/api/insights/refresh` | Regenerate executive insights |
| `GET` | `/api/snapshots` | Historical metric snapshots |

### Search and Retrieval

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/semantic-search` | Semantic similarity search over reviews |
| `GET` | `/api/semantic-clusters` | Semantic review clusters |
| `GET` | `/api/rag/context` | RAG-ready context for LLM queries |

### Forecasting and Anomalies

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/forecasting` | Forecasting portfolio summary |
| `GET` | `/api/forecasting/{slug}` | Airline-specific forecasts |
| `POST` | `/api/forecasting/refresh` | Regenerate forecasts |
| `GET` | `/api/anomalies` | Recent anomaly events |
| `GET` | `/api/anomalies/alerts` | Operational anomaly alerts |
| `POST` | `/api/anomalies/refresh` | Trigger anomaly detection |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/scheduler/status` | Background job scheduler status |
| `GET` | `/api/data-quality` | Data quality reports |
| `GET` | `/health` | Service health check |
| `GET` | `/metrics` | Prometheus-compatible metrics |

## Frontend Commands

```bash
make frontend-dev      # Run Vite dev server on port 5173
make frontend-build    # Production build
```

Or directly:

```bash
cd frontend
npm install
npm run dev            # Development server
npm run build          # Production build
npm run preview        # Preview production build
```

## Docker Operations

Development compose uses bind mounts and Vite dev server:

```bash
docker compose up --build
```

Production compose removes bind mounts, runs FastAPI through Gunicorn/Uvicorn workers, builds the frontend into Nginx, enables Redis append-only persistence, and keeps Playwright optional:

```bash
POSTGRES_PASSWORD=replace-me docker compose -f docker-compose.prod.yml up --build
```

All runtime services define healthchecks and `restart: unless-stopped`. App and worker wait for healthy PostgreSQL and Redis before startup.

Production secrets can be passed through Docker secrets. By default, `docker-compose.prod.yml` reads the database URL from `secrets/database_url.example`; set `DATABASE_URL_SECRET_FILE=./secrets/database_url.txt` for a real deployment.

### Lightweight Build Mode

Playwright browser installation is enabled by default. To skip browser installation during a fast backend-only build:

```bash
docker compose build --build-arg INSTALL_PLAYWRIGHT=false app worker
```

Scrapy still works for static pages without Playwright. Use `use_playwright=true` only for sources that need browser rendering.

## Observability

- `GET /metrics` exposes Prometheus-compatible API, DB, Redis, RQ, Scrapy, and worker gauges/counters.
- Prometheus scrapes the API, PostgreSQL exporter, and Redis exporter.
- Grafana provisions the `SkyTrax Enterprise Operations` dashboard automatically.
- Structured logs include request and trace IDs, service/module, spider, airline, duration, retry, and error fields.

## Mac Silicon Development

The default NLP stack is intentionally lightweight for Mac M1/M2/M3 and Docker ARM64:

- BERTopic, HDBSCAN, and UMAP are not installed by default.
- Torch is pinned to CPU wheels through the PyTorch CPU index.
- `NLP_ENABLE_EMBEDDINGS=false` keeps sentence-transformers from loading at worker startup.
- Topic extraction uses `TfidfVectorizer`, which is CPU-only and fast to build.

Enable embeddings only when needed:

```bash
NLP_ENABLE_EMBEDDINGS=true docker compose up --build
```

## CI/CD

GitHub Actions validates:

- Ruff linting
- Alembic upgrade and drift check
- Pytest with coverage gate
- Scrapy spider registration smoke test
- Docker Compose config and backend/frontend builds

## Troubleshooting

**Docker builds timeout:** Rebuild after pruning partial layers with `docker compose build --no-cache app worker`.

**Docker daemon not available:** Start Docker Desktop and verify with `docker compose config`.

**Torch issues:** This project is CPU-only by default. Do not add `torchvision`, `torchaudio`, BERTopic, HDBSCAN, or UMAP unless the environment is prepared for their native build requirements.

**Playwright failures:** Build without Playwright using `--build-arg INSTALL_PLAYWRIGHT=false`, then install later with `docker compose exec app playwright install --with-deps chromium`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/development.md)
- [ETL Flow](docs/etl_flow.md)
- [Database Structure](docs/database.md)
- [Observability](docs/observability.md)
- [Production Hardening](docs/production.md)
- [Roadmap](docs/roadmap.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
