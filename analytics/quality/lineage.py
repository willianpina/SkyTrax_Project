from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import DataLineage, NLPResult, Review, SpiderRun


class DataLineageService:
    """Source provenance and pipeline versioning."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        entity_type: str,
        entity_id: str | None,
        source: str,
        pipeline_stage: str,
        model_version: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.session.add(
            DataLineage(
                entity_type=entity_type,
                entity_id=entity_id,
                source=source,
                pipeline_stage=pipeline_stage,
                model_version=model_version,
                metadata_=metadata or {},
                recorded_at=datetime.now(timezone.utc),
            )
        )

    def snapshot_crawl_lineage(self, spider_run_id: str) -> None:
        run = self.session.get(SpiderRun, spider_run_id)
        if not run:
            return
        self.record(
            entity_type="spider_run",
            entity_id=run.id,
            source=run.source,
            pipeline_stage="scrapy_ingest",
            metadata={
                "spider_name": run.spider_name,
                "items_scraped": run.items_scraped,
                "pages_crawled": run.pages_crawled,
            },
        )

    def snapshot_nlp_lineage(self, review_id: str, model_versions: dict) -> None:
        self.record(
            entity_type="review",
            entity_id=review_id,
            source="nlp_pipeline",
            pipeline_stage="enrichment",
            model_version=model_versions.get("embeddings"),
            metadata=model_versions,
        )

    def list_lineage(self, entity_type: str | None = None, limit: int = 50) -> list[dict]:
        query = self.session.query(DataLineage).order_by(DataLineage.recorded_at.desc())
        if entity_type:
            query = query.filter(DataLineage.entity_type == entity_type)
        return [
            {
                "id": row.id,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "source": row.source,
                "pipeline_stage": row.pipeline_stage,
                "model_version": row.model_version,
                "metadata": row.metadata_,
                "recorded_at": row.recorded_at.isoformat(),
            }
            for row in query.limit(limit).all()
        ]

    def governance_summary(self) -> dict:
        review_count = self.session.query(Review).count()
        nlp_count = self.session.query(NLPResult).count()
        crawl_runs = self.session.query(SpiderRun).count()
        return {
            "reviews_tracked": review_count,
            "nlp_enriched": nlp_count,
            "crawl_runs_logged": crawl_runs,
            "embedding_version": "sentence-transformers/all-MiniLM-L6-v2",
            "nlp_pipeline": "lexicon-v1 + tfidf-fallback-v1",
        }
