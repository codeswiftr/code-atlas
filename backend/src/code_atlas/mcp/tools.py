"""MCP tool definitions for Code Atlas.

Defines tools that can be called via MCP protocol:
- query_graph - Execute Cypher query
- search_entities - Search entities by name/type
- get_insights - Get insights (top entities, recurring problems)
- process_sessions - Submit sessions for processing
"""

from __future__ import annotations

from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


class ToolManager:
    """Manages MCP tools for Code Atlas."""

    def __init__(self, graph_populator: Any) -> None:
        """Initialize tool manager.

        Args:
            graph_populator: GraphPopulator instance for graph operations.
        """
        self.graph = graph_populator
        logger.info("MCP ToolManager initialized")

    async def list_all(self) -> list[dict[str, Any]]:
        """List all available tools.

        Returns:
            List of tool definitions with schemas.
        """
        return [
            {
                "name": "query_graph",
                "description": "Execute a read-only Cypher query against the knowledge graph",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Cypher query to execute (read-only, MATCH/RETURN only)",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Query parameters",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 100,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_entities",
                "description": "Search entities by name or type",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (entity name)",
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": ["Concept", "File", "Tool", "Problem", "Solution"],
                            "description": "Filter by entity type",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_insights",
                "description": "Get insights from the knowledge graph",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "insight_type": {
                            "type": "string",
                            "enum": ["top-entities", "recurring-problems", "popular-tools"],
                            "description": "Type of insight to retrieve",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 10,
                        },
                    },
                    "required": ["insight_type"],
                },
            },
            {
                "name": "process_sessions",
                "description": "Submit sessions for processing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of session file paths to process",
                        },
                        "use_llm": {
                            "type": "boolean",
                            "description": "Use LLM for extraction",
                            "default": True,
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Validate without writing to database",
                            "default": False,
                        },
                    },
                    "required": ["session_paths"],
                },
            },
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            name: Tool name to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result.
        """
        if name == "query_graph":
            return await self._query_graph(
                arguments.get("query", ""),
                arguments.get("parameters", {}),
                arguments.get("limit", 100),
            )
        elif name == "search_entities":
            return await self._search_entities(
                arguments.get("query", ""),
                arguments.get("entity_type"),
                arguments.get("limit", 20),
            )
        elif name == "get_insights":
            return await self._get_insights(
                arguments.get("insight_type", ""),
                arguments.get("limit", 10),
            )
        elif name == "process_sessions":
            return await self._process_sessions(
                arguments.get("session_paths", []),
                arguments.get("use_llm", True),
                arguments.get("dry_run", False),
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def _query_graph(
        self,
        query: str,
        parameters: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        """Execute Cypher query."""
        # Security: Only allow read queries
        query_upper = query.upper().strip()
        if any(keyword in query_upper for keyword in ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "DROP"]):
            return {
                "error": "Only read queries are allowed (MATCH, RETURN, etc.)",
            }

        try:
            # Add limit if not present
            if "LIMIT" not in query_upper:
                query = f"{query} LIMIT {limit}"

            results = self.graph.execute_query(query, parameters)
            return {
                "results": results,
                "count": len(results),
            }
        except Exception as exc:
            logger.error("Graph query failed", error=str(exc))
            return {
                "error": str(exc),
            }

    async def _search_entities(
        self,
        query: str,
        entity_type: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Search entities."""
        try:
            if entity_type:
                cypher_query = f"""
                    MATCH (e:{entity_type})
                    WHERE toLower(e.name) CONTAINS toLower($query)
                    RETURN e.id as id, e.name as name, labels(e)[0] as type
                    LIMIT $limit
                """
            else:
                cypher_query = """
                    MATCH (e)
                    WHERE toLower(e.name) CONTAINS toLower($query)
                    RETURN e.id as id, e.name as name, labels(e)[0] as type
                    LIMIT $limit
                """

            results = self.graph.execute_query(cypher_query, {"query": query, "limit": limit})
            return {
                "entities": results,
                "count": len(results),
            }
        except Exception as exc:
            logger.error("Entity search failed", error=str(exc))
            return {
                "error": str(exc),
            }

    async def _get_insights(
        self,
        insight_type: str,
        limit: int,
    ) -> dict[str, Any]:
        """Get insights."""
        insight_queries = {
            "top-entities": """
                MATCH (e)
                WHERE e.mention_count > 0
                RETURN e.id as id, e.name as name, e.mention_count as mentions, labels(e)[0] as type
                ORDER BY mentions DESC
                LIMIT $limit
            """,
            "recurring-problems": """
                MATCH (p:Problem)
                WITH p, count(DISTINCT p.source_session) as session_count
                WHERE session_count >= 2
                RETURN p.id as id, p.name as name, session_count
                ORDER BY session_count DESC
                LIMIT $limit
            """,
            "popular-tools": """
                MATCH (t:Tool)-[r:USES]-(e)
                WITH t, count(r) as usage_count
                RETURN t.id as id, t.name as name, usage_count
                ORDER BY usage_count DESC
                LIMIT $limit
            """,
        }

        query = insight_queries.get(insight_type)
        if not query:
            return {
                "error": f"Unknown insight type: {insight_type}",
            }

        try:
            results = self.graph.execute_query(query, {"limit": limit})
            return {
                "insight_type": insight_type,
                "data": results,
                "count": len(results),
            }
        except Exception as exc:
            logger.error("Insight retrieval failed", insight_type=insight_type, error=str(exc))
            return {
                "error": str(exc),
            }

    async def _process_sessions(
        self,
        session_paths: list[str],
        use_llm: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """Process sessions (placeholder - would integrate with pipeline)."""
        # This would integrate with the actual session processing pipeline
        return {
            "message": "Session processing initiated",
            "session_count": len(session_paths),
            "use_llm": use_llm,
            "dry_run": dry_run,
            "note": "Full implementation requires pipeline integration",
        }
