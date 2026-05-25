# Architecture

## System Overview

The SkyTrax Airline Intelligence Platform is a modular market intelligence system that collects airline reviews, enriches them with NLP, and delivers analytical insights through a REST API and interactive dashboard.

The system follows a pipeline architecture: data flows from external sources through collection, enrichment, analytics, and presentation layers. Each layer is independently deployable and horizontally scalable.

```text
+------------------------------------------------------------------+
|                        PRESENTATION LAYER                         |
|  React 18 + Vite + ECharts + Tailwind CSS + i18next              |
+-----------------------------------+------------------------------+
                                    |
+-----------------------------------v------------------------------+
|                           API LAYER                               |
|  FastAPI + Pydantic schemas + middleware stack                     |
|  (CORS, rate limiting, timeouts, security headers, GZip)          |
+---+-------------+-------------+-------------+---+----------------+
    |             |             |             |   |
+---v---+   +----v----+   +----v----+   +----v---v---------+
|Reviews|   |Analytics|   |Intelli- |   |Search / Forecast |
|Router |   |Router   |   |gence   |   |Anomalies / Admin |
+---+---+   +----+----+   +----+----+   +----+-------------+
    |             |             |             |
+---v-------------v-------------v-------------v----------------+
|                       SERVICE LAYER                           |
|  AnalyticsService, ReputationService, BenchmarkingService,    |
|  TopicTrendService, SemanticSearchService, ForecastingService,|
|  AnomalyDetectionService, ExecutiveInsightEngine,             |
|  SnapshotService, DataQualityMonitor                          |
+-------------------------------+------------------------------+
                                |
+-------------------------------v------------------------------+
|                       DATA LAYER                              |
|  SQLAlchemy ORM + PostgreSQL + pgvector + Alembic             |
|  Models: Airline, Review, NLPResult, TopicSnapshot,           |
|          MetricSnapshot, ForecastSnapshot, AnomalyEvent,      |
|          ExecutiveInsight, SemanticCluster, ReputationHistory  |
+-------------------------------+------------------------------+
                                |
+---------------+---------------v--------------+---------------+
|   COLLECTION  |         NLP PIPELINE         |    WORKERS    |
|   Scrapy      |  spaCy, TF-IDF, embeddings,  |  Redis + RQ   |
|   spiders     |  sentiment, topics, entities  |  job scheduler|
+---------------+------------------------------+---------------+
```

## Layer Architecture

### API Layer

The API layer is built on FastAPI with a middleware stack that provides security, reliability, and observability:

| Middleware | Purpose |
|---|---|
| `CORSMiddleware` | Cross-origin access control |
| `RequestContextMiddleware` | Inject request/trace IDs into logs |
| `TimeoutMiddleware` | Cancel long-running requests |
| `RateLimitMiddleware` | Per-client request throttling |
| `RequestSizeLimitMiddleware` | Reject oversized payloads |
| `SecurityHeadersMiddleware` | Inject security response headers |
| `GZipMiddleware` | Compress responses above 1KB |
| `TrustedHostMiddleware` | Validate Host header |

Routes are organized into domain-specific routers aggregated through `api/routes.py`. Exception handlers provide structured error responses for database errors, validation failures, and unhandled exceptions.

### Service Layer

Business logic is encapsulated in service classes, each receiving a SQLAlchemy session:

| Service | Responsibility |
|---|---|
| `AnalyticsService` | Executive summaries, rankings, sentiment distribution |
| `ReputationService` | Composite ARS scoring with component breakdown |
| `BenchmarkingService` | Cross-airline metric comparison |
| `TopicTrendService` | Temporal topic evolution analysis |
| `SemanticSearchService` | pgvector cosine similarity search, RAG context |
| `TrendForecastingService` | EWMA/rolling forecasts, portfolio summaries |
| `AnomalyDetectionService` | Statistical anomaly detection and alerting |
| `ExecutiveInsightEngine` | Intelligence signal generation and persistence |
| `SnapshotService` | Temporal metric snapshot generation |
| `SemanticClusterService` | Review clustering by operational theme |
| `DataQualityMonitor` | Automated data quality scans |
| `TopicModelingService` | TF-IDF topic extraction and snapshot refresh |

