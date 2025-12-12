"""Hybrid search combining Cypher graph queries with vector similarity search.

Provides functionality to search the knowledge graph using both structural
graph queries and semantic vector similarity, combining results with weighted ranking.
"""

from __future__ import annotations

from typing import Any

from .embeddings import EmbeddingGenerator, get_embedding_generator
from .logging_config import get_logger
from .vector_store import VectorStore

logger = get_logger(__name__)


class HybridSearchResult:
    """Result from hybrid search containing both graph and vector search results."""

    def __init__(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        graph_score: float = 0.0,
        vector_score: float = 0.0,
        combined_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize hybrid search result.

        Args:
            entity_id: Unique identifier for the entity.
            entity_name: Name of the entity.
            entity_type: Type of entity.
            graph_score: Score from graph structure analysis (0.0 to 1.0).
            vector_score: Score from vector similarity (0.0 to 1.0).
            combined_score: Weighted combination of graph and vector scores.
            metadata: Additional metadata about the entity.
        """
        self.entity_id = entity_id
        self.entity_name = entity_name
        self.entity_type = entity_type
        self.graph_score = graph_score
        self.vector_score = vector_score
        self.combined_score = combined_score
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "graph_score": self.graph_score,
            "vector_score": self.vector_score,
            "combined_score": self.combined_score,
            "metadata": self.metadata,
        }


class HybridSearch:
    """Hybrid search combining Cypher queries with vector similarity."""

    def __init__(
        self,
        graph_populator: Any,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator | None = None,
        graph_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> None:
        """Initialize hybrid search.

        Args:
            graph_populator: GraphPopulator instance for Cypher queries.
            vector_store: VectorStore instance for vector search.
            embedding_generator: EmbeddingGenerator instance (auto-created if None).
            graph_weight: Weight for graph structure scores (default 0.4).
            vector_weight: Weight for vector similarity scores (default 0.6).
        """
        self.graph = graph_populator
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator or get_embedding_generator()
        self.graph_weight = graph_weight
        self.vector_weight = vector_weight

        # Normalize weights
        total_weight = graph_weight + vector_weight
        if total_weight > 0:
            self.graph_weight = graph_weight / total_weight
            self.vector_weight = vector_weight / total_weight

        logger.info(
            "Hybrid search initialized",
            graph_weight=self.graph_weight,
            vector_weight=self.vector_weight,
        )

    def search(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 20,
        min_score: float = 0.0,
        use_graph_structure: bool = True,
        use_vector_search: bool = True,
    ) -> list[HybridSearchResult]:
        """Perform hybrid search combining graph and vector search.

        Args:
            query: Search query (natural language or keyword).
            entity_type: Optional filter by entity type.
            limit: Maximum number of results to return.
            min_score: Minimum combined score threshold.
            use_graph_structure: Whether to use graph structure scoring.
            use_vector_search: Whether to use vector similarity search.

        Returns:
            List of HybridSearchResult objects, sorted by combined_score descending.
        """
        logger.info(
            "Performing hybrid search",
            query=query[:100],
            entity_type=entity_type,
            limit=limit,
        )

        results_map: dict[str, HybridSearchResult] = {}

        # Step 1: Vector similarity search
        if use_vector_search:
            try:
                query_embedding = self.embedding_generator.generate_embedding(query)
                vector_results = self.vector_store.search_similar(
                    query_embedding=query_embedding,
                    entity_type=entity_type,
                    limit=limit * 2,  # Get more candidates for ranking
                    min_similarity=min_score,
                )

                for entity_id, similarity in vector_results:
                    if entity_id not in results_map:
                        # Get entity details from graph
                        entity_details = self._get_entity_details(entity_id)
                        if entity_details:
                            results_map[entity_id] = HybridSearchResult(
                                entity_id=entity_id,
                                entity_name=entity_details.get("name", entity_id),
                                entity_type=entity_details.get("type", "Concept"),
                                vector_score=similarity,
                                metadata=entity_details,
                            )
                        else:
                            results_map[entity_id] = HybridSearchResult(
                                entity_id=entity_id,
                                entity_name=entity_id,
                                entity_type=entity_type or "Concept",
                                vector_score=similarity,
                            )
                    else:
                        results_map[entity_id].vector_score = similarity

            except Exception as exc:
                logger.warning("Vector search failed, continuing with graph search", error=str(exc))

        # Step 2: Graph structure search (Cypher query)
        if use_graph_structure:
            try:
                graph_results = self._graph_search(query, entity_type, limit * 2)

                for entity_id, graph_score, entity_name, entity_type_result in graph_results:
                    if entity_id not in results_map:
                        entity_details = self._get_entity_details(entity_id)
                        results_map[entity_id] = HybridSearchResult(
                            entity_id=entity_id,
                            entity_name=entity_name or entity_id,
                            entity_type=entity_type_result or entity_type or "Concept",
                            graph_score=graph_score,
                            metadata=entity_details or {},
                        )
                    else:
                        results_map[entity_id].graph_score = graph_score
                        if entity_name:
                            results_map[entity_id].entity_name = entity_name

            except Exception as exc:
                logger.warning("Graph search failed", error=str(exc))

        # Step 3: Combine scores and rank
        for result in results_map.values():
            combined = (
                self.graph_weight * result.graph_score + self.vector_weight * result.vector_score
            )
            result.combined_score = combined

        # Step 4: Filter and sort
        filtered_results = [
            r for r in results_map.values() if r.combined_score >= min_score
        ]
        filtered_results.sort(key=lambda x: x.combined_score, reverse=True)

        return filtered_results[:limit]

    def _graph_search(
        self,
        query: str,
        entity_type: str | None,
        limit: int,
    ) -> list[tuple[str, float, str | None, str | None]]:
        """Perform graph-based search using Cypher.

        Returns list of (entity_id, score, name, type) tuples.
        """
        # Build Cypher query for text search in entity names
        if entity_type:
            cypher_query = f"""
                MATCH (e:{entity_type})
                WHERE toLower(e.name) CONTAINS toLower($query)
                   OR e.description CONTAINS $query
                RETURN e.id as entity_id, e.name as name, labels(e)[0] as type, e.mention_count as mentions
                ORDER BY e.mention_count DESC
                LIMIT $limit
            """
        else:
            cypher_query = """
                MATCH (e)
                WHERE toLower(e.name) CONTAINS toLower($query)
                   OR e.description CONTAINS $query
                RETURN e.id as entity_id, e.name as name, labels(e)[0] as type, e.mention_count as mentions
                ORDER BY e.mention_count DESC
                LIMIT $limit
            """

        try:
            results = self.graph.execute_query(cypher_query, {"query": query, "limit": limit})

            # Normalize mention_count to 0-1 score range
            # Use logarithmic scaling for better distribution
            max_mentions = max((r.get("mentions", 0) for r in results), default=1)
            graph_results: list[tuple[str, float, str | None, str | None]] = []

            for row in results:
                entity_id = row.get("entity_id", "")
                mentions = row.get("mentions", 0)
                name = row.get("name")
                entity_type_result = row.get("type")

                if not entity_id:
                    continue

                # Score based on mention count (normalized)
                score = min(1.0, mentions / max(max_mentions, 1))

                graph_results.append((entity_id, score, name, entity_type_result))

            return graph_results

        except Exception as exc:
            logger.error("Graph search query failed", error=str(exc))
            return []

    def _get_entity_details(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity details from graph database."""
        query = """
            MATCH (e {id: $entity_id})
            RETURN e, labels(e) as labels
            LIMIT 1
        """
        try:
            results = self.graph.execute_query(query, {"entity_id": entity_id})
            if not results:
                return None

            node = results[0].get("e", {})
            labels = results[0].get("labels", [])

            return {
                "id": entity_id,
                "name": node.get("name", node.get("title", entity_id)),
                "type": labels[0] if labels else "Concept",
                "properties": dict(node),
            }
        except Exception as exc:
            logger.warning("Failed to get entity details", entity_id=entity_id, error=str(exc))
            return None
