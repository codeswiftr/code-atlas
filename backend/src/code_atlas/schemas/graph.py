"""Graph-related API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .common import BaseResponse


class EntityType(str, Enum):
    """Types of entities in the knowledge graph."""

    SESSION = "Session"
    CONCEPT = "Concept"
    FILE = "File"
    TOOL = "Tool"
    PROBLEM = "Problem"
    SOLUTION = "Solution"


class RelationshipType(str, Enum):
    """Types of relationships in the knowledge graph."""

    MENTIONS = "MENTIONS"
    REFERENCES = "REFERENCES"
    SOLVES = "SOLVES"
    USES = "USES"
    RELATED_TO = "RELATED_TO"


class EntityResponse(BaseModel):
    """Single entity from the knowledge graph."""

    id: str
    type: EntityType
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    source_session: str | None = None
    created_at: datetime | None = None
    mention_count: int = 0
    # Merge tracking fields
    merged_count: int | None = Field(
        default=None,
        description="Number of entities merged into this one",
    )
    merged_names: list[str] | None = Field(
        default=None,
        description="Names of entities that were merged into this one",
    )
    last_merged_at: datetime | None = Field(
        default=None,
        description="Timestamp of the last merge operation",
    )
    is_canonical: bool = Field(
        default=True,
        description="Whether this is a canonical entity (not merged into another)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "concept-abc123",
                "type": "Concept",
                "name": "Authentication",
                "properties": {
                    "description": "User authentication and authorization",
                    "tags": ["security", "auth"],
                },
                "confidence": 0.95,
                "source_session": "session-def456",
                "created_at": "2025-01-15T10:30:00Z",
                "mention_count": 5,
                "merged_count": 2,
                "merged_names": ["Auth", "auth system"],
                "last_merged_at": "2025-01-15T12:00:00Z",
                "is_canonical": True,
            }
        }
    }


class EntityListResponse(BaseResponse):
    """Response containing a list of entities."""

    entities: list[EntityResponse]
    total: int
    page: int
    page_size: int


class RelationshipResponse(BaseModel):
    """Single relationship from the knowledge graph."""

    id: str
    type: RelationshipType
    source_id: str
    source_name: str
    source_type: EntityType
    target_id: str
    target_name: str
    target_type: EntityType
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    created_at: datetime | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "rel-abc123",
                "type": "SOLVES",
                "source_id": "solution-xyz",
                "source_name": "JWT Token Implementation",
                "source_type": "Solution",
                "target_id": "problem-abc",
                "target_name": "User Session Management",
                "target_type": "Problem",
                "properties": {"context": "Implemented in auth module"},
                "confidence": 0.92,
                "created_at": "2025-01-15T10:30:00Z",
            }
        }
    }


class RelationshipListResponse(BaseResponse):
    """Response containing a list of relationships."""

    relationships: list[RelationshipResponse]
    total: int
    page: int
    page_size: int


class GraphQueryRequest(BaseModel):
    """Request to execute a Cypher query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Cypher query to execute (read-only)",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "MATCH (e:Concept) WHERE e.name CONTAINS $search RETURN e LIMIT $limit",
                "parameters": {"search": "auth"},
                "limit": 50,
            }
        }
    }


class GraphQueryResponse(BaseResponse):
    """Response from a Cypher query."""

    results: list[dict[str, Any]]
    columns: list[str]
    row_count: int
    execution_time_ms: float


class NodeData(BaseModel):
    """Node data for graph visualization."""

    id: str
    label: str
    type: EntityType
    size: float = 10.0
    color: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "concept-abc123",
                "label": "Authentication",
                "type": "Concept",
                "size": 15.0,
                "color": "#A78BFA",
                "properties": {"mention_count": 5},
            }
        }
    }


class EdgeData(BaseModel):
    """Edge data for graph visualization."""

    id: str
    source: str
    target: str
    type: RelationshipType
    weight: float = 1.0
    color: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "rel-abc123",
                "source": "solution-xyz",
                "target": "problem-abc",
                "type": "SOLVES",
                "weight": 1.5,
                "color": "#10B981",
                "properties": {},
            }
        }
    }


class GraphVisualizationResponse(BaseResponse):
    """Response with graph data for visualization."""

    nodes: list[NodeData]
    edges: list[EdgeData]
    node_count: int
    edge_count: int
    layout_hint: str = "force"

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "nodes": [
                    {
                        "id": "concept-abc",
                        "label": "Auth",
                        "type": "Concept",
                        "size": 15.0,
                        "color": "#A78BFA",
                    }
                ],
                "edges": [
                    {
                        "id": "rel-xyz",
                        "source": "solution-1",
                        "target": "concept-abc",
                        "type": "MENTIONS",
                        "weight": 1.0,
                    }
                ],
                "node_count": 1,
                "edge_count": 1,
                "layout_hint": "force",
            }
        }
    }


