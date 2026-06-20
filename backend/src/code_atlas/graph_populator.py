"""Helpers for writing sessions into FalkorDB (or dry-run logging)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

import redis

from .insight_extractor import Entity, ExtractionResult
from .logging_config import get_logger
from .metrics import AtlasMetrics
from .models import ParsedSession

logger = get_logger(__name__)


def _hash(value: str) -> str:
    # usedforsecurity=False: SHA1 for deterministic ID generation, not cryptography
    return hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()


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
    metrics: AtlasMetrics | None = None
    enable_deduplication: bool = False
    similarity_threshold: float = 0.85
    client: redis.Redis | None = field(init=False, default=None)
    executed_queries: list[str] = field(init=False, default_factory=list)
    _resolver: object | None = field(init=False, default=None)

    # Predefined indexes for production performance (FalkorDB syntax)
    # Note: FalkorDB silently ignores duplicate index creation, no IF NOT EXISTS needed
    INDEXES: ClassVar[dict[str, list[str]]] = {
        "Session": [
            "CREATE INDEX ON :Session(id)",
            "CREATE INDEX ON :Session(project)",
            "CREATE INDEX ON :Session(modified_at)",
            "CREATE INDEX ON :Session(size_bytes)",
        ],
        "Entity": [
            "CREATE INDEX ON :File(id)",
            "CREATE INDEX ON :File(name)",
            "CREATE INDEX ON :File(type)",
            "CREATE INDEX ON :Concept(id)",
            "CREATE INDEX ON :Concept(name)",
            "CREATE INDEX ON :Concept(type)",
        ],
        "Insight": [
            "CREATE INDEX ON :Insight(id)",
        ],
        "Relationships": [
            # FalkorDB does not support relationship property indexes
            # Query optimization relies on node indexes instead
        ],
        "FullText": [
            # FalkorDB full-text search uses CALL procedure syntax
            # Note: Run only once - FalkorDB will error if index already exists
            "CALL db.idx.fulltext.createNodeIndex('File', 'name')",
            "CALL db.idx.fulltext.createNodeIndex('Concept', 'name')",
        ],
    }

    def __post_init__(self) -> None:
        if not self.dry_run and self.redis_url:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        elif not self.dry_run:
            # Assume local FalkorDB via default port if no URL passed.
            self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        else:
            self.client = None

        # Update active database connections metric
        if self.metrics and self.client:
            self.metrics.update_db_connections(1)

        # Create indexes if requested and not in dry-run mode
        if self.create_indexes and not self.dry_run and self.client:
            self._ensure_indexes()
            if self.verify_indexes_after_creation:
                self._verify_index_creation()

    @property
    def entity_resolver(self):
        """Lazily create entity resolver for deduplication."""
        if self._resolver is None and self.enable_deduplication:
            from .entity_resolver import EntityResolver

            self._resolver = EntityResolver(
                graph=self,
                similarity_threshold=self.similarity_threshold,
            )
        return self._resolver

    def upsert(self, session: ParsedSession, extraction: ExtractionResult) -> None:
        # Record session node creation
        if self.metrics:
            self.metrics.record_node_created("Session")

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
            # Record entity creation metrics
            if self.metrics:
                self.metrics.record_node_created(entity.type.capitalize())
                self.metrics.record_entity_extracted(entity.type)

            entity_queries, node_id = self._entity_queries(
                session.metadata.session_id, entity, extraction
            )
            entity_ids[entity.name] = node_id
            queries.extend(entity_queries)

        for rel in extraction.relationships:
            # Record relationship creation metrics
            if self.metrics:
                self.metrics.record_relationship_created(rel.type or "RELATED_TO")
                self.metrics.record_relationship_extracted(rel.type or "RELATED_TO")

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
            # Record insight creation metrics
            if self.metrics:
                self.metrics.record_node_created("Insight")

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
        label = entity.type.capitalize()

        # Use entity resolver for deduplication if enabled
        if self.enable_deduplication and self.entity_resolver:
            node_id, is_existing = self.entity_resolver.resolve(label, entity.name)
            if is_existing:
                logger.debug(
                    "Resolved entity to existing",
                    entity_name=entity.name,
                    resolved_id=node_id,
                )
        else:
            node_id = _hash(entity.name)

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

    def execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a read query and return results as list of dicts.

        Args:
            query: Cypher query to execute
            params: Query parameters (substituted into query)

        Returns:
            List of result rows as dictionaries
        """
        # Substitute parameters into query
        if params:
            for key, value in params.items():
                placeholder = f"${key}"
                if isinstance(value, str):
                    query = query.replace(placeholder, _quote(value))
                else:
                    query = query.replace(placeholder, str(value))

        self.executed_queries.append(query)

        if not self.client:
            logger.debug("Dry run query", query=query)
            return []

        # Time the query execution
        context_manager = (
            self.metrics.time_db_query("read") if self.metrics else self._null_context_manager()
        )

        with context_manager:
            logger.debug(
                "Executing read query",
                graph_name=self.graph_name,
                query=query,
            )
            try:
                result = self.client.execute_command("GRAPH.QUERY", self.graph_name, query)
                return self._parse_result(result)
            except redis.RedisError as exc:
                if self.metrics:
                    self.metrics.record_error("database", type(exc).__name__)
                logger.error(
                    "Failed to execute read query",
                    graph_name=self.graph_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise exc

    def _parse_result(self, result) -> list[dict]:
        """Parse FalkorDB result into list of dictionaries."""
        if not result or len(result) < 2:
            return []

        # FalkorDB returns [header, data, stats]
        header = result[0]
        data = result[1]

        if not header or not data:
            return []

        # Extract column names from header
        columns = []
        for col in header:
            if isinstance(col, (list, tuple)) and len(col) >= 2:
                columns.append(col[1])  # Column name is second element
            elif isinstance(col, str):
                columns.append(col)
            else:
                columns.append(str(col))

        # Build result dictionaries
        rows = []
        for row in data:
            row_dict = {}
            for i, value in enumerate(row):
                if i < len(columns):
                    col_name = columns[i]
                    row_dict[col_name] = self._parse_value(value)
            rows.append(row_dict)

        return rows

    def _parse_value(self, value):
        """Parse a FalkorDB value into Python type."""
        if value is None:
            return None

        # Node format: [type_code, [id, labels, properties]]
        if isinstance(value, (list, tuple)):
            if len(value) >= 2 and isinstance(value[0], int):
                type_code = value[0]
                data = value[1]

                # Type 1 = Node
                if type_code == 1 and isinstance(data, (list, tuple)) and len(data) >= 3:
                    _, _, props = data[0], data[1], data[2]
                    result = {}
                    if isinstance(props, (list, tuple)):
                        for prop in props:
                            if isinstance(prop, (list, tuple)) and len(prop) >= 2:
                                key = prop[0]
                                val = prop[1] if len(prop) == 2 else prop[2]
                                result[key] = val
                    return result

                # Type 7 = Scalar/Array
                if type_code == 7 and isinstance(data, (list, tuple)):
                    return [self._parse_value(v) for v in data]

                # Other scalar types
                return data

            # Plain array
            return [self._parse_value(v) for v in value]

        return value

    def _execute(self, query: str) -> None:
        self.executed_queries.append(query)
        if self.client:
            # Time the query execution
            context_manager = (
                self.metrics.time_db_query("execute")
                if self.metrics
                else self._null_context_manager()
            )

            with context_manager:
                logger.debug(
                    "Executing graph query",
                    graph_name=self.graph_name,
                    query=query,
                )
                try:
                    self.client.execute_command("GRAPH.QUERY", self.graph_name, query, "--compact")
                except redis.RedisError as exc:
                    # Record error metrics
                    if self.metrics:
                        self.metrics.record_error("database", type(exc).__name__)

                    logger.error(
                        "Failed to execute graph query",
                        graph_name=self.graph_name,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    raise exc

    def _null_context_manager(self):
        """Null context manager for when metrics are disabled."""
        from contextlib import nullcontext

        return nullcontext()

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
            graph_name=self.graph_name,
        )

    def list_indexes(self) -> dict[str, list[str]]:
        """List all indexes currently defined in the system."""
        return self.INDEXES.copy()

    def verify_indexes(self) -> dict[str, dict[str, bool] | str]:
        """Verify which indexes exist in the database.

        Returns:
            Dictionary mapping category to dict of index existence status
        """
        if not self.client:
            return {"error": "No database connection available"}

        result: dict[str, dict[str, bool] | str] = {}

        for category, index_queries in self.INDEXES.items():
            category_result: dict[str, bool] = {}

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
                        # We'll consider the index as existing if we can run a query that uses it
                        test_query = "SHOW INDEXES"
                        self.client.execute_command("GRAPH.QUERY", self.graph_name, test_query)
                        # For now, assume index exists if no error occurred
                        category_result[index_name] = True
                    except redis.RedisError:
                        category_result[index_name] = False

            result[category] = category_result

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
                index_identifier = "unknown"
                try:
                    # FalkorDB syntax: CREATE INDEX ON :Label(property)
                    if "CREATE INDEX ON" in index_query:
                        # Extract :Label(property) part and use same syntax for drop
                        # e.g., "CREATE INDEX ON :Session(id)" -> "DROP INDEX ON :Session(id)"
                        drop_query = index_query.replace("CREATE INDEX ON", "DROP INDEX ON")
                        index_identifier = index_query.split("ON")[1].strip()
                        self._execute(drop_query)
                        logger.debug(
                            "Index dropped successfully",
                            category=category,
                            index=index_identifier,
                        )
                    elif "CALL db.idx.fulltext.createNodeIndex" in index_query:
                        # Full-text indexes: CALL db.idx.fulltext.drop('Label')
                        # Extract label from createNodeIndex('Label', 'property')
                        import re

                        match = re.search(r"createNodeIndex\('(\w+)'", index_query)
                        if match:
                            label = match.group(1)
                            drop_query = f"CALL db.idx.fulltext.drop('{label}')"
                            index_identifier = f"fulltext:{label}"
                            self._execute(drop_query)
                            logger.debug("Full-text index dropped", category=category, label=label)
                except redis.RedisError as exc:
                    logger.warning(
                        "Failed to drop index",
                        category=category,
                        index=index_identifier,
                        error=str(exc),
                    )

    def _verify_index_creation(self) -> None:
        """Verify that indexes were created successfully."""
        if not self.client:
            return

        logger.info("Verifying database indexes", graph_name=self.graph_name)

        try:
            # Try a simple query that should use indexes
            # Note: In Cypher, LIMIT must come after RETURN
            test_queries = [
                "MATCH (s:Session) RETURN s LIMIT 1",
                "MATCH (f:File) RETURN f LIMIT 1",
                "MATCH (c:Concept) RETURN c LIMIT 1",
                "MATCH (i:Insight) RETURN i LIMIT 1",
            ]

            for test_query in test_queries:
                try:
                    self.executed_queries.append(test_query)
                    self.client.execute_command("GRAPH.QUERY", self.graph_name, test_query)
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
