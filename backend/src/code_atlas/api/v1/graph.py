"""Knowledge graph API endpoints."""

import time
from difflib import SequenceMatcher
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from ...logging_config import get_logger
from ..dependencies import Graph, ApiKey
from ...schemas.graph import (
    EntityType,
    RelationshipType,
    EntityResponse,
    EntityListResponse,
    EntitySearchResponse,
    EntitySearchResult,
    RelationshipResponse,
    RelationshipListResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphVisualizationResponse,
    NodeData,
    EdgeData,
    GraphStatsResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResultItem,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

# Color mapping for entity types (from design system)
ENTITY_COLORS = {
    EntityType.SESSION: "#38BDF8",  # Electric Blue
    EntityType.CONCEPT: "#A78BFA",  # Purple
    EntityType.FILE: "#34D399",  # Green
    EntityType.TOOL: "#FB923C",  # Orange
    EntityType.PROBLEM: "#F87171",  # Red
    EntityType.SOLUTION: "#10B981",  # Emerald
}

# Color mapping for relationship types
RELATIONSHIP_COLORS = {
    RelationshipType.MENTIONS: "#64748B",
    RelationshipType.REFERENCES: "#94A3B8",
    RelationshipType.SOLVES: "#10B981",
    RelationshipType.USES: "#38BDF8",
    RelationshipType.RELATED_TO: "#A78BFA",
}


def _parse_node_to_entity(node: dict[str, Any], node_type: str) -> EntityResponse:
    """Convert a FalkorDB node to EntityResponse."""
    properties = dict(node)
    entity_id = properties.pop("id", f"{node_type.lower()}-{hash(str(node))}")
    name = properties.pop("name", properties.pop("title", str(entity_id)))
    confidence = properties.pop("confidence", None)
    source_session = properties.pop("source_session", None)
    created_at = properties.pop("created_at", None)
    mention_count = properties.pop("mention_count", 0)

    return EntityResponse(
        id=str(entity_id),
        type=EntityType(node_type) if node_type in EntityType.__members__.values() else EntityType.CONCEPT,
        name=str(name),
        properties=properties,
        confidence=float(confidence) if confidence else None,
        source_session=source_session,
        created_at=created_at,
        mention_count=int(mention_count) if mention_count else 0,
    )


def _calculate_similarity(query: str, text: str) -> float:
    """Calculate similarity score between query and text.

    Uses case-insensitive sequence matching for fuzzy comparison.
    Returns a score between 0.0 and 1.0.
    """
    query_lower = query.lower()
    text_lower = text.lower()

    # Exact match
    if query_lower == text_lower:
        return 1.0

    # Contains match (higher weight for substring matches)
    if query_lower in text_lower:
        # Score based on how much of the text the query covers
        return 0.8 + (0.2 * len(query) / len(text))

    # Fuzzy match using SequenceMatcher
    return SequenceMatcher(None, query_lower, text_lower).ratio()


def _highlight_match(query: str, text: str) -> str:
    """Highlight matching portion of text with markdown bold."""
    query_lower = query.lower()
    text_lower = text.lower()

    if query_lower not in text_lower:
        return text

    start = text_lower.find(query_lower)
    end = start + len(query)

    return f"{text[:start]}**{text[start:end]}**{text[end:]}"


@router.get(
    "/entities",
    response_model=EntityListResponse,
    summary="List entities",
    description="List entities from the knowledge graph with optional filtering.",
)
async def list_entities(
    graph: Graph,
    api_key: ApiKey,
    entity_type: Annotated[EntityType | None, Query(alias="type")] = None,
    search: str | None = Query(default=None, min_length=1, max_length=200),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> EntityListResponse:
    """List entities from the knowledge graph."""
    logger.info(
        "Listing entities",
        entity_type=entity_type,
        search=search,
        page=page,
    )

    try:
        # Build Cypher query
        where_clauses = []
        params: dict[str, Any] = {}

        if entity_type:
            label = entity_type.value
            base_query = f"MATCH (e:{label})"
        else:
            base_query = "MATCH (e)"

        if search:
            where_clauses.append("e.name CONTAINS $search")
            params["search"] = search

        if min_confidence > 0:
            where_clauses.append("e.confidence >= $min_confidence")
            params["min_confidence"] = min_confidence

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count query
        count_query = f"{base_query}{where_str} RETURN count(e) as total"

        # Data query with pagination
        skip = (page - 1) * page_size
        params["skip"] = skip
        params["limit"] = page_size
        data_query = f"{base_query}{where_str} RETURN e, labels(e) as labels ORDER BY e.name SKIP $skip LIMIT $limit"

        # Execute queries
        count_result = graph.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        data_result = graph.execute_query(data_query, params)

        entities = []
        for row in data_result:
            node = row.get("e", {})
            labels = row.get("labels", ["Concept"])
            node_type = labels[0] if labels else "Concept"
            entities.append(_parse_node_to_entity(node, node_type))

        return EntityListResponse(
            entities=entities,
            total=total,
            page=page,
            page_size=page_size,
            message=f"Found {total} entities",
        )

    except Exception as exc:
        logger.error("Entity listing failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list entities: {str(exc)}",
        )


@router.get(
    "/entities/search",
    response_model=EntitySearchResponse,
    summary="Search entities",
    description="Full-text search across entity names with fuzzy matching and relevance scoring.",
)
async def search_entities(
    graph: Graph,
    api_key: ApiKey,
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    entity_type: Annotated[EntityType | None, Query(alias="type")] = None,
    fuzzy: bool = Query(default=True, description="Enable fuzzy matching"),
    min_score: float = Query(default=0.3, ge=0.0, le=1.0, description="Minimum relevance score"),
    limit: int = Query(default=20, ge=1, le=100),
) -> EntitySearchResponse:
    """Full-text search across entity names.

    Returns relevance-ranked results with scores.
    Supports fuzzy matching for typo tolerance.
    """
    start_time = time.time()

    logger.info(
        "Searching entities",
        query=q,
        entity_type=entity_type,
        fuzzy=fuzzy,
    )

    try:
        # Build query to get all candidate entities
        if entity_type:
            base_query = f"MATCH (e:{entity_type.value})"
        else:
            base_query = "MATCH (e)"

        # Get candidates (all entities or filtered by type)
        # For efficiency, we fetch more than needed and filter client-side
        data_query = f"{base_query} RETURN e, labels(e) as labels LIMIT 1000"
        data_result = graph.execute_query(data_query, {})

        # Score and filter results
        scored_results: list[tuple[EntityResponse, float, list[str]]] = []

        for row in data_result:
            node = row.get("e", {})
            labels = row.get("labels", ["Concept"])
            node_type = labels[0] if labels else "Concept"

            name = node.get("name", node.get("title", ""))
            if not name:
                continue

            # Calculate similarity score
            score = _calculate_similarity(q, name)

            # For non-fuzzy search, require exact substring match
            if not fuzzy and q.lower() not in name.lower():
                continue

            # Filter by minimum score
            if score < min_score:
                continue

            entity = _parse_node_to_entity(node, node_type)

            # Generate highlights
            highlights = []
            if q.lower() in name.lower():
                highlights.append(_highlight_match(q, name))

            scored_results.append((entity, score, highlights))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Apply limit
        scored_results = scored_results[:limit]

        # Build response
        results = [
            EntitySearchResult(
                entity=entity,
                score=round(score, 3),
                highlights=highlights,
            )
            for entity, score, highlights in scored_results
        ]

        took_ms = (time.time() - start_time) * 1000

        return EntitySearchResponse(
            results=results,
            total=len(results),
            query=q,
            took_ms=round(took_ms, 2),
            message=f"Found {len(results)} matching entities",
        )

    except Exception as exc:
        logger.error("Entity search failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search entities: {str(exc)}",
        )


@router.post(
    "/hybrid-search",
    response_model=HybridSearchResponse,
    summary="Hybrid search",
    description="Search entities using both graph structure and semantic vector similarity.",
)
async def hybrid_search(
    request: HybridSearchRequest,
    graph: Graph,
    api_key: ApiKey,
) -> HybridSearchResponse:
    """Perform hybrid search combining Cypher queries with vector similarity."""
    try:
        start_time = time.time()

        # Import here to avoid circular dependencies
        from ...hybrid_search import HybridSearch
        from ...vector_store import create_vector_store

        # Create vector store and hybrid search instances
        vector_store = create_vector_store("falkordb", graph_populator=graph)
        hybrid_search_instance = HybridSearch(
            graph_populator=graph,
            vector_store=vector_store,
            graph_weight=request.graph_weight,
            vector_weight=request.vector_weight,
        )

        # Perform hybrid search
        search_results = hybrid_search_instance.search(
            query=request.query,
            entity_type=request.entity_type.value if request.entity_type else None,
            limit=request.limit,
            min_score=request.min_score,
            use_graph_structure=request.use_graph_structure,
            use_vector_search=request.use_vector_search,
        )

        # Convert to response format
        result_items = [
            HybridSearchResultItem(
                entity_id=r.entity_id,
                entity_name=r.entity_name,
                entity_type=r.entity_type,
                graph_score=r.graph_score,
                vector_score=r.vector_score,
                combined_score=r.combined_score,
                metadata=r.metadata,
            )
            for r in search_results
        ]

        execution_time = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            success=True,
            results=result_items,
            total=len(result_items),
            query=request.query,
            execution_time_ms=execution_time,
            message=f"Hybrid search found {len(result_items)} results",
        )

    except Exception as exc:
        logger.error("Hybrid search failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid search failed: {str(exc)}",
        )


@router.get(
    "/entities/{entity_id}",
    response_model=EntityResponse,
    summary="Get entity",
    description="Get a single entity by ID.",
)
async def get_entity(
    entity_id: str,
    graph: Graph,
    api_key: ApiKey,
) -> EntityResponse:
    """Get a single entity by ID."""
    try:
        query = "MATCH (e {id: $id}) RETURN e, labels(e) as labels"
        result = graph.execute_query(query, {"id": entity_id})

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity not found: {entity_id}",
            )

        row = result[0]
        node = row.get("e", {})
        labels = row.get("labels", ["Concept"])
        node_type = labels[0] if labels else "Concept"

        return _parse_node_to_entity(node, node_type)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Entity retrieval failed", entity_id=entity_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity: {str(exc)}",
        )