### Intelligence Layer

The intelligence pipeline produces higher-order analytical outputs:

1. **Reputation Scoring** -- Weighted composite score combining rating averages, sentiment distribution, recommendation rate, and review volume into a single Airline Reputation Score (ARS) with historical tracking.

2. **Anomaly Detection** -- Z-score and IQR-based detection across sentiment, volume, and rating metrics. Anomalies are classified by severity and persisted with explanations.

3. **Trend Forecasting** -- Exponentially weighted moving average (EWMA) and rolling-average forecasts at weekly and monthly horizons. Includes confidence scoring and trend direction classification.

4. **Executive Insights** -- Rule-based intelligence engine that synthesizes reputation, anomaly, topic, and sentiment signals into actionable insight statements with confidence levels and supporting evidence.

5. **Competitive Benchmarking** -- Multi-dimensional airline comparison across rating, sentiment, topic, and volume metrics.

6. **Semantic Search** -- Cosine similarity search over 384-dimensional sentence-transformer embeddings stored in pgvector with HNSW indexing. Supports filtered search by airline, date range, and category.

### Data Layer

PostgreSQL with pgvector serves as the primary data store. SQLAlchemy 2.0 mapped columns define the schema, and Alembic manages migrations.

### Collection Layer

Scrapy spiders crawl airline reviews from airlinequality.com. The scraping infrastructure includes:

- Auto-throttle and conservative concurrency
- Retry middleware for rate limits and transient failures
- Rotating user agents and browser-like headers
- Optional Playwright rendering for JavaScript-heavy pages
- Fingerprint-based deduplication
- Structured JSONL export and PostgreSQL persistence
- Operational metrics persisted in `spider_runs`

### Worker Layer

Redis + RQ provides background job processing with overlap lock protection:

| Job | Schedule | Description |
|---|---|---|
| `run_scrapy_airlinequality` | Configurable | Execute Scrapy spiders for one or all airlines |
| `schedule_priority_crawls` | Every N hours | Enqueue crawls for priority airlines |
| `enrich_pending_reviews` | Every 30 min | NLP enrichment for un-processed reviews |
| `generate_metric_snapshots` | Hourly/daily | Temporal metric aggregation |
| `generate_executive_insights` | Every 4 hours | Intelligence signal generation |
| `persist_reputation_scores` | Periodic | ARS calculation and persistence |
| `refresh_semantic_clusters` | Periodic | Review clustering refresh |
| `run_forecasting_job` | Every 4 hours | Forecast generation |
| `run_anomaly_detection_job` | Every 2 hours | Anomaly detection sweep |
| `run_data_quality_scan` | Periodic | Data quality audit |
| `operational_cleanup` | Daily | Prune old spider run records |

All jobs use `acquire_job_lock` / `release_job_lock` to prevent overlapping execution. Failed jobs emit alerts through the configurable webhook.

### Frontend Layer

React 18 single-page application built with Vite:

| Component | Purpose |
|---|---|
| `ExecutiveDashboard` | Main dashboard layout with summary metrics |
| `CommandRail` | Intelligence command panel (insights, anomalies, search) |
| `ChartPanel` | Reusable ECharts wrapper with theming |
| `BenchmarkingRadar` | Radar chart for competitive comparison |
| `ForecastPanel` | Trend forecast visualization |
| `AnomalyPanel` | Anomaly event timeline |
| `ExecutiveInsightsPanel` | Intelligence signal feed |
| `SemanticInvestigationPanel` | Semantic search interface |
| `AnomalyFeed` | Real-time anomaly stream |
| `IntelligenceTimeline` | Temporal intelligence events |
| `PanelShell` | Consistent panel container with loading states |

Internationalization is handled by i18next with English and Portuguese translations.

## Data Flow