class EntitySearchRequest(BaseModel):
    """Request to search entities."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Search query",
    )
    entity_types: list[EntityType] | None = Field(
        default=None,
        description="Filter by entity types",
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score",
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class GraphStatsResponse(BaseResponse):
    """Response with knowledge graph statistics."""

    total_nodes: int
    total_edges: int
    nodes_by_type: dict[str, int]
    edges_by_type: dict[str, int]
    avg_connections_per_node: float
    most_connected_entities: list[EntityResponse]


class EntitySearchResult(BaseModel):
    """Search result with relevance score."""

    entity: EntityResponse
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (1.0 = exact match)",
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Matched text snippets",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "entity": {
                    "id": "concept-abc123",
                    "type": "Concept",
                    "name": "Authentication",
                    "properties": {},
                    "confidence": 0.95,
                },
                "score": 0.92,
                "highlights": ["**Auth**entication"],
            }
        }
    }


class EntitySearchResponse(BaseResponse):
    """Full-text search response."""

    results: list[EntitySearchResult]
    total: int
    query: str
    took_ms: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "results": [
                    {
                        "entity": {
                            "id": "concept-abc",
                            "type": "Concept",
                            "name": "Authentication",
                        },
                        "score": 0.95,
                        "highlights": ["**Auth**entication"],
                    }
                ],
                "total": 1,
                "query": "auth",
                "took_ms": 12.5,
            }
        }
    }


class MergeRecordResponse(BaseModel):
    """Record of an entity merge operation."""

    merged_id: str = Field(description="ID of entity that was merged (deleted)")
    canonical_id: str = Field(description="ID of entity that received the merge")
    merged_at: datetime = Field(description="When the merge occurred")
    similarity_score: float = Field(
        ge=0.0, le=1.0, description="Similarity score that triggered the merge"
    )
    merged_name: str = Field(description="Name of the merged entity")
    canonical_name: str = Field(description="Name of the canonical entity")

    model_config = {
        "json_schema_extra": {
            "example": {
                "merged_id": "concept-xyz789",
                "canonical_id": "concept-abc123",
                "merged_at": "2025-01-15T12:00:00Z",
                "similarity_score": 0.92,
                "merged_name": "Auth",
                "canonical_name": "Authentication",
            }
        }
    }


class HybridSearchRequest(BaseModel):
    """Request for hybrid search combining graph and vector search."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    entity_type: EntityType | None = Field(
        default=None, alias="type", description="Filter by entity type"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum combined score")
    graph_weight: float = Field(
        default=0.4, ge=0.0, le=1.0, description="Weight for graph structure scores"
    )
    vector_weight: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Weight for vector similarity scores"
    )
    use_graph_structure: bool = Field(default=True, description="Include graph structure in search")
    use_vector_search: bool = Field(default=True, description="Include vector similarity in search")


class HybridSearchResultItem(BaseModel):
    """Single result from hybrid search."""

    entity_id: str
    entity_name: str
    entity_type: str
    graph_score: float = Field(..., ge=0.0, le=1.0)
    vector_score: float = Field(..., ge=0.0, le=1.0)
    combined_score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HybridSearchResponse(BaseResponse):
    """Response from hybrid search."""

    results: list[HybridSearchResultItem]
    total: int
    query: str
    execution_time_ms: float


class RAGQueryRequest(BaseModel):
    """Request for RAG question answering."""

    question: str = Field(..., min_length=1, max_length=1000, description="Question to answer")
    entity_type: EntityType | None = Field(
        default=None, alias="type", description="Filter context by entity type"
    )
    context_limit: int = Field(
        default=5, ge=1, le=20, description="Maximum entities to use as context"
    )
    include_sources: bool = Field(default=True, description="Include source entity citations")


class RAGQueryResponse(BaseResponse):
    """Response from RAG question answering."""

    answer: str = Field(..., description="Generated answer to the question")
    sources: list[str] = Field(default_factory=list, description="Entity IDs used as context")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the answer")
    context_entities: list[dict[str, Any]] = Field(
        default_factory=list, description="Entities used as context"
    )
    search_results_count: int = Field(..., description="Number of entities found in search")
    execution_time_ms: float = Field(..., description="Time taken to generate answer")


class DeduplicationStatsResponse(BaseResponse):
    """Statistics about entity deduplication."""

    total_merges: int = Field(description="Total number of merge operations")
    avg_similarity: float = Field(description="Average similarity score of merges")
    unique_canonical_ids: int = Field(description="Number of unique canonical entities with merges")
    recent_merges: list[MergeRecordResponse] = Field(
        default_factory=list, description="Recent merge operations"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "total_merges": 45,
                "avg_similarity": 0.89,
                "unique_canonical_ids": 30,
                "recent_merges": [
                    {
                        "merged_id": "concept-xyz",
                        "canonical_id": "concept-abc",
                        "merged_at": "2025-01-15T12:00:00Z",
                        "similarity_score": 0.92,
                        "merged_name": "Auth",
                        "canonical_name": "Authentication",
                    }
                ],
            }
        }
    }
