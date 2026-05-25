# Database Structure

## `airlines`

Tracked airlines by source, slug, country and review URL. Includes `last_scraped_at` for incremental collection monitoring.

## `reviews`

Canonical review facts collected by Scrapy. Includes rating, recommendation, route, aircraft, seat type, travel type, source URL, review date, raw metrics and deduplication `fingerprint`.

## `nlp_results`

One-to-one NLP enrichment for reviews. Stores cleaned text, sentiment label, sentiment score, extracted entities, topic keywords, model versions and pgvector embedding.

## `topic_snapshots`

Materialized positive and negative topic aggregates by airline.

## `spider_runs`

Operational table prepared for spider monitoring, including run status, item counts, page counts and errors.

## PostGIS (optional)

The platform supports two geospatial modes:

| Mode | `ENABLE_POSTGIS` | Requirements | Capabilities |
|------|------------------|--------------|--------------|
| Lightweight (default) | `false` | PostgreSQL + pgvector only | `latitude`/`longitude`, routes, hubs, heatmap points via lat/lon |
| Full geospatial | `true` | PostgreSQL with PostGIS extension | Adds `airports.location` geography column and spatial indexes |

Migrations never abort when PostGIS is missing. Extension creation is attempted only when `ENABLE_POSTGIS=true`; otherwise a structured warning is logged and tables are created with scalar coordinates only.

### Future map stack

Architecture retains `regions`, `airports`, and `routes` for Deck.gl / Mapbox overlays. Enable PostGIS on a `postgis/postgis` image (or install the extension manually) and set `ENABLE_POSTGIS=true` before running migrations or seed jobs.

## `anomaly_events` / `forecast_snapshots`

Operational intelligence tables for statistical anomaly detection and lightweight forecasting (EWMA + rolling averages). Independent of PostGIS.

## pgvector

`nlp_results.embedding` uses pgvector HNSW indexes. Semantic search and RAG remain available in lightweight mode without PostGIS.
