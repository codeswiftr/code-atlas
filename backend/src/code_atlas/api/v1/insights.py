"""Insights and reports API endpoints."""

import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from anthropic import Anthropic
from fastapi import APIRouter, HTTPException, Query, status

from ...logging_config import get_logger
from ...schemas.graph import (
    EntityType,
    RAGQueryRequest,
    RAGQueryResponse,
)
from ..dependencies import ApiKey, Graph
from .graph import _parse_node_to_entity

logger = get_logger(__name__)
router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/top-entities")
async def get_top_entities(
    graph: Graph,
    api_key: ApiKey,
    limit: int = Query(default=10, ge=1, le=100),
    entity_type: EntityType | None = Query(default=None, alias="type"),  # noqa: B008
) -> dict[str, Any]:
    """Get most mentioned entities."""
    try:
        start_time = time.time()

        # Build query based on entity type filter
        if entity_type:
            query = f"""
                MATCH (e:{entity_type.value})
                WHERE e.mention_count > 0
                RETURN e, e.mention_count as mentions, labels(e) as labels
                ORDER BY mentions DESC
                LIMIT $limit
            """
        else:
            query = """
                MATCH (e)
                WHERE e.mention_count > 0
                RETURN e, e.mention_count as mentions, labels(e) as labels
                ORDER BY mentions DESC
                LIMIT $limit
            """

        result = graph.execute_query(query, {"limit": limit})

        entities = []
        for row in result:
            node = row.get("e", {})
            labels = row.get("labels", ["Concept"])
            node_type = labels[0] if labels else "Concept"
            entity = _parse_node_to_entity(node, node_type)
            entity.mention_count = row.get("mentions", 0)
            entities.append(entity)

        execution_time = (time.time() - start_time) * 1000

        return {
            "entities": [e.dict() for e in entities],
            "total": len(entities),
            "entity_type": entity_type.value if entity_type else None,
            "execution_time_ms": execution_time,
            "message": f"Found {len(entities)} top entities",
        }
    except Exception as exc:
        logger.error("Top entities query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top entities: {str(exc)}",
        ) from exc


