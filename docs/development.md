# Development Guide

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| Docker + Docker Compose | Latest | Container orchestration |
| Python | 3.11+ | Backend, analytics, NLP, scraping |
| Node.js | 20+ | Frontend build and development |
| Git | Latest | Version control |

Python and Node.js are only required for local (non-Docker) development. The Docker Compose setup includes all runtime dependencies.

## Local Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd SkyTrax_Project
```

### 2. Start All Services

```bash
make dev
```

This runs `docker compose up --build`, which starts:

- **app** -- FastAPI backend (port 8000)
- **worker** -- RQ worker for background jobs
- **db** -- PostgreSQL with pgvector (port 5432)
- **redis** -- Redis (port 6379)
- **frontend** -- Vite dev server (port 5173)
- **prometheus** -- Metrics collection (port 9090)
- **grafana** -- Dashboards (port 3000)

### 3. Initialize the Database

```bash
docker compose exec app alembic upgrade head
```

### 4. Seed Reference Data

```bash
docker compose exec app python scripts/seed_airlines.py
```

### 5. Run an Initial Crawl

```bash
docker compose exec app scrapy crawl airlinequality_reviews -a max_pages=3
```

### 6. Run NLP Enrichment

```bash
docker compose exec worker python -c \
  "from worker.jobs import enrich_pending_reviews; print(enrich_pending_reviews())"
```

### 7. Verify

- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:5173`

## Environment Variables

Runtime configuration is centralized in `app/config.py` via a frozen `Settings` dataclass. All settings are loaded from environment variables with sensible defaults.

Create a `.env` file in the project root to override defaults. Key variables:

```bash
# Database
DATABASE_URL=postgresql+psycopg://skytrax:skytrax@db:5432/skytrax
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis:6379/0

# API
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
API_RATE_LIMIT_PER_MINUTE=120
API_REQUEST_TIMEOUT_SECONDS=30

# NLP
NLP_ENABLE_EMBEDDINGS=false
NLP_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Scraping
CRAWL_MAX_PAGES=5
SCRAPE_RATE_LIMIT_SECONDS=2.0
PRIORITY_AIRLINES=british-airways,emirates,qatar-airways,lufthansa,latam-airlines

# Scheduler
SCHEDULER_ENABLED=true
CRAWL_INTERVAL_HOURS=6
NLP_INTERVAL_MINUTES=30
INSIGHTS_INTERVAL_HOURS=4
FORECAST_INTERVAL_HOURS=4
ANOMALY_INTERVAL_HOURS=2

# Observability
LOG_LEVEL=INFO
APP_ENV=development
```

For production, secrets can be provided through Docker secrets using the `_FILE` suffix convention (e.g. `DATABASE_URL_FILE=/run/secrets/database_url`).

## Running Services

### Start Everything

```bash
make dev
```

### Stop Everything

```bash
make dev-down
```

### Rebuild Images

```bash
make build
```

### Run Frontend Only

```bash
make frontend-dev
```

Or without Docker:

```bash
cd frontend
npm install
npm run dev
```

### Lightweight Backend Build

Skip Playwright browser installation for faster builds:

```bash
docker compose build --build-arg INSTALL_PLAYWRIGHT=false app worker
```

## Running Tests

```bash
make test
```

This runs `pytest` inside the API container with coverage for `api`, `analytics`, and `worker` packages:

```bash
docker compose run --rm api pytest --cov=api --cov=analytics --cov=worker -v
```

### Smoke Tests

Run smoke tests against a live environment:

```bash
make smoke
```

## Code Style

### Python

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
make lint       # Check linting and formatting
make format     # Auto-format code
```

Or directly:

```bash
ruff check .
ruff format .
```

### Frontend

The frontend uses standard Vite/React conventions with Tailwind CSS for styling. ESLint can be configured per team preference.

### Commit Conventions

Follow the patterns established in the repository. Keep commits focused and descriptive. See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

## Making Changes

### Backend Changes

1. Create or modify code in the relevant module (`api/`, `analytics/`, `nlp/`, `worker/`).
2. If the change touches the database schema, create a migration:
   ```bash
   docker compose exec app alembic revision --autogenerate -m "description"
   docker compose exec app alembic upgrade head
   ```
3. Run linting: `make lint`
4. Run tests: `make test`
5. Verify the migration is clean: `make migrate-check`

### Frontend Changes

1. Modify components in `frontend/src/`.
2. The Vite dev server hot-reloads changes automatically.
3. For new translations, update `frontend/src/i18n/en/` and `frontend/src/i18n/pt/`.
4. Build and verify: `npm run build && npm run preview`

### Adding a New API Endpoint

1. Define Pydantic schemas in `api/schemas.py`.
2. Create or extend a router in `api/routers/`.
3. Register the router in `api/routes.py` or `api/main.py`.
4. Implement business logic in the appropriate service class under `analytics/`.
5. Add tests covering the endpoint.

### Adding a New Worker Job

1. Define the job function in `worker/jobs.py`.
2. Wrap execution with `_with_lock()` for overlap protection.
3. Register the job in the scheduler configuration.
4. Add Prometheus metrics via `record_worker_metric()`.

## Troubleshooting

### Docker builds timeout

Rebuild without cached layers:

```bash
docker compose build --no-cache app worker
```

### Docker daemon not available

Start Docker Desktop and verify:

```bash
docker compose config
```

### Database migration drift

Check for unapplied or divergent migrations:

```bash
make migrate-check
```

If drift is detected, generate a new migration:

```bash
docker compose exec app alembic revision --autogenerate -m "fix drift"
docker compose exec app alembic upgrade head
```

### Port conflicts

If default ports are in use, override them in your `.env` or `docker-compose.override.yml`.

### Mac Silicon / ARM64 issues

- BERTopic, HDBSCAN, and UMAP are excluded by default to avoid native build failures.
- Torch is pinned to CPU-only wheels.
- Keep `NLP_ENABLE_EMBEDDINGS=false` unless embeddings are needed.
- Do not add `torchvision` or `torchaudio` unless the environment supports them.

### Playwright failures

Build without Playwright and install later:

```bash
docker compose build --build-arg INSTALL_PLAYWRIGHT=false app worker
docker compose exec app playwright install --with-deps chromium
```

### Redis connection refused

Ensure Redis is running and healthy:

```bash
docker compose ps redis
docker compose logs redis
```

### NLP enrichment not processing

Verify there are un-enriched reviews and the worker is running:

```bash
docker compose ps worker
docker compose logs worker --tail 50
```
