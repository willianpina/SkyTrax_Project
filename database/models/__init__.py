"""database.models — re-exports every model so existing imports keep working.

Usage unchanged:
    from database.models import Airline, Review, ...
"""

from database.session import Base
from database.models.base import TimestampMixin
from database.models.core import Airline, Review, NLPResult, SpiderRun
from database.models.analytics import (
    TopicSnapshot,
    MetricSnapshot,
    ReputationScoreHistory,
    ForecastSnapshot,
    AnomalyEvent,
)
from database.models.intelligence import (
    ExecutiveInsight,
    SemanticCluster,
    DataQualityReport,
    DataLineage,
    ScheduledJob,
)
from database.models.geo import Region, Airport, Route
from database.models.aviation import (
    Alliance,
    AirlineMetadata,
    AirportMetadata,
    AirlineAirport,
    AviationTaxonomy,
    AviationCoverageReport,
)
from database.models.operations import OperationalRefreshRun
from database.models.graph import (
    GraphNode,
    GraphEdge,
    FusionSignal,
    ReviewIntelligence,
)

__all__ = [
    "Base",
    "TimestampMixin",
    # core
    "Airline",
    "Review",
    "NLPResult",
    "SpiderRun",
    # analytics
    "TopicSnapshot",
    "MetricSnapshot",
    "ReputationScoreHistory",
    "ForecastSnapshot",
    "AnomalyEvent",
    # intelligence
    "ExecutiveInsight",
    "SemanticCluster",
    "DataQualityReport",
    "DataLineage",
    "ScheduledJob",
    # geo
    "Region",
    "Airport",
    "Route",
    # aviation metadata
    "Alliance",
    "AirlineMetadata",
    "AirportMetadata",
    "AirlineAirport",
    "AviationTaxonomy",
    "AviationCoverageReport",
    # operations
    "OperationalRefreshRun",
    # knowledge graph
    "GraphNode",
    "GraphEdge",
    "FusionSignal",
    "ReviewIntelligence",
]