@router.get(
    "/relationships",
    response_model=RelationshipListResponse,
    summary="List relationships",
    description="List relationships from the knowledge graph.",
)
async def list_relationships(
    graph: Graph,
    api_key: ApiKey,
    rel_type: Annotated[RelationshipType | None, Query(alias="type")] = None,
    source_id: str | None = None,
    target_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RelationshipListResponse:
    """List relationships from the knowledge graph."""
    logger.info(
        "Listing relationships",
        rel_type=rel_type,
        source_id=source_id,
        target_id=target_id,
    )

    try:
        where_clauses = []
        params: dict[str, Any] = {}

        if rel_type:
            rel_pattern = f"[r:{rel_type.value}]"
        else:
            rel_pattern = "[r]"

        base_query = f"MATCH (s)-{rel_pattern}->(t)"

        if source_id:
            where_clauses.append("s.id = $source_id")
            params["source_id"] = source_id

        if target_id:
            where_clauses.append("t.id = $target_id")
            params["target_id"] = target_id

        where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count query
        count_query = f"{base_query}{where_str} RETURN count(r) as total"

        # Data query
        skip = (page - 1) * page_size
        params["skip"] = skip
        params["limit"] = page_size
        data_query = f"""
            {base_query}{where_str}
            RETURN r, type(r) as rel_type, s, t, labels(s) as source_labels, labels(t) as target_labels
            SKIP $skip LIMIT $limit
        """

        count_result = graph.execute_query(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        data_result = graph.execute_query(data_query, params)

        relationships = []
        for row in data_result:
            rel = row.get("r", {})
            rel_type_str = row.get("rel_type", "RELATED_TO")
            source = row.get("s", {})
            target = row.get("t", {})
            source_labels = row.get("source_labels", ["Concept"])
            target_labels = row.get("target_labels", ["Concept"])

            relationships.append(
                RelationshipResponse(
                    id=f"rel-{hash(str(rel))}",
                    type=RelationshipType(rel_type_str) if rel_type_str in RelationshipType.__members__.values() else RelationshipType.RELATED_TO,
                    source_id=source.get("id", ""),
                    source_name=source.get("name", ""),
                    source_type=EntityType(source_labels[0]) if source_labels else EntityType.CONCEPT,
                    target_id=target.get("id", ""),
                    target_name=target.get("name", ""),
                    target_type=EntityType(target_labels[0]) if target_labels else EntityType.CONCEPT,
                    properties=dict(rel),
                    confidence=rel.get("confidence"),
                    created_at=rel.get("created_at"),
                )
            )

        return RelationshipListResponse(
            relationships=relationships,
            total=total,
            page=page,
            page_size=page_size,
            message=f"Found {total} relationships",
        )

    except Exception as exc:
        logger.error("Relationship listing failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list relationships: {str(exc)}",
        )


@router.post(
    "/query",
    response_model=GraphQueryResponse,
    summary="Execute Cypher query",
    description="Execute a read-only Cypher query against the knowledge graph.",
)
async def execute_query(
    request: GraphQueryRequest,
    graph: Graph,
    api_key: ApiKey,
) -> GraphQueryResponse:
    """Execute a Cypher query."""
    logger.info("Executing query", query=request.query[:100])

    # Security: Only allow read queries
    query_upper = request.query.upper().strip()
    if any(
        keyword in query_upper
        for keyword in ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "DROP"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only read queries are allowed (MATCH, RETURN, etc.)",
        )

    try:
        start_time = time.time()

        # Add limit to query if not present
        if "LIMIT" not in query_upper:
            query = f"{request.query} LIMIT {request.limit}"
        else:
            query = request.query

        result = graph.execute_query(query, request.parameters)

        execution_time = (time.time() - start_time) * 1000  # Convert to ms

        # Extract column names from first result
        columns = list(result[0].keys()) if result else []

        return GraphQueryResponse(
            results=result,
            columns=columns,
            row_count=len(result),
            execution_time_ms=execution_time,
            message=f"Query returned {len(result)} rows",
        )

    except Exception as exc:
        logger.error("Query execution failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query failed: {str(exc)}",
        )


@router.get(
    "/visualization",
    response_model=GraphVisualizationResponse,
    summary="Get visualization data",
    description="Get graph data formatted for visualization (D3.js, Cytoscape.js).",
)
async def get_visualization(
    graph: Graph,
    api_key: ApiKey,
    entity_type: Annotated[EntityType | None, Query(alias="type")] = None,
    center_entity_id: str | None = Query(default=None, description="Center visualization on this entity"),
    depth: int = Query(default=2, ge=1, le=5, description="Traversal depth from center entity"),
    max_nodes: int = Query(default=100, ge=1, le=500),
) -> GraphVisualizationResponse:
    """Get graph data for visualization."""
    logger.info(
        "Getting visualization data",
        entity_type=entity_type,
        center_entity_id=center_entity_id,
        depth=depth,
    )

    try:
        nodes: list[NodeData] = []
        edges: list[EdgeData] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        if center_entity_id:
            # Get subgraph centered on entity
            query = f"""
                MATCH path = (center {{id: $center_id}})-[*1..{depth}]-(connected)
                RETURN path
                LIMIT {max_nodes * 2}
            """
            params = {"center_id": center_entity_id}
        elif entity_type:
            # Get nodes of specific type
            query = f"""
                MATCH (n:{entity_type.value})-[r]-(m)
                RETURN n, r, m, labels(n) as n_labels, labels(m) as m_labels, type(r) as rel_type
                LIMIT {max_nodes * 2}
            """
            params = {}
        else:
            # Get overview of graph
            query = f"""
                MATCH (n)-[r]->(m)
                RETURN n, r, m, labels(n) as n_labels, labels(m) as m_labels, type(r) as rel_type
                LIMIT {max_nodes * 2}
            """
            params = {}

        result = graph.execute_query(query, params)

        for row in result:
            if len(nodes) >= max_nodes:
                break

            # Process nodes
            for node_key in ["n", "m", "center", "connected"]:
                if node_key in row and row[node_key]:
                    node = row[node_key]
                    node_id = str(node.get("id", hash(str(node))))

                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        labels_key = f"{node_key}_labels" if f"{node_key}_labels" in row else "labels"
                        labels = row.get(labels_key, ["Concept"])
                        node_type_str = labels[0] if labels else "Concept"

                        try:
                            node_type = EntityType(node_type_str)
                        except ValueError:
                            node_type = EntityType.CONCEPT

                        nodes.append(
                            NodeData(
                                id=node_id,
                                label=str(node.get("name", node_id)),
                                type=node_type,
                                size=10.0 + (node.get("mention_count", 0) * 2),
                                color=ENTITY_COLORS.get(node_type, "#64748B"),
                                properties={
                                    k: v
                                    for k, v in node.items()
                                    if k not in ["id", "name"]
                                },
                            )
                        )

            # Process edges
            if "r" in row and row["r"]:
                rel = row["r"]
                rel_type_str = row.get("rel_type", "RELATED_TO")

                # Get source and target from the relationship
                source_id = str(row.get("n", {}).get("id", ""))
                target_id = str(row.get("m", {}).get("id", ""))
                edge_id = f"{source_id}-{rel_type_str}-{target_id}"

                if edge_id not in seen_edges and source_id and target_id:
                    seen_edges.add(edge_id)

                    try:
                        rel_type = RelationshipType(rel_type_str)
                    except ValueError:
                        rel_type = RelationshipType.RELATED_TO

                    edges.append(
                        EdgeData(
                            id=edge_id,
                            source=source_id,
                            target=target_id,
                            type=rel_type,
                            weight=1.0 + (rel.get("confidence", 0) or 0),
                            color=RELATIONSHIP_COLORS.get(rel_type, "#64748B"),
                            properties={
                                k: v
                                for k, v in rel.items()
                                if k not in ["confidence"]
                            },
                        )
                    )

        return GraphVisualizationResponse(
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            layout_hint="force" if len(nodes) > 50 else "hierarchical",
            message=f"Visualization with {len(nodes)} nodes and {len(edges)} edges",
        )

    except Exception as exc:
        logger.error("Visualization failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get visualization: {str(exc)}",
        )


@router.get(
    "/stats",
    response_model=GraphStatsResponse,
    summary="Get graph statistics",
    description="Get statistics about the knowledge graph.",
)
async def get_stats(
    graph: Graph,
    api_key: ApiKey,
) -> GraphStatsResponse:
    """Get knowledge graph statistics."""
    try:
        # Count nodes by type
        nodes_by_type: dict[str, int] = {}
        for entity_type in EntityType:
            query = f"MATCH (n:{entity_type.value}) RETURN count(n) as count"
            result = graph.execute_query(query, {})
            nodes_by_type[entity_type.value] = result[0]["count"] if result else 0

        total_nodes = sum(nodes_by_type.values())

        # Count edges by type
        edges_by_type: dict[str, int] = {}
        for rel_type in RelationshipType:
            query = f"MATCH ()-[r:{rel_type.value}]->() RETURN count(r) as count"
            result = graph.execute_query(query, {})
            edges_by_type[rel_type.value] = result[0]["count"] if result else 0

        total_edges = sum(edges_by_type.values())

        # Average connections
        avg_connections = total_edges * 2 / total_nodes if total_nodes > 0 else 0

        # Most connected entities
        query = """
            MATCH (n)-[r]-()
            WITH n, count(r) as connections, labels(n) as labels
            ORDER BY connections DESC
            LIMIT 5
            RETURN n, connections, labels
        """
        result = graph.execute_query(query, {})

        most_connected = []
        for row in result:
            node = row.get("n", {})
            labels = row.get("labels", ["Concept"])
            node_type = labels[0] if labels else "Concept"
            entity = _parse_node_to_entity(node, node_type)
            entity.mention_count = row.get("connections", 0)
            most_connected.append(entity)

        return GraphStatsResponse(
            total_nodes=total_nodes,
            total_edges=total_edges,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            avg_connections_per_node=avg_connections,
            most_connected_entities=most_connected,
            message="Graph statistics retrieved",
        )

    except Exception as exc:
        logger.error("Stats retrieval failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(exc)}",
        )
