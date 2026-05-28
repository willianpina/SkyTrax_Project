# ──────────────────────────────────────────────────────────────────────
# SkyTrax Airline Intelligence Platform — Developer Makefile
#
# Stack: Python 3.11+, FastAPI, Scrapy, PostgreSQL, Redis,
#        Docker Compose, Alembic, pytest, ruff, React/Vite
#
# Usage:  make <target>          (run `make help` for all targets)
# ──────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help dev dev-down build test lint format migrate migrate-check \
        crawl seed frontend-build frontend-dev healthcheck clean smoke \
        forecast anomalies semantic observability logs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Services ──────────────────────────────────────────────────────────

dev: ## Start all services (build if needed)
	$(COMPOSE) up --build

dev-down: ## Stop and remove all services
	$(COMPOSE) down

build: ## Build all Docker images
	$(COMPOSE) build

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=50

# ── Backend ───────────────────────────────────────────────────────────

test: ## Run pytest with coverage
	$(COMPOSE) run --rm app pytest --cov=api --cov=analytics --cov=worker -v

lint: ## Run ruff linter and format check
	ruff check .
	ruff format --check .

format: ## Auto-format code with ruff
	ruff format .

migrate: ## Apply all pending Alembic migrations
	$(COMPOSE) exec app alembic upgrade head

migrate-check: ## Detect migration drift
	$(COMPOSE) exec app alembic check

# ── Data Pipeline ─────────────────────────────────────────────────────

crawl: ## Enqueue a scraping job
	$(COMPOSE) exec app python scripts/enqueue_scrape.py

seed: ## Seed airline reference data
	$(COMPOSE) exec app python scripts/seed_airlines.py

forecast: ## Trigger forecast generation
	$(COMPOSE) exec worker python -c "from worker.jobs import run_forecasting_job; run_forecasting_job()"

anomalies: ## Trigger anomaly detection
	$(COMPOSE) exec worker python -c "from worker.jobs import run_anomaly_detection_job; run_anomaly_detection_job()"

semantic: ## Refresh semantic clusters
	$(COMPOSE) exec worker python -c "from worker.jobs import refresh_semantic_clusters; refresh_semantic_clusters()"

# ── Frontend ──────────────────────────────────────────────────────────

frontend-build: ## Build the React/Vite frontend
	docker run --rm -v "$$(pwd)/frontend":/app -w /app node:20-alpine sh -c "npm install && npm run build"

frontend-dev: ## Run the frontend dev server (port 5173)
	docker run --rm -v "$$(pwd)/frontend":/app -w /app -p 5173:5173 node:20-alpine sh -c "npm install && npm run dev -- --host"

# ── Observability ─────────────────────────────────────────────────────

healthcheck: ## Hit the API health endpoint
	@curl -s http://localhost:8000/health | python3 -m json.tool

observability: ## Show Prometheus targets and Grafana URL
	@echo "Prometheus: http://localhost:9090/targets"
	@echo "Grafana:    http://localhost:3000  (admin/admin)"
	@echo "Metrics:    http://localhost:8000/metrics"

# ── Cleanup ───────────────────────────────────────────────────────────

clean: ## Remove caches, bytecode, and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf frontend/dist

smoke: ## Run smoke tests against a live environment
	python scripts/smoke_test.py

refresh: ## Trigger operational intelligence refresh via API
	@curl -s -X POST http://localhost:8000/api/operations/refresh | python -m json.tool 2>/dev/null || echo '{"info": "API not reachable"}'

refresh-status: ## Check current operational refresh status
	@curl -s http://localhost:8000/api/operations/status | python -m json.tool 2>/dev/null || echo '{"info": "API not reachable"}'
