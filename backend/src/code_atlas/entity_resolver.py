"""Entity deduplication with similarity detection and merge logic."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .logging_config import get_logger

if TYPE_CHECKING:
    from .graph_populator import GraphPopulator

logger = get_logger(__name__)


@dataclass
class MergeRecord:
    """Record of an entity merge operation."""

    merged_id: str
    canonical_id: str
    merged_at: str
    similarity_score: float
    merged_name: str
    canonical_name: str


@dataclass
class EntityResolver:
    """Detects and resolves duplicate entities across sessions.

    Uses fuzzy string matching to find similar entity names and
    merges duplicates while preserving relationships.
    """

    graph: GraphPopulator
    similarity_threshold: float = 0.85
    merge_history: list[MergeRecord] = field(default_factory=list)

    def find_similar(
        self,
        entity_type: str,
        name: str,
        limit: int = 5,
    ) -> list[tuple[str, str, float]]:
        """Find entities with similar names.

        Args:
            entity_type: Type of entity (File, Concept, Tool, etc.)
            name: Name to search for
            limit: Maximum results to return

        Returns:
            List of (entity_id, entity_name, similarity_score) tuples
            sorted by similarity descending
        """
        # Query existing entities of this type
        query = f"MATCH (e:{entity_type}) RETURN e.id as id, e.name as name LIMIT 1000"

        try:
            results = self.graph.execute_query(query, {})
        except Exception as exc:
            logger.warning(
                "Failed to query entities for similarity",
                entity_type=entity_type,
                error=str(exc),
            )
            return []

        # Calculate similarity scores
        similar: list[tuple[str, str, float]] = []
        name_lower = name.lower()

        for row in results:
            entity_id = row.get("id", "")
            entity_name = row.get("name", "")

            if not entity_id or not entity_name:
                continue

            # Skip exact match (same entity)
            if entity_name.lower() == name_lower:
                continue

            score = self._calculate_similarity(name, entity_name)

            if score >= self.similarity_threshold:
                similar.append((entity_id, entity_name, score))

        # Sort by score descending and limit
        similar.sort(key=lambda x: x[2], reverse=True)
        return similar[:limit]

    def resolve(
        self,
        entity_type: str,
        name: str,
    ) -> tuple[str, bool]:
        """Resolve an entity name to canonical ID.

        If a similar entity exists above threshold, returns its ID.
        Otherwise, generates a new ID for the entity.

        Args:
            entity_type: Type of entity
            name: Entity name to resolve

        Returns:
            Tuple of (entity_id, is_existing) where is_existing
            indicates if we matched an existing entity
        """
        similar = self.find_similar(entity_type, name, limit=1)

        if similar:
            existing_id, existing_name, score = similar[0]
            logger.info(
                "Resolved entity to existing",
                entity_type=entity_type,
                new_name=name,
                existing_name=existing_name,
                similarity=round(score, 3),
            )
            return existing_id, True

        # Generate new ID
        new_id = self._generate_id(name)
        return new_id, False

    def merge_entities(
        self,
        source_id: str,
        target_id: str,
        source_name: str,
        target_name: str,
        similarity_score: float,
    ) -> bool:
        """Merge source entity into target, transferring relationships.

        Args:
            source_id: ID of entity to merge (will be deleted)
            target_id: ID of canonical entity (will receive relationships)
            source_name: Name of source entity
            target_name: Name of target entity
            similarity_score: Similarity score that triggered merge

        Returns:
            True if merge successful, False otherwise
        """
        try:
            # Transfer incoming relationships
            transfer_in_query = """
                MATCH (n)-[r]->(source {id: $source_id})
                MATCH (target {id: $target_id})
                WHERE n <> target
                CREATE (n)-[r2:RELATED_TO]->(target)
                SET r2 = properties(r)
                DELETE r
            """
            self.graph.execute_query(
                transfer_in_query,
                {"source_id": source_id, "target_id": target_id},
            )

            # Transfer outgoing relationships
            transfer_out_query = """
                MATCH (source {id: $source_id})-[r]->(n)
                MATCH (target {id: $target_id})
                WHERE n <> target
                CREATE (target)-[r2:RELATED_TO]->(n)
                SET r2 = properties(r)
                DELETE r
            """
            self.graph.execute_query(
                transfer_out_query,
                {"source_id": source_id, "target_id": target_id},
            )

            # Update target with merge metadata
            update_query = """
                MATCH (target {id: $target_id})
                SET target.merged_count = COALESCE(target.merged_count, 0) + 1,
                    target.last_merged_at = $merged_at,
                    target.merged_names = COALESCE(target.merged_names, []) + [$source_name]
            """
            self.graph.execute_query(
                update_query,
                {
                    "target_id": target_id,
                    "merged_at": datetime.now(timezone.utc).isoformat(),
                    "source_name": source_name,
                },
            )

            # Delete source entity
            delete_query = "MATCH (source {id: $source_id}) DETACH DELETE source"
            self.graph.execute_query(delete_query, {"source_id": source_id})

            # Record merge history
            record = MergeRecord(
                merged_id=source_id,
                canonical_id=target_id,
                merged_at=datetime.now(timezone.utc).isoformat(),
                similarity_score=similarity_score,
                merged_name=source_name,
                canonical_name=target_name,
            )
            self.merge_history.append(record)

            logger.info(
                "Merged entities",
                source_id=source_id,
                target_id=target_id,
                source_name=source_name,
                target_name=target_name,
                similarity=round(similarity_score, 3),
            )
            return True

        except Exception as exc:
            logger.error(
                "Failed to merge entities",
                source_id=source_id,
                target_id=target_id,
                error=str(exc),
            )
            return False

    def deduplicate_batch(
        self,
        entity_type: str,
        names: list[str],
    ) -> dict[str, str]:
        """Deduplicate a batch of entity names.

        Args:
            entity_type: Type of entities
            names: List of entity names to deduplicate

        Returns:
            Dict mapping original names to canonical IDs
        """
        resolved: dict[str, str] = {}
        seen_ids: dict[str, str] = {}  # id -> canonical_name

        for name in names:
            # First check if we've already resolved this exact name
            if name in resolved:
                continue

            # Try to resolve against existing entities
            entity_id, is_existing = self.resolve(entity_type, name)

            if is_existing:
                resolved[name] = entity_id
            else:
                # Check against names we've already processed in this batch
                best_match: tuple[str, float] | None = None

                for seen_name in resolved:
                    score = self._calculate_similarity(name, seen_name)
                    if score >= self.similarity_threshold:
                        if best_match is None or score > best_match[1]:
                            best_match = (seen_name, score)

                if best_match:
                    # Use the ID we already assigned to the similar name
                    resolved[name] = resolved[best_match[0]]
                    logger.debug(
                        "Batch dedupe match",
                        name=name,
                        matched_to=best_match[0],
                        similarity=round(best_match[1], 3),
                    )
                else:
                    # New unique entity
                    resolved[name] = entity_id
                    seen_ids[entity_id] = name

        return resolved

    def get_merge_history(self, entity_id: str | None = None) -> list[MergeRecord]:
        """Get merge history, optionally filtered by entity.

        Args:
            entity_id: Filter to merges involving this entity ID

        Returns:
            List of merge records
        """
        if entity_id is None:
            return list(self.merge_history)

        return [
            record
            for record in self.merge_history
            if record.merged_id == entity_id or record.canonical_id == entity_id
        ]

    def get_stats(self) -> dict:
        """Get deduplication statistics.

        Returns:
            Dict with merge counts and statistics
        """
        total_merges = len(self.merge_history)

        if total_merges == 0:
            return {
                "total_merges": 0,
                "avg_similarity": 0.0,
                "unique_canonical_ids": 0,
            }

        avg_similarity = sum(r.similarity_score for r in self.merge_history) / total_merges
        unique_canonical = len({r.canonical_id for r in self.merge_history})

        return {
            "total_merges": total_merges,
            "avg_similarity": round(avg_similarity, 3),
            "unique_canonical_ids": unique_canonical,
        }

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity score between two strings.

        Uses case-insensitive sequence matching.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        # Exact match
        if s1_lower == s2_lower:
            return 1.0

        # Contains match (one is substring of other)
        if s1_lower in s2_lower or s2_lower in s1_lower:
            shorter = min(len(s1_lower), len(s2_lower))
            longer = max(len(s1_lower), len(s2_lower))
            return 0.8 + (0.2 * shorter / longer)

        # Fuzzy match
        return SequenceMatcher(None, s1_lower, s2_lower).ratio()

    def _generate_id(self, name: str) -> str:
        """Generate deterministic ID from entity name.

        Args:
            name: Entity name

        Returns:
            SHA1 hash of the name
        """
        return hashlib.sha1(name.encode("utf-8")).hexdigest()
