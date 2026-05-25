from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ServiceStatusResponse(BaseModel):
    project: str
    status: str
    docs: str


class HealthResponse(BaseModel):
    status: str


class AirlineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    country: str | None
    source: str
    review_url: str | None
    is_active: bool
    last_scraped_at: datetime | None


class ReviewResponse(BaseModel):
    id: str
    airline: str
    source: str
    source_url: str | None
    title: str | None
    text: str
    rating: float | None
    recommended: bool | None
    seat_type: str | None
    route: str | None
    aircraft: str | None
    travel_type: str | None
    review_date: date | None
    sentiment: str | None
    sentiment_score: float | None


class PaginatedReviewsResponse(BaseModel):
    items: list[ReviewResponse]
    limit: int
    offset: int
    total: int
    has_next: bool


class TopicResponse(BaseModel):
    id: str | None = None
    airline_id: str | None = None
    label: str
    polarity: str | None = None
    weight: float
    sample_size: int


class RankingResponse(BaseModel):
    name: str
    slug: str
    average_rating: float
    review_count: int
    recommendation_rate: float


class TimelinePointResponse(BaseModel):
    month: str
    average_rating: float
    count: int


class AnalyticsSummaryResponse(BaseModel):
    average_rating: float
    review_count: int
    recommendation_rate: float
    sentiment_distribution: dict[str, int]
    timeline: list[TimelinePointResponse]
    top_positive_topics: list[TopicResponse]
    top_negative_topics: list[TopicResponse]


class SentimentSummaryResponse(BaseModel):
    distribution: dict[str, int]
    positive_share: float
    negative_share: float


class ErrorResponse(BaseModel):
    detail: str


class ReputationScoreResponse(BaseModel):
    airline: str
    slug: str
    score: float
    rating_component: float
    sentiment_component: float
    recommendation_component: float
    complaint_severity: float
    topic_negativity: float
    recency_component: float = 0.0
    complaint_density: float = 0.0
    review_count: int
    timeline: list[dict]
    categories: dict[str, float]
    history: list[dict] = []


class TopicTrendResponse(BaseModel):
    topic: str
    current: int
    previous: int
    growth_rate: float


class BenchmarkingResponse(BaseModel):
    airlines: list[dict]
    topic_heatmap: dict[str, list[dict]]
    leaders: list[dict]
    radar_analytics: list[dict] = []
    comparative_trends: list[list[dict]] = []
    category_comparison: dict[str, dict[str, float]] = {}
    complaint_density: dict[str, float] = {}
    operational_risk: dict[str, float] = {}


class ExecutiveInsightResponse(BaseModel):
    id: str | None = None
    severity: str
    airline: str
    airline_slug: str | None = None
    category: str | None = None
    confidence: float | None = None
    generated_at: str | None = None
    summary: str
    insight_text: str | None = None
    drivers: list[str]
    supporting_metrics: dict | None = None


class SemanticSearchResultResponse(BaseModel):
    review_id: str
    airline: str
    airline_slug: str | None = None
    score: float
    lexical_score: float | None = None
    vector_score: float | None = None
    title: str | None
    text: str
    source_url: str | None
    review_date: str | None = None
    sentiment: str | None = None


class RAGContextResponse(BaseModel):
    query: str
    chunks: list[dict]
    temporal_window_days: int | None = None
    structural_summary: dict | None = None
    top_supporting_reviews: list[dict] = []
    comparative_context: list[dict] = []
    ranking_notes: str | None = None


class MetricSnapshotResponse(BaseModel):
    id: str
    airline_id: str | None
    snapshot_type: str
    period_start: str
    period_end: str
    metrics: dict


class SemanticClusterResponse(BaseModel):
    id: str
    airline: str
    airline_slug: str | None
    cluster_label: str
    review_count: int
    centroid_terms: list[str]
    sample_review_ids: list[str]


class DataQualityReportResponse(BaseModel):
    id: str
    report_type: str
    severity: str
    findings: list[dict]
    sample_size: int
    generated_at: str


class SchedulerStatusResponse(BaseModel):
    jobs: list[dict]


class ForecastSnapshotResponse(BaseModel):
    id: str
    airline: str
    airline_slug: str | None = None
    metric: str
    horizon: str
    method: str
    current_value: float
    forecast_value: float
    trend_direction: str
    generated_at: str
    payload: dict


class ForecastingSummaryResponse(BaseModel):
    generated_at: str
    metrics: dict[str, list[ForecastSnapshotResponse]]
    airlines: list[str]


class AnomalyEventResponse(BaseModel):
    id: str
    airline_id: str | None = None
    airline: str
    airline_slug: str | None = None
    anomaly_type: str
    severity: str
    metric: str
    expected_value: float | None
    observed_value: float
    context: dict
    detected_at: str


class OperationalAlertResponse(BaseModel):
    id: str
    title: str
    airline: str
    severity: str
    anomaly_type: str
    detected_at: str
    detail: str
