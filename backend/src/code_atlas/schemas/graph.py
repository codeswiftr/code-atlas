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

    class Config:
        json_schema_extra = {
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

    class Config:
        json_schema_extra = {
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

    class Config:
        json_schema_extra = {
            "example": {
                "query": "MATCH (e:Concept) WHERE e.name CONTAINS $search RETURN e LIMIT $limit",
                "parameters": {"search": "auth"},
                "limit": 50,
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

    class Config:
        json_schema_extra = {
            "example": {
                "id": "concept-abc123",
                "label": "Authentication",
                "type": "Concept",
                "size": 15.0,
                "color": "#A78BFA",
                "properties": {"mention_count": 5},
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

    class Config:
        json_schema_extra = {
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


class GraphVisualizationResponse(BaseResponse):
    """Response with graph data for visualization."""

    nodes: list[NodeData]
    edges: list[EdgeData]
    node_count: int
    edge_count: int
    layout_hint: str = "force"

    class Config:
        json_schema_extra = {
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
