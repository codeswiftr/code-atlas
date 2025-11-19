"""Helpers for writing sessions into FalkorDB (or dry-run logging)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

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
    client: redis.Redis | None = field(init=False, default=None)
    executed_queries: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if not self.dry_run and self.redis_url:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        elif not self.dry_run:
            # Assume local FalkorDB via default port if no URL passed.
            self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        else:
            self.client = None

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
