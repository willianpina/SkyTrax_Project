from __future__ import annotations

from datetime import date

from analytics.constants import SEMANTIC_CLUSTER_LABELS
from analytics.semantic_ops import SemanticClusterService


def test_semantic_cluster_assignment() -> None:
    service = SemanticClusterService.__new__(SemanticClusterService)
    label = service._assign_cluster(
        "My baggage was lost and refund was denied after a long delay at the airport."
    )
    assert label in SEMANTIC_CLUSTER_LABELS or label == "general feedback"


def test_enhanced_search_threshold_filters_low_scores() -> None:
    from analytics.semantic_ops import EnhancedSemanticSearchService

    class _FakeReview:
        def __init__(self, text: str) -> None:
            self.id = "r1"
            self.text = text
            self.title = "t"
            self.source_url = None
            self.review_date = date.today()
            self.airline = type("A", (), {"name": "Test Air", "slug": "test"})()
            self.nlp_result = None

    class _FakeQuery:
        def options(self, *args, **kwargs):
            return self

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, n):
            return [_FakeReview("unrelated hotel stay with no aviation context")]

    class _FakeSession:
        def query(self, *args):
            return _FakeQuery()

    service = EnhancedSemanticSearchService(_FakeSession())
    results = service.search("refund baggage delay", threshold=0.5, limit=5)
    assert results == []


def test_openapi_operational_routes() -> None:
    from fastapi.testclient import TestClient

    from tests.conftest import app

    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/snapshots" in paths
    assert "/api/semantic-clusters" in paths
    assert "/api/data-quality" in paths
    assert "/api/scheduler/status" in paths


def test_reputation_score_has_ars_components() -> None:
    from analytics.intelligence import ReputationService

    class _Session:
        def query(self, *args, **kwargs):
            return self

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def outerjoin(self, *args, **kwargs):
            return self

        def all(self):
            return []

        def first(self):
            return None

        def scalar(self):
            return 0

        def group_by(self, *args):
            return self

        def order_by(self, *args):
            return self

    score = ReputationService(_Session()).score_airline("emirates")
    assert "recency_component" in score
    assert "complaint_density" in score
    assert "history" in score
