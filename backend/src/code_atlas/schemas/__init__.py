"""API schemas for Code Atlas."""

from .common import (
    BaseResponse,
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
)
from .embeddings import (
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    SimilarityRequest,
    SimilarityResponse,
)
from .graph import (
    EdgeData,
    EntityListResponse,
    EntityResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphVisualizationResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResultItem,
    NodeData,
    RAGQueryRequest,
    RAGQueryResponse,
    RelationshipResponse,
)
from .sessions import (
    JobStatus,
    ProcessingJob,
    SessionDiscoveryRequest,
    SessionDiscoveryResponse,
    SessionInfo,
    SessionProcessRequest,
    SessionProcessResponse,
)

from .usage import (
    UsageEvent,
    UsageEventType,
    UsageReport,
    UsageSummary,
)

__all__ = [
    # Common
    "BaseResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
    # Sessions
    "SessionDiscoveryRequest",
    "SessionDiscoveryResponse",
    "SessionInfo",
    "SessionProcessRequest",
    "SessionProcessResponse",
    "ProcessingJob",
    "JobStatus",
    # Graph
    "EntityResponse",
    "EntityListResponse",
    "RelationshipResponse",
    "GraphQueryRequest",
    "GraphQueryResponse",
    "GraphVisualizationResponse",
    "NodeData",
    "EdgeData",
    "HybridSearchRequest",
    "HybridSearchResponse",
    "HybridSearchResultItem",
    "RAGQueryRequest",
    "RAGQueryResponse",
    # Embeddings
    "EmbeddingRequest",
    "EmbeddingResponse",
    "BatchEmbeddingRequest",
    "BatchEmbeddingResponse",
    "SimilarityRequest",
    "SimilarityResponse",
    # Usage
    "UsageEvent",
    "UsageEventType",
    "UsageReport",
    "UsageSummary",
]
