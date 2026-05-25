# ETL Flow

1. Seed tracked airlines with `python scripts/seed_airlines.py`.
2. Run Scrapy directly or enqueue `worker.jobs.run_scrapy_airlinequality`.
3. Spider emits `AirlineItem` and `ReviewItem` records.
4. Pipelines validate items, generate deterministic fingerprints and persist records in PostgreSQL.
5. Duplicate reviews are skipped by `fingerprint`.
6. NLP worker enriches pending reviews with sentiment, entities, topics and embeddings.
7. Topic snapshots are materialized for dashboard reads.
8. FastAPI exposes analytics, rankings, topics, sentiment and airline metadata.
9. React/ECharts dashboard presents executive customer experience and reputation intelligence.