```text
1. COLLECTION
   Scrapy spider crawls airlinequality.com
   -> Scrapy pipeline validates, deduplicates, persists to PostgreSQL
   -> SpiderRun record tracks operational metrics

2. ENRICHMENT
   RQ worker picks up pending reviews (no NLPResult)
   -> ReviewNLPPipeline: clean -> sentiment -> topics -> entities -> embed
   -> NLPResult persisted with model versions
   -> TopicSnapshot aggregates refreshed

3. ANALYTICS
   Periodic jobs generate derived data:
   -> MetricSnapshot: temporal aggregates (hourly, daily)
   -> ReputationScoreHistory: composite ARS per airline
   -> ForecastSnapshot: EWMA/rolling predictions
   -> AnomalyEvent: statistical outlier detection
   -> ExecutiveInsight: synthesized intelligence signals
   -> SemanticCluster: thematic review groupings
   -> DataQualityReport: automated quality findings

4. SERVING
   FastAPI reads from PostgreSQL
   -> Pydantic schemas serialize responses
   -> React dashboard renders charts and panels
```

## Database Schema Overview

### Core Tables

| Table | Description |
|---|---|
| `airlines` | Airline registry with slug, country, source, active status |
| `reviews` | Canonical review facts with rating, text, route, seat type, metrics (JSONB) |
| `nlp_results` | NLP enrichment: sentiment, topics, entities, embedding (vector 384) |
| `spider_runs` | Scrapy operational monitoring (items scraped, pages crawled, quality score) |

### Analytics Tables

| Table | Description |
|---|---|
| `topic_snapshots` | Materialized topic aggregates by airline and polarity |
| `metric_snapshots` | Temporal metric aggregates (sentiment, volume, reputation trends) |
| `reputation_score_history` | Historical ARS records with component breakdown |
| `forecast_snapshots` | Persisted forecasts with method, horizon, confidence |
| `anomaly_events` | Detected anomalies with severity, expected/observed values |

### Intelligence Tables

| Table | Description |
|---|---|
| `executive_insights` | Generated intelligence signals with confidence and evidence |
| `semantic_clusters` | Review groupings by operational theme |
| `data_quality_reports` | Automated quality findings |
| `data_lineage` | Pipeline provenance tracking |
| `scheduled_jobs` | Job scheduler state and overlap control |

### Key Indexes

- `ix_nlp_results_embedding_hnsw` -- HNSW index for cosine similarity search
- `ix_reviews_airline_date` -- Composite index for time-series queries
- `ix_reviews_metrics_gin` -- GIN index on JSONB metrics
- `ix_nlp_results_topics_gin` -- GIN index for topic containment queries

## API Layer Design

The API is versioned at `/api` with domain-specific router modules:

| Router Module | Prefix | Endpoints |
|---|---|---|
| `reviews` | `/api` | airlines, reviews, topics |
| `analytics_router` | `/api` | analytics, rankings, sentiment, topic-trends |
| `intelligence` | `/api` | reputation, benchmarking, insights, snapshots |
| `search` | `/api` | semantic-search, semantic-clusters, rag/context |
| `forecasting` | `/api/forecasting` | forecasts, refresh, per-airline |
| `anomalies` | `/api/anomalies` | anomaly events, alerts, refresh |
| `admin` | `/api` | scheduler status, data quality |

All endpoints return Pydantic-validated JSON. The API includes structured exception handlers for `SQLAlchemyError`, `NoResultFound`, and `RequestValidationError`.

## Observability Stack

```text
+-------------+     +-------------------+     +------------+
|  FastAPI    |     |  Prometheus       |     |  Grafana   |
|  /metrics   +---->|  scrape targets:  +---->|  SkyTrax   |
|             |     |  - API            |     |  Enterprise|
+-------------+     |  - PG exporter    |     |  Dashboard |
                    |  - Redis exporter |     +------------+
                    +-------------------+
```

Metrics exposed at `/metrics`:

- API request counts, latencies, and error rates
- Database connection pool utilization
- Redis connection health and RQ queue depth
- Scrapy spider run counts and durations
- Worker job execution metrics (NLP throughput, forecast counts, anomaly counts)

Structured JSON logs include: request ID, trace ID, service name, module, spider name, airline slug, duration, retry count, and error details.
