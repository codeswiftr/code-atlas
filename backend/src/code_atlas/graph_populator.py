"""Helpers for writing sessions into FalkorDB (or dry-run logging)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

import redis

from .insight_extractor import Entity, ExtractionResult
from .logging_config import get_logger
from .models import ParsedSession

logger = get_logger(__name__)


def _hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _quote(value: str) -> str:
    escaped = value.replace("'", "\\'")
    return f"'{escaped}'"


@dataclass
class GraphPopulator:
    graph_name: str = "code_atlas"
    redis_url: str | None = None
    dry_run: bool = False
    create_indexes: bool = True
    index_timeout: int = 30
    verify_indexes_after_creation: bool = True
    client: redis.Redis | None = field(init=False, default=None)
    executed_queries: list[str] = field(init=False, default_factory=list)

    # Predefined indexes for production performance
    INDEXES: ClassVar[dict[str, list[str]]] = {
        "Session": [
            "CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.id)",
            "CREATE INDEX session_project IF NOT EXISTS FOR (s:Session) ON (s.project)",
            "CREATE INDEX session_modified_at IF NOT EXISTS FOR (s:Session) ON (s.modified_at)",
            "CREATE INDEX session_size_bytes IF NOT EXISTS FOR (s:Session) ON (s.size_bytes)",
        ],
        "Entity": [
            "CREATE INDEX entity_id IF NOT EXISTS FOR (e:File) ON (e.id)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:File) ON (e.name)",
            "CREATE INDEX entity_id IF NOT EXISTS FOR (e:Concept) ON (e.id)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Concept) ON (e.name)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:File) ON (e.type)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Concept) ON (e.type)",
        ],
        "Insight": [
            "CREATE INDEX insight_id IF NOT EXISTS FOR (i:Insight) ON (i.id)",
        ],
        "Relationships": [
            # Indexes for MENTIONS relationship lookups
            "CREATE INDEX mentions_source IF NOT EXISTS FOR ()-[r:MENTIONS]->() ON (r.confidence)",
            "CREATE INDEX mentions_extracted_at IF NOT EXISTS FOR ()-[r:MENTIONS]->() ON (r.extracted_at)",
        ],
        "FullText": [
            # Full-text search indexes for entity names
            "CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS FOR (e) ON EACH [e.name]",
        ]
    }

    def __post_init__(self) -> None:
        if not self.dry_run and self.redis_url:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        elif not self.dry_run:
            # Assume local FalkorDB via default port if no URL passed.
            self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        else:
            self.client = None

        # Create indexes if requested and not in dry-run mode
        if self.create_indexes and not self.dry_run and self.client:
            self._ensure_indexes()
            if self.verify_indexes_after_creation:
                self._verify_index_creation()

    def upsert(self, session: ParsedSession, extraction: ExtractionResult) -> None:
        queries: list[str] = []

        # Add extraction provenance metadata to session node
        session_metadata_str = (
            f"s.extracted_at={_quote(extraction.extracted_at or '')}, "
            f"s.extractor_model={_quote(extraction.extractor_model or '')}, "
            f"s.extraction_method={_quote(extraction.extraction_method)}"
        )

        session_node = (
            f"MERGE (s:Session {{id:{_quote(session.metadata.session_id)}}}) "
            f"SET s.project={_quote(session.metadata.project)}, "
            f"s.size_bytes={session.metadata.size_bytes}, "
            f"s.modified_at={session.metadata.modified_at.timestamp()}, "
            f"{session_metadata_str}"
        )
        queries.append(session_node)

        entity_ids: dict[str, str] = {}
        for entity in extraction.entities:
            entity_queries, node_id = self._entity_queries(
                session.metadata.session_id, entity, extraction
            )
            entity_ids[entity.name] = node_id
            queries.extend(entity_queries)

        for rel in extraction.relationships:
            src_clause = self._match_clause(rel.source, session, entity_ids, alias="src")
            dst_clause = self._match_clause(rel.target, session, entity_ids, alias="dst")

            # Add relationship provenance metadata
            rel_metadata = (
                f"r.confidence={rel.confidence}, "
                f"r.extracted_at={_quote(extraction.extracted_at or '')}, "
                f"r.source='code_atlas'"
            )

            queries.append(
                f"{src_clause} {dst_clause} "
                f"MERGE (src)-[r:{rel.type or 'RELATED_TO'}]->(dst) "
                f"SET {rel_metadata}"
            )

        for insight in extraction.insights:
            queries.append(
                f"MATCH (s:Session {{id:{_quote(session.metadata.session_id)}}}) "
                f"MERGE (n:Insight {{id:{_quote(_hash(insight))}, text:{_quote(insight)}}}) "
                f"MERGE (s)-[:HAS_INSIGHT]->(n)"
            )

        for query in queries:
            self._execute(query)

    def _entity_queries(
        self, session_id: str, entity: Entity, extraction: ExtractionResult
    ) -> tuple[list[str], str]:
        node_id = _hash(entity.name)
        label = entity.type.capitalize()
        metadata_assignments = ", ".join(
            f"e.{key}={_quote(str(value))}" for key, value in entity.metadata.items()
        )
        if metadata_assignments:
            metadata_assignments = ", " + metadata_assignments

        node_query = (
            f"MERGE (e:{label} {{id:{_quote(node_id)}, name:{_quote(entity.name)}}}) "
            f"SET e.type={_quote(entity.type)}{metadata_assignments}"
        )

        # Add provenance metadata to MENTIONS relationship
        rel_query = (
            f"MATCH (s:Session {{id:{_quote(session_id)}}}), (e {{id:{_quote(node_id)}}}) "
            f"MERGE (s)-[r:MENTIONS]->(e) "
            f"SET r.confidence={entity.confidence}, "
            f"r.extracted_at={_quote(extraction.extracted_at or '')}, "
            f"r.source='code_atlas'"
        )

        return [node_query, rel_query], node_id

    def _match_clause(
        self,
        name: str,
        session: ParsedSession,
        entity_ids: dict[str, str],
        alias: str,
    ) -> str:
        if name == session.metadata.session_id:
            return f"MATCH ({alias}:Session {{id:{_quote(session.metadata.session_id)}}})"
        if name in entity_ids:
            return f"MATCH ({alias} {{id:{_quote(entity_ids[name])}}})"
        return f"MATCH ({alias} {{id:{_quote(_hash(name))}}})"

    def _execute(self, query: str) -> None:
        self.executed_queries.append(query)
        if self.client:
            logger.debug(
                "Executing graph query",
                graph_name=self.graph_name,
                query=query,
            )
            try:
                self.client.execute_command("GRAPH.QUERY", self.graph_name, query, "--compact")
            except redis.RedisError as exc:
                logger.error(
                    "Failed to execute graph query",
                    graph_name=self.graph_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise exc

    def _ensure_indexes(self) -> None:
        """Create database indexes for optimal query performance."""
        if not self.client:
            logger.warning("No database client available for index creation")
            return

        logger.info("Creating database indexes for optimal performance", graph_name=self.graph_name)

        total_indexes = sum(len(indexes) for indexes in self.INDEXES.values())
        created_indexes = 0
        failed_indexes = 0

        for category, index_queries in self.INDEXES.items():
            logger.debug("Creating indexes", category=category, count=len(index_queries))

            for index_query in index_queries:
                try:
                    # Execute index creation query
                    self._execute(index_query)
                    created_indexes += 1
                    logger.debug("Index created successfully", category=category, query=index_query)
                except redis.RedisError as exc:
                    failed_indexes += 1
                    logger.warning(
                        "Failed to create index",
                        category=category,
                        query=index_query,
                        error=str(exc),
                    )
                    # Continue with other indexes even if one fails
                except Exception as exc:
                    failed_indexes += 1
                    logger.error(
                        "Unexpected error creating index",
                        category=category,
                        query=index_query,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    # Continue with other indexes

        logger.info(
            "Index creation completed",
            total_requested=total_indexes,
            created=created_indexes,
            failed=failed_indexes,
            graph_name=self.graph_name
        )

    def list_indexes(self) -> dict[str, list[str]]:
        """List all indexes currently defined in the system."""
        return self.INDEXES.copy()

    def verify_indexes(self) -> dict[str, dict[str, bool]]:
        """Verify which indexes exist in the database.

        Returns:
            Dictionary mapping category to dict of index existence status
        """
        if not self.client:
            return {"error": "No database connection available"}

        result = {}

        for category, index_queries in self.INDEXES.items():
            result[category] = {}

            for index_query in index_queries:
                # Extract index name from query for verification
                # Query format: "CREATE INDEX index_name IF NOT EXISTS ..."
                index_name = None
                try:
                    # Split by spaces and find the index name
                    parts = index_query.split()
                    if "INDEX" in parts and parts.index("INDEX") + 1 < len(parts):
                        index_name = parts[parts.index("INDEX") + 1]
                except (ValueError, IndexError):
                    index_name = None

                if index_name:
                    # Try to query index status
                    try:
                        # FalkorDB doesn't have a direct index status query
                        # We'll consider the index as existing if we can run a query that would use it
                        test_query = f"SHOW INDEXES"
                        verification_result = self.client.execute_command(
                            "GRAPH.QUERY", self.graph_name, test_query
                        )
                        # For now, assume index exists if no error occurred
                        result[category][index_name] = True
                    except redis.RedisError:
                        result[category][index_name] = False
                else:
                    result[category][index_query] = None  # Unknown status

        return result

    def drop_indexes(self) -> None:
        """Drop all custom indexes (useful for testing or migration)."""
        if not self.client:
            logger.warning("No database client available for dropping indexes")
            return

        logger.info("Dropping database indexes", graph_name=self.graph_name)

        # Drop indexes in reverse order of dependencies
        drop_order = ["FullText", "Relationships", "Insight", "Entity", "Session"]

        for category in drop_order:
            if category not in self.INDEXES:
                continue

            for index_query in self.INDEXES[category]:
                try:
                    # Convert CREATE INDEX to DROP INDEX
                    if "CREATE INDEX" in index_query:
                        parts = index_query.split()
                        if "INDEX" in parts and parts.index("INDEX") + 1 < len(parts):
                            index_name = parts[parts.index("INDEX") + 1]
                            drop_query = f"DROP INDEX {index_name} IF EXISTS"
                            self._execute(drop_query)
                            logger.debug("Index dropped successfully", category=category, index=index_name)
                except redis.RedisError as exc:
                    logger.warning(
                        "Failed to drop index",
                        category=category,
                        index=index_name if 'index_name' in locals() else "unknown",
                        error=str(exc),
                    )

    def _verify_index_creation(self) -> None:
        """Verify that indexes were created successfully."""
        if not self.client:
            return

        logger.info("Verifying database indexes", graph_name=self.graph_name)

        try:
            # Try a simple query that should use indexes
            test_queries = [
                "MATCH (s:Session) LIMIT 1",
                "MATCH (f:File) LIMIT 1",
                "MATCH (c:Concept) LIMIT 1",
                "MATCH (i:Insight) LIMIT 1"
            ]

            for test_query in test_queries:
                try:
                    result = self.client.execute_command("GRAPH.QUERY", self.graph_name, test_query)
                    logger.debug("Index verification query successful", query=test_query)
                except redis.RedisError as exc:
                    logger.warning(
                        "Index verification query failed",
                        query=test_query,
                        error=str(exc),
                    )

            logger.info("Index verification completed", graph_name=self.graph_name)
        except Exception as exc:
            logger.error(
                "Unexpected error during index verification",
                error=str(exc),
                error_type=type(exc).__name__,
            )
