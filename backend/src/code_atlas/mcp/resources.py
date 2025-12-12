"""MCP resource definitions for Code Atlas.

Defines resources that can be accessed via MCP protocol:
- sessions://* - Session resources
- entities://* - Entity resources
- insights://* - Insight resources
- graph://* - Graph visualization data
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..logging_config import get_logger

logger = get_logger(__name__)


class ResourceManager:
    """Manages MCP resources for Code Atlas."""

    def __init__(self, graph_populator: Any) -> None:
        """Initialize resource manager.

        Args:
            graph_populator: GraphPopulator instance for graph queries.
        """
        self.graph = graph_populator
        logger.info("MCP ResourceManager initialized")

    async def list_all(self) -> list[dict[str, Any]]:
        """List all available resources.

        Returns:
            List of resource definitions.
        """
        resources = []

        # List session resources
        try:
            sessions = await self._list_sessions()
            for session in sessions:
                resources.append({
                    "uri": f"sessions://{session['id']}",
                    "name": session.get("name", session["id"]),
                    "description": f"Session: {session.get('project_name', 'Unknown')}",
                    "mimeType": "application/json",
                })
        except Exception as exc:
            logger.warning("Failed to list sessions", error=str(exc))

        # List entity resources (sample)
        try:
            entities = await self._list_sample_entities()
            for entity in entities:
                resources.append({
                    "uri": f"entities://{entity['id']}",
                    "name": entity.get("name", entity["id"]),
                    "description": f"Entity: {entity.get('type', 'Unknown')}",
                    "mimeType": "application/json",
                })
        except Exception as exc:
            logger.warning("Failed to list entities", error=str(exc))

        return resources

    async def get(self, uri: str) -> dict[str, Any]:
        """Get a specific resource by URI.

        Args:
            uri: Resource URI (e.g., "sessions://session-123")

        Returns:
            Resource data as dictionary.
        """
        parsed = urlparse(uri)

        if parsed.scheme == "sessions":
            session_id = parsed.path.lstrip("/")
            return await self._get_session(session_id)

        elif parsed.scheme == "entities":
            entity_id = parsed.path.lstrip("/")
            return await self._get_entity(entity_id)

        elif parsed.scheme == "insights":
            insight_type = parsed.path.lstrip("/")
            return await self._get_insight(insight_type)

        elif parsed.scheme == "graph":
            return await self._get_graph_data()

        else:
            raise ValueError(f"Unknown resource scheme: {parsed.scheme}")

    async def _list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        query = """
            MATCH (s:Session)
            RETURN s.id as id, s.project as project_name, s.modified_at as modified_at
            ORDER BY s.modified_at DESC
            LIMIT 100
        """
        try:
            results = self.graph.execute_query(query, {})
            return [
                {
                    "id": row.get("id", ""),
                    "project_name": row.get("project_name", "Unknown"),
                    "modified_at": row.get("modified_at"),
                }
                for row in results
            ]
        except Exception as exc:
            logger.error("Failed to list sessions", error=str(exc))
            return []

    async def _list_sample_entities(self) -> list[dict[str, Any]]:
        """List sample entities."""
        query = """
            MATCH (e)
            RETURN e.id as id, e.name as name, labels(e)[0] as type
            LIMIT 50
        """
        try:
            results = self.graph.execute_query(query, {})
            return [
                {
                    "id": row.get("id", ""),
                    "name": row.get("name", ""),
                    "type": row.get("type", "Concept"),
                }
                for row in results
            ]
        except Exception as exc:
            logger.error("Failed to list entities", error=str(exc))
            return []

    async def _get_session(self, session_id: str) -> dict[str, Any]:
        """Get session resource."""
        query = """
            MATCH (s:Session {id: $session_id})
            OPTIONAL MATCH (s)-[r]-(e)
            RETURN s, collect(DISTINCT {rel: type(r), entity: e.name, entity_type: labels(e)[0]}) as entities
            LIMIT 1
        """
        try:
            results = self.graph.execute_query(query, {"session_id": session_id})
            if not results:
                raise ValueError(f"Session not found: {session_id}")

            row = results[0]
            session = row.get("s", {})
            entities = row.get("entities", [])

            return {
                "id": session.get("id", session_id),
                "project": session.get("project", "Unknown"),
                "modified_at": session.get("modified_at"),
                "entities": entities,
                "metadata": dict(session),
            }
        except Exception as exc:
            logger.error("Failed to get session", session_id=session_id, error=str(exc))
            raise

    async def _get_entity(self, entity_id: str) -> dict[str, Any]:
        """Get entity resource."""
        query = """
            MATCH (e {id: $entity_id})
            OPTIONAL MATCH (e)-[r]-(related)
            RETURN e, labels(e) as labels,
                   collect(DISTINCT {rel: type(r), target: related.name, target_type: labels(related)[0]}) as relationships
            LIMIT 1
        """
        try:
            results = self.graph.execute_query(query, {"entity_id": entity_id})
            if not results:
                raise ValueError(f"Entity not found: {entity_id}")

            row = results[0]
            entity = row.get("e", {})
            labels = row.get("labels", [])
            relationships = row.get("relationships", [])

            return {
                "id": entity.get("id", entity_id),
                "name": entity.get("name", entity_id),
                "type": labels[0] if labels else "Concept",
                "properties": dict(entity),
                "relationships": relationships,
            }
        except Exception as exc:
            logger.error("Failed to get entity", entity_id=entity_id, error=str(exc))
            raise

    async def _get_insight(self, insight_type: str) -> dict[str, Any]:
        """Get insight resource."""
        # Map insight types to queries
        insight_queries = {
            "top-entities": """
                MATCH (e)
                WHERE e.mention_count > 0
                RETURN e, e.mention_count as mentions, labels(e)[0] as type
                ORDER BY mentions DESC
                LIMIT 10
            """,
            "recurring-problems": """
                MATCH (p:Problem)
                WITH p, count(DISTINCT p.source_session) as session_count
                WHERE session_count >= 2
                RETURN p, session_count
                ORDER BY session_count DESC
                LIMIT 10
            """,
        }

        query = insight_queries.get(insight_type)
        if not query:
            raise ValueError(f"Unknown insight type: {insight_type}")

        try:
            results = self.graph.execute_query(query, {})
            return {
                "type": insight_type,
                "data": results,
                "count": len(results),
            }
        except Exception as exc:
            logger.error("Failed to get insight", insight_type=insight_type, error=str(exc))
            raise

    async def _get_graph_data(self) -> dict[str, Any]:
        """Get graph visualization data."""
        query = """
            MATCH (e)
            OPTIONAL MATCH (e)-[r]-(related)
            RETURN e, labels(e) as labels, collect(DISTINCT type(r)) as rel_types
            LIMIT 100
        """
        try:
            results = self.graph.execute_query(query, {})
            return {
                "nodes": [
                    {
                        "id": row.get("e", {}).get("id", ""),
                        "type": row.get("labels", ["Concept"])[0],
                        "name": row.get("e", {}).get("name", ""),
                    }
                    for row in results
                ],
                "count": len(results),
            }
        except Exception as exc:
            logger.error("Failed to get graph data", error=str(exc))
            raise
