"""analytics.semantic -- semantic search and clustering sub-package.

Re-exports preserve ``from analytics.semantic_ops import X`` compatibility.
"""

from analytics.semantic.search import (  # noqa: F401
    EnhancedSemanticSearchService,
    SemanticClusterService,
)

__all__ = ["EnhancedSemanticSearchService", "SemanticClusterService"]
