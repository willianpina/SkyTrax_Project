from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session, selectinload

from analytics.constants import SEMANTIC_CLUSTER_LABELS
from app.config import get_settings
from database.models import Airline, NLPResult, Review, SemanticCluster
from nlp.pipeline import ReviewNLPPipeline


class SemanticClusterService:
    """Lightweight keyword-based semantic clustering without BERTopic."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.pipeline = ReviewNLPPipeline(enable_embeddings=False)

    def refresh_clusters(self, airline_slug: str | None = None, limit: int = 2000) -> dict:
        query = (
            self.session.query(Review)
            .options(selectinload(Review.airline))
            .join(Airline)
            .order_by(Review.review_date.desc().nullslast())
        )
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        reviews = query.limit(limit).all()
        grouped: defaultdict[tuple[str | None, str], list[Review]] = defaultdict(list)
        for review in reviews:
            label = self._assign_cluster(review.text)
            grouped[(review.airline_id, label)].append(review)

        if airline_slug:
            airline = self.session.query(Airline).filter(Airline.slug == airline_slug).first()
            self.session.query(SemanticCluster).filter(SemanticCluster.airline_id == (airline.id if airline else None)).delete()
        else:
            self.session.query(SemanticCluster).delete()

        created = 0
        for (airline_id, label), cluster_reviews in grouped.items():
            if not cluster_reviews:
                continue
            terms = Counter()
            for review in cluster_reviews:
                terms.update(self.pipeline.tokenize(review.text))
            centroid = [term for term, _ in terms.most_common(8)]
            self.session.add(
                SemanticCluster(
                    airline_id=airline_id,
                    cluster_label=label,
                    review_count=len(cluster_reviews),
                    centroid_terms=centroid,
                    sample_review_ids=[review.id for review in cluster_reviews[:5]],
                )
            )
            created += 1
        self.session.commit()
        return {"clusters_created": created}

    def list_clusters(self, airline_slug: str | None = None) -> list[dict]:
        query = self.session.query(SemanticCluster, Airline).outerjoin(Airline, SemanticCluster.airline_id == Airline.id)
        if airline_slug:
            query = query.filter(Airline.slug == airline_slug)
        return [
            {
                "id": cluster.id,
                "airline": airline.name if airline else "Portfolio",
                "airline_slug": airline.slug if airline else None,
                "cluster_label": cluster.cluster_label,
                "review_count": cluster.review_count,
                "centroid_terms": cluster.centroid_terms,
                "sample_review_ids": cluster.sample_review_ids,
            }
            for cluster, airline in query.order_by(SemanticCluster.review_count.desc()).all()
        ]

    @staticmethod
    def _assign_cluster(text: str) -> str:
        tokens = set(re.findall(r"[a-z']+", text.lower()))
        best_label = "general feedback"
        best_score = 0
        for label, keywords in SEMANTIC_CLUSTER_LABELS.items():
            score = len(tokens & keywords)
            if score > best_score:
                best_score = score
                best_label = label
        return best_label


class EnhancedSemanticSearchService:
    """Hybrid lexical + embedding retrieval with filters and tuning."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.pipeline = ReviewNLPPipeline(enable_embeddings=self.settings.nlp_enable_embeddings)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        airline_slug: str | None = None,
        category: str | None = None,
        since: date | None = None,
        until: date | None = None,
        threshold: float | None = None,
        lexical_weight: float = 0.45,
    ) -> list[dict]:
        threshold = threshold if threshold is not None else self.settings.semantic_similarity_threshold
        query_clean = self.pipeline.clean_text(query)
        query_tokens = set(self.pipeline.tokenize(query_clean))
        query_embedding = self.pipeline.embed(query_clean)

        db_query = (
            self.session.query(Review)
            .options(selectinload(Review.airline), selectinload(Review.nlp_result))
            .join(Airline)
            .order_by(Review.review_date.desc().nullslast())
        )
        if airline_slug:
            db_query = db_query.filter(Airline.slug == airline_slug)
        if since:
            db_query = db_query.filter(Review.review_date >= since)
        if until:
            db_query = db_query.filter(Review.review_date <= until)
        if category:
            db_query = db_query.join(NLPResult).filter(NLPResult.topics.contains([category]))

        results = []
        for review in db_query.limit(800).all():
            tokens = set(self.pipeline.tokenize(review.text))
            lexical = len(query_tokens & tokens) / max(math.sqrt(len(query_tokens) * len(tokens)), 1)
            vector_score = 0.0
            if query_embedding and review.nlp_result and review.nlp_result.embedding is not None:
                vector_score = self._cosine(query_embedding, list(review.nlp_result.embedding))
            hybrid = lexical_weight * lexical + (1 - lexical_weight) * vector_score
            if hybrid >= threshold:
                results.append(
                    {
                        "review_id": review.id,
                        "airline": review.airline.name,
                        "airline_slug": review.airline.slug,
                        "score": round(hybrid, 4),
                        "lexical_score": round(lexical, 4),
                        "vector_score": round(vector_score, 4),
                        "title": review.title,
                        "text": review.text[:900],
                        "source_url": review.source_url,
                        "review_date": review.review_date.isoformat() if review.review_date else None,
                        "sentiment": review.nlp_result.sentiment_label if review.nlp_result else None,
                    }
                )
        return sorted(results, key=lambda row: row["score"], reverse=True)[:limit]

    def context(
        self,
        query: str,
        *,
        limit: int = 5,
        airline_slug: str | None = None,
        compare_slugs: list[str] | None = None,
        days: int = 90,
    ) -> dict:
        since = date.today() - timedelta(days=days)
        results = self.search(query, limit=limit * 2, airline_slug=airline_slug, since=since)
        comparative = []
        if compare_slugs:
            for slug in compare_slugs[:4]:
                peer_hits = self.search(query, limit=3, airline_slug=slug, since=since)
                comparative.append({"airline_slug": slug, "top_hits": peer_hits})
        summary = self._structural_summary(results)
        return {
            "query": query,
            "temporal_window_days": days,
            "structural_summary": summary,
            "top_supporting_reviews": results[:limit],
            "chunks": [
                {
                    "chunk_id": f"{row['review_id']}:0",
                    "source": row["source_url"],
                    "airline": row["airline"],
                    "text": row["text"],
                    "score": row["score"],
                    "review_date": row.get("review_date"),
                }
                for row in results[:limit]
            ],
            "comparative_context": comparative,
            "ranking_notes": "Hybrid lexical + vector score with recency bias applied in search ordering.",
        }

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm_left = math.sqrt(sum(a * a for a in left))
        norm_right = math.sqrt(sum(b * b for b in right))
        if norm_left == 0 or norm_right == 0:
            return 0.0
        return dot / (norm_left * norm_right)

    @staticmethod
    def _structural_summary(results: list[dict]) -> dict:
        if not results:
            return {"airlines": [], "dominant_sentiment": None, "avg_score": 0}
        sentiments = Counter(row.get("sentiment") or "unknown" for row in results)
        airlines = Counter(row["airline"] for row in results)
        return {
            "airlines": [{"name": name, "hits": count} for name, count in airlines.most_common(5)],
            "dominant_sentiment": sentiments.most_common(1)[0][0] if sentiments else None,
            "avg_score": round(sum(row["score"] for row in results) / len(results), 4),
            "review_count": len(results),
        }