@router.get("/recurring-problems")
async def get_recurring_problems(
    graph: Graph,
    api_key: ApiKey,
    min_sessions: int = Query(default=2, ge=1, description="Minimum number of sessions"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Get problems that appear in multiple sessions."""
    try:
        start_time = time.time()

        query = """
            MATCH (p:Problem)
            WITH p, count(DISTINCT p.source_session) as session_count
            WHERE session_count >= $min_sessions
            RETURN p, session_count, labels(p) as labels
            ORDER BY session_count DESC, p.mention_count DESC
            LIMIT $limit
        """

        result = graph.execute_query(query, {"min_sessions": min_sessions, "limit": limit})

        problems = []
        for row in result:
            node = row.get("p", {})
            entity = _parse_node_to_entity(node, "Problem")
            entity.mention_count = row.get("session_count", 0)
            problems.append(
                {
                    "entity": entity.dict(),
                    "session_count": row.get("session_count", 0),
                }
            )

        execution_time = (time.time() - start_time) * 1000

        return {
            "problems": problems,
            "total": len(problems),
            "min_sessions": min_sessions,
            "execution_time_ms": execution_time,
            "message": f"Found {len(problems)} recurring problems",
        }
    except Exception as exc:
        logger.error("Recurring problems query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recurring problems: {str(exc)}",
        ) from exc


@router.get("/popular-tools")
async def get_popular_tools(
    graph: Graph,
    api_key: ApiKey,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Get most used tools."""
    try:
        start_time = time.time()

        query = """
            MATCH (t:Tool)-[r:USES]-(e)
            WITH t, count(r) as usage_count
            RETURN t, usage_count, labels(t) as labels
            ORDER BY usage_count DESC
            LIMIT $limit
        """

        result = graph.execute_query(query, {"limit": limit})

        tools = []
        for row in result:
            node = row.get("t", {})
            entity = _parse_node_to_entity(node, "Tool")
            entity.mention_count = row.get("usage_count", 0)
            tools.append(
                {
                    "entity": entity.dict(),
                    "usage_count": row.get("usage_count", 0),
                }
            )

        execution_time = (time.time() - start_time) * 1000

        return {
            "tools": tools,
            "total": len(tools),
            "execution_time_ms": execution_time,
            "message": f"Found {len(tools)} popular tools",
        }
    except Exception as exc:
        logger.error("Popular tools query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get popular tools: {str(exc)}",
        ) from exc


@router.get("/concept-relationships")
async def get_concept_relationships(
    graph: Graph,
    api_key: ApiKey,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Get relationship patterns between concepts."""
    try:
        start_time = time.time()

        query = """
            MATCH (a:Concept)-[r]->(b:Concept)
            WITH type(r) as rel_type, count(r) as count
            ORDER BY count DESC
            LIMIT $limit
        """

        result = graph.execute_query(query, {"limit": limit})

        relationships = []
        for row in result:
            relationships.append(
                {
                    "relationship_type": row.get("rel_type", "RELATED_TO"),
                    "count": row.get("count", 0),
                }
            )

        # Get most connected concept pairs
        pair_query = """
            MATCH (a:Concept)-[r]->(b:Concept)
            WITH a, b, count(r) as connection_strength
            ORDER BY connection_strength DESC
            LIMIT 20
            RETURN a.name as source, b.name as target, connection_strength,
                   labels(a) as source_labels, labels(b) as target_labels
        """

        pair_result = graph.execute_query(pair_query, {})

        pairs = []
        for row in pair_result:
            pairs.append(
                {
                    "source": row.get("source", ""),
                    "target": row.get("target", ""),
                    "connection_strength": row.get("connection_strength", 0),
                }
            )

        execution_time = (time.time() - start_time) * 1000

        return {
            "relationship_types": relationships,
            "top_pairs": pairs,
            "total_relationships": sum(r["count"] for r in relationships),
            "execution_time_ms": execution_time,
            "message": f"Found {len(relationships)} relationship types",
        }
    except Exception as exc:
        logger.error("Concept relationships query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get concept relationships: {str(exc)}",
        ) from exc


@router.get("/trends")
async def get_trends(
    graph: Graph,
    api_key: ApiKey,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
) -> dict[str, Any]:
    """Get time-based trends for entity creation."""
    try:
        start_time = time.time()

        # Get entities created over time
        query = """
            MATCH (e)
            WHERE e.created_at IS NOT NULL
            WITH e, date(e.created_at) as created_date
            RETURN created_date, count(e) as entity_count, labels(e)[0] as entity_type
            ORDER BY created_date DESC
            LIMIT 1000
        """

        result = graph.execute_query(query, {})

        # Group by date and type
        trends_by_date: dict[str, dict[str, int]] = {}
        trends_by_type: dict[str, list[dict[str, Any]]] = {}

        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        for row in result:
            created_date_str = row.get("created_date", "")
            if not created_date_str:
                continue

            try:
                created_date = datetime.fromisoformat(created_date_str.replace("Z", "+00:00"))
                if created_date < cutoff_date:
                    continue
            except (ValueError, AttributeError):
                continue

            date_key = created_date.strftime("%Y-%m-%d")
            entity_type = row.get("entity_type", "Concept")
            count = row.get("entity_count", 0)

            if date_key not in trends_by_date:
                trends_by_date[date_key] = {}
            trends_by_date[date_key][entity_type] = (
                trends_by_date[date_key].get(entity_type, 0) + count
            )

            if entity_type not in trends_by_type:
                trends_by_type[entity_type] = []
            trends_by_type[entity_type].append(
                {
                    "date": date_key,
                    "count": count,
                }
            )

        # Convert to sorted lists
        trend_data = [
            {
                "date": date,
                "counts": counts,
                "total": sum(counts.values()),
            }
            for date, counts in sorted(trends_by_date.items())
        ]

        execution_time = (time.time() - start_time) * 1000

        return {
            "trends": trend_data,
            "trends_by_type": {
                entity_type: sorted(data, key=lambda x: x["date"])
                for entity_type, data in trends_by_type.items()
            },
            "days_analyzed": days,
            "execution_time_ms": execution_time,
            "message": f"Trends for last {days} days",
        }
    except Exception as exc:
        logger.error("Trends query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trends: {str(exc)}",
        ) from exc


@router.get("/reports")
async def get_insight_report(
    graph: Graph,
    api_key: ApiKey,
) -> dict[str, Any]:
    """Generate comprehensive insight report."""
    try:
        start_time = time.time()

        # Get top entities
        top_entities_query = """
            MATCH (e)
            WHERE e.mention_count > 0
            RETURN e, e.mention_count as mentions, labels(e) as labels
            ORDER BY mentions DESC
            LIMIT 10
        """
        top_entities_result = graph.execute_query(top_entities_query, {})
        top_entities = []
        for row in top_entities_result:
            node = row.get("e", {})
            labels = row.get("labels", ["Concept"])
            entity = _parse_node_to_entity(node, labels[0] if labels else "Concept")
            entity.mention_count = row.get("mentions", 0)
            top_entities.append(entity.dict())

        # Get recurring problems
        problems_query = """
            MATCH (p:Problem)
            WITH p, count(DISTINCT p.source_session) as session_count
            WHERE session_count >= 2
            RETURN p, session_count
            ORDER BY session_count DESC
            LIMIT 10
        """
        problems_result = graph.execute_query(problems_query, {})
        recurring_problems = []
        for row in problems_result:
            node = row.get("p", {})
            entity = _parse_node_to_entity(node, "Problem")
            recurring_problems.append(
                {
                    "entity": entity.dict(),
                    "session_count": row.get("session_count", 0),
                }
            )

        # Get popular tools
        tools_query = """
            MATCH (t:Tool)-[r:USES]-(e)
            WITH t, count(r) as usage_count
            RETURN t, usage_count
            ORDER BY usage_count DESC
            LIMIT 10
        """
        tools_result = graph.execute_query(tools_query, {})
        popular_tools = []
        for row in tools_result:
            node = row.get("t", {})
            entity = _parse_node_to_entity(node, "Tool")
            popular_tools.append(
                {
                    "entity": entity.dict(),
                    "usage_count": row.get("usage_count", 0),
                }
            )

        # Get graph stats
        stats_query = """
            MATCH (e)
            WITH count(e) as total_nodes, labels(e)[0] as node_type
            RETURN node_type, total_nodes
        """
        graph.execute_query(stats_query, {})  # Execute query for completeness

        execution_time = (time.time() - start_time) * 1000

        return {
            "top_entities": top_entities,
            "recurring_problems": recurring_problems,
            "popular_tools": popular_tools,
            "generated_at": datetime.now(UTC).isoformat(),
            "execution_time_ms": execution_time,
            "message": "Insight report generated",
        }
    except Exception as exc:
        logger.error("Insight report generation failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(exc)}",
        ) from exc


# RAG endpoint - create new router file or add here


def _get_anthropic_client() -> Anthropic | None:
    """Create Anthropic client from environment if API key is configured.

    Returns None if ANTHROPIC_API_KEY is not set, enabling graceful fallback
    to context-based answers without LLM.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set, RAG will use fallback answers")
        return None
    return Anthropic(api_key=api_key)


@router.post(
    "/rag/query",
    response_model=RAGQueryResponse,
    summary="RAG question answering",
    description=(
        "Answer natural language questions using retrieval-augmented generation"
        " over the knowledge graph."
    ),
)
async def rag_query(
    request: RAGQueryRequest,
    graph: Graph,
    api_key: ApiKey,
) -> RAGQueryResponse:
    """Answer a question using RAG over the knowledge graph."""
    try:
        start_time = time.time()

        # Import RAG service and dependencies
        from ...rag_service import create_rag_service
        from ...vector_store import create_vector_store

        # Create Anthropic client (returns None if API key not configured)
        llm_client = _get_anthropic_client()

        # Create vector store and RAG service
        vector_store = create_vector_store("falkordb", graph_populator=graph)
        rag_service = create_rag_service(
            graph_populator=graph,
            vector_store=vector_store,
            llm_client=llm_client,
        )

        # Answer question
        result = rag_service.answer_question(
            question=request.question,
            entity_type=request.entity_type.value if request.entity_type else None,
            include_sources=request.include_sources,
        )

        execution_time = (time.time() - start_time) * 1000

        return RAGQueryResponse(
            success=True,
            answer=result["answer"],
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            context_entities=result.get("context_entities", []),
            search_results_count=result.get("search_results_count", 0),
            execution_time_ms=execution_time,
            message="Question answered successfully",
        )

    except Exception as exc:
        logger.error("RAG query failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(exc)}",
        ) from exc
