from __future__ import annotations

import re

from sqlalchemy.orm import Session

from analytics.anomaly import AnomalyDetectionService
from analytics.explainability.explainable import ExplainableIntelligenceService
from analytics.forecasting import TrendForecastingService
from analytics.explainability.insights_engine import ExecutiveInsightEngine
from analytics.intelligence import BenchmarkingService, ReputationService
from analytics.semantic.search import EnhancedSemanticSearchService
from analytics.explainability.snapshots import SnapshotService


class ExecutiveCopilotEngine:
    """Rule-based executive Q&A over semantic retrieval and strategic analytics."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.search = EnhancedSemanticSearchService(session)
        self.reputation = ReputationService(session)
        self.benchmarking = BenchmarkingService(session)
        self.insights = ExecutiveInsightEngine(session)
        self.forecasting = TrendForecastingService(session)
        self.anomalies = AnomalyDetectionService(session)
        self.explainable = ExplainableIntelligenceService(session)
        self.snapshots = SnapshotService(session)

    def ask(self, question: str, airline_slug: str | None = None) -> dict:
        q = question.strip()
        intent = self._classify_intent(q)
        context = {"question": q, "intent": intent}

        if intent == "operational_risk":
            slug = airline_slug or self._extract_airline(q) or "emirates"
            hits = self.search.search(f"{slug} premium operational risk", limit=5, airline_slug=slug)
            score = self.reputation.score_airline(slug)
            anomalies = [a for a in self.anomalies.list_recent(10) if a.get("airline_slug") == slug]
            answer = (
                f"Top operational risks for {slug.replace('-', ' ').title()} premium passengers include "
                f"{', '.join(a['anomaly_type'] for a in anomalies[:3]) or 'elevated complaint density'} "
                f"with ARS {score['score']} and complaint density {score.get('complaint_density', 0)}."
            )
            context.update({"answer": answer, "evidence": hits, "anomalies": anomalies, "score": score})

        elif intent == "reputation_decline":
            scores = [self.reputation.score_airline(slug) for slug in self._benchmark_slugs()]
            worst = min(scores, key=lambda row: row.get("score", 100))
            explanation = self.explainable.explain_reputation_score(worst["slug"])
            answer = (
                f"{worst['airline']} showed the largest reputation pressure this period "
                f"(ARS {worst['score']}). {explanation['narrative']}"
            )
            context.update({"answer": answer, "airline": worst, "explanation": explanation})

        elif intent == "european_sentiment":
            slugs = ["british-airways", "lufthansa"]
            topics = []
            for slug in slugs:
                rows = self.search.search("negative sentiment europe", limit=3, airline_slug=slug)
                topics.extend([row.get("matched_topics", []) for row in rows])
            insights = self.insights.list_recent(10)
            eu_insights = [i for i in insights if i.get("airline_slug") in slugs]
            answer = (
                "European carriers are primarily driven by "
                f"{', '.join(i['category'] for i in eu_insights[:3]) or 'delays, baggage and crew behavior'} "
                "in negative sentiment clusters."
            )
            context.update({"answer": answer, "insights": eu_insights})

        else:
            hits = self.search.search(q, limit=6, airline_slug=airline_slug)
            bench = self.benchmarking.compare()
            answer = (
                f"Based on {len(hits)} semantically relevant reviews and peer benchmarking, "
                f"key themes include {', '.join(bench.get('leaders', [{}])[0].get('airline', 'portfolio analysis'))}."
            )
            context.update({"answer": answer, "semantic_hits": hits, "benchmarking": bench})

        context["executive_summary"] = self._executive_summary(context)
        return context

    def _classify_intent(self, question: str) -> str:
        lower = question.lower()
        if "operational risk" in lower or "premium" in lower:
            return "operational_risk"
        if "largest reputation decline" in lower or "reputation decline" in lower:
            return "reputation_decline"
        if "european" in lower and "sentiment" in lower:
            return "european_sentiment"
        return "general"

    def _extract_airline(self, question: str) -> str | None:
        aliases = {
            "emirates": "emirates",
            "qatar": "qatar-airways",
            "british": "british-airways",
            "lufthansa": "lufthansa",
            "latam": "latam-airlines",
        }
        lower = question.lower()
        for key, slug in aliases.items():
            if key in lower:
                return slug
        return None

    def _benchmark_slugs(self) -> list[str]:
        from analytics.constants import BENCHMARK_AIRLINES

        return BENCHMARK_AIRLINES

    def _executive_summary(self, context: dict) -> str:
        return context.get("answer", "No executive summary available.")
