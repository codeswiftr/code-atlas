"""API schemas for Code Atlas."""

from .common import (
    BaseResponse,
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
)
from .sessions import (
    SessionDiscoveryRequest,
    SessionDiscoveryResponse,
    SessionInfo,
    SessionProcessRequest,
    SessionProcessResponse,
    ProcessingJob,
    JobStatus,
)
from .graph import (
    EntityResponse,
    EntityListResponse,
    RelationshipResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphVisualizationResponse,
    NodeData,
    EdgeData,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResultItem,
    RAGQueryRequest,
    RAGQueryResponse,
)
from .embeddings import (
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    SimilarityRequest,
    SimilarityResponse,
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
]
