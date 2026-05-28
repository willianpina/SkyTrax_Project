from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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
    complaint_count: int = 0
    negative_count: int = 0
    country: str | None = None
    region: str | None = None
    alliance: str | None = None
    star_rating: int | None = None
    airline_type: str | None = None
    iata_code: str | None = None
    icao_code: str | None = None
    primary_hub: str | None = None
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


class PipelineHealthPipeline(BaseModel):
    """Pipeline subsection for GET /api/operations/health/pipeline."""

    model_config = ConfigDict(extra="allow")

    running: bool = False
    stage: str | None = None
    progress: int | float | None = None
    pipeline_status: str | None = None
    operation_id: str | None = None
    degraded: bool = False
    false_degraded_detected: bool = False


class PipelineHealthSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    healthy: bool = True
    migration_drift: bool | None = None
    missing_tables: list[str] = Field(default_factory=list)
    pending_migrations: list[str] = Field(default_factory=list)
    current_revision: str | None = None
    head_revision: str | None = None
    canonical_aviation_valid: bool | None = None
    aviation_missing_columns: list[str] = Field(default_factory=list)
    aviation_aliases_detected: dict = Field(default_factory=dict)
    aviation_backfill_status: str | None = None
    aviation_semantic_drift: bool | None = None
    runtime_schema_consistent: bool | None = None
    stale_reflection_detected: bool = False
    engine_generation: int = 0
    runtime_refresh_count: int = 0
    aviation_identity_health: dict = Field(default_factory=dict)
    canonical_identity_consistent: bool | None = None
    semantic_duplicates_detected: int | None = None
    slug_collision_rate: float | None = None
    identity_merge_count: int | None = None
    summary_source: str | None = None


class PipelineHealthResponse(BaseModel):
    """Enterprise pipeline health — JSON-safe governance fields."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    status: str = "ready"
    readiness: str = "ready"
    environment: str = "development"
    degraded: bool = False
    pipeline: PipelineHealthPipeline = Field(default_factory=PipelineHealthPipeline)
    # Avoid field name `schema` — shadows BaseModel.schema() and breaks OpenAPI/serialization.
    schema_health: PipelineHealthSchema = Field(
        default_factory=PipelineHealthSchema,
        alias="schema",
    )
    native: dict = Field(default_factory=dict)
    runtime: dict = Field(default_factory=dict)
    runtime_health: dict = Field(default_factory=dict)
    startup: dict | None = None
    blocked_stages: list[str] = Field(default_factory=list)
    degraded_history: list[dict] = Field(default_factory=list)
    auto_migrate_policy: str = "validate_only"
    integrity_reconciled: bool = False
    authoritative_kpis: dict = Field(default_factory=dict)
    canonical_kpis: dict = Field(default_factory=dict)
    accumulated_kpis: dict = Field(default_factory=dict)
    delta_kpis: dict = Field(default_factory=dict)
    kpi_governance: dict = Field(default_factory=dict)
    kpi_lineage: dict = Field(default_factory=dict)
    metric_lineage: dict = Field(default_factory=dict)
    metric_semantics: dict = Field(default_factory=dict)
    integrity_consistent: bool = True
    runtime_authoritative: bool = False
    stale_kpis_removed: int = 0
    payload_safe: bool = True
    governance_source: str | None = None
