"""Helpers for writing sessions into FalkorDB (or dry-run logging)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict

import redis

from .insight_extractor import ExtractionResult, Entity, Relationship
from .models import ParsedSession

logger = logging.getLogger(__name__)


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
            "MERGE (s:Session {id:%s}) "
            "SET s.project=%s, s.size_bytes=%s, s.modified_at=%s, %s"
        ) % (
            _quote(session.metadata.session_id),
            _quote(session.metadata.project),
            session.metadata.size_bytes,
            session.metadata.modified_at.timestamp(),
            session_metadata_str,
        )
        queries.append(session_node)

        entity_ids: Dict[str, str] = {}
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
                "MATCH (s:Session {id:%s}) "
                "MERGE (n:Insight {id:%s, text:%s}) "
                "MERGE (s)-[:HAS_INSIGHT]->(n)"
                % (
                    _quote(session.metadata.session_id),
                    _quote(_hash(insight)),
                    _quote(insight),
                )
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
            "MERGE (e:{label} {{id:%s, name:%s}}) SET e.type=%s{metadata}"
        ).format(label=label, metadata=metadata_assignments) % (
            _quote(node_id),
            _quote(entity.name),
            _quote(entity.type),
        )

        # Add provenance metadata to MENTIONS relationship
        rel_query = (
            "MATCH (s:Session {id:%s}), (e {id:%s}) "
            "MERGE (s)-[r:MENTIONS]->(e) "
            "SET r.confidence=%s, r.extracted_at=%s, r.source='code_atlas'"
        ) % (
            _quote(session_id),
            _quote(node_id),
            entity.confidence,
            _quote(extraction.extracted_at or ""),
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
            logger.debug("GRAPH.QUERY %s %s", self.graph_name, query)
            try:
                self.client.execute_command("GRAPH.QUERY", self.graph_name, query, "--compact")
            except redis.RedisError as exc:
                logger.error("Failed to execute query: %s", exc)
                raise
