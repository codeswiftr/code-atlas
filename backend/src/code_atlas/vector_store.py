"""Vector storage abstraction for entity embeddings.

Provides an interface for storing and retrieving entity embeddings, with support
for multiple backends (FalkorDB vector extension, external vector DBs, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .logging_config import get_logger

logger = get_logger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector storage backends."""

    @abstractmethod
    def store_embedding(
        self,
        entity_id: str,
        entity_type: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store an embedding for an entity.

        Args:
            entity_id: Unique identifier for the entity.
            entity_type: Type of entity (Concept, File, Tool, etc.).
            embedding: Embedding vector to store.
            metadata: Optional metadata to store with the embedding.
        """
        pass

    @abstractmethod
    def get_embedding(self, entity_id: str) -> list[float] | None:
        """Retrieve embedding for an entity.

        Args:
            entity_id: Unique identifier for the entity.

        Returns:
            Embedding vector if found, None otherwise.
        """
        pass

    @abstractmethod
    def search_similar(
        self,
        query_embedding: list[float],
        entity_type: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[tuple[str, float]]:
        """Search for entities with similar embeddings.

        Args:
            query_embedding: Query embedding vector.
            entity_type: Optional filter by entity type.
            limit: Maximum number of results to return.
            min_similarity: Minimum similarity threshold (0.0 to 1.0).

        Returns:
            List of (entity_id, similarity_score) tuples, sorted by similarity descending.
        """
        pass

    @abstractmethod
    def delete_embedding(self, entity_id: str) -> None:
        """Delete embedding for an entity.

        Args:
            entity_id: Unique identifier for the entity.
        """
        pass

    @abstractmethod
    def batch_store_embeddings(
        self,
        embeddings: list[tuple[str, str, list[float], dict[str, Any] | None]],
    ) -> None:
        """Store multiple embeddings efficiently.

        Args:
            embeddings: List of (entity_id, entity_type, embedding, metadata) tuples.
        """
        pass


class FalkorDBVectorStore(VectorStore):
    """Vector storage using FalkorDB with vector extension support.

    Stores embeddings as node properties in FalkorDB graph.
    Note: This is a simplified implementation. Full implementation would
    use FalkorDB's vector search capabilities if available.
    """

    def __init__(self, graph_populator: Any) -> None:
        """Initialize FalkorDB vector store.

        Args:
            graph_populator: GraphPopulator instance for database access.
        """
        self.graph = graph_populator
        logger.info("FalkorDB vector store initialized")

    def store_embedding(
        self,
        entity_id: str,
        entity_type: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store embedding as node property in FalkorDB."""
        # Convert embedding to JSON-serializable format
        embedding_str = ",".join(str(x) for x in embedding)

        # Update node with embedding property
        # Note: In production, this would use FalkorDB vector extension if available
        query = f"""
            MATCH (e:{entity_type} {{id: $entity_id}})
            SET e.embedding = $embedding
            {', e.embedding_metadata = $metadata' if metadata else ''}
        """
        params: dict[str, Any] = {
            "entity_id": entity_id,
            "embedding": embedding_str,
        }
        if metadata:
            params["metadata"] = metadata

        try:
            self.graph.execute_query(query, params)
            logger.debug("Stored embedding", entity_id=entity_id, entity_type=entity_type)
        except Exception as exc:
            logger.error("Failed to store embedding", entity_id=entity_id, error=str(exc))
            raise

    def get_embedding(self, entity_id: str) -> list[float] | None:
        """Retrieve embedding from FalkorDB node property."""
        query = """
            MATCH (e {id: $entity_id})
            WHERE e.embedding IS NOT NULL
            RETURN e.embedding as embedding
            LIMIT 1
        """
        try:
            result = self.graph.execute_query(query, {"entity_id": entity_id})
            if not result:
                return None

            embedding_str = result[0].get("embedding", "")
            if not embedding_str:
                return None

            # Parse comma-separated embedding string
            embedding = [float(x) for x in embedding_str.split(",")]
            return embedding
        except Exception as exc:
            logger.error("Failed to retrieve embedding", entity_id=entity_id, error=str(exc))
            return None

    def search_similar(
        self,
        query_embedding: list[float],
        entity_type: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[tuple[str, float]]:
        """Search for similar embeddings.

        Note: This is a simplified implementation that retrieves all embeddings
        and calculates similarity in-memory. Production implementation would use
        FalkorDB vector extension or external vector DB for efficient search.
        """
        # Build query to get all embeddings of specified type
        if entity_type:
            query = f"""
                MATCH (e:{entity_type})
                WHERE e.embedding IS NOT NULL
                RETURN e.id as entity_id, e.embedding as embedding
            """
        else:
            query = """
                MATCH (e)
                WHERE e.embedding IS NOT NULL
                RETURN e.id as entity_id, e.embedding as embedding
            """

        try:
            results = self.graph.execute_query(query, {})

            # Calculate similarities
            similarities: list[tuple[str, float]] = []
            for row in results:
                entity_id = row.get("entity_id", "")
                embedding_str = row.get("embedding", "")

                if not entity_id or not embedding_str:
                    continue

                try:
                    # Parse embedding
                    stored_embedding = [float(x) for x in embedding_str.split(",")]

                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)

                    if similarity >= min_similarity:
                        similarities.append((entity_id, similarity))
                except (ValueError, TypeError) as exc:
                    logger.warning(
                        "Invalid embedding format",
                        entity_id=entity_id,
                        error=str(exc),
                    )
                    continue

            # Sort by similarity descending and limit
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:limit]

        except Exception as exc:
            logger.error("Vector search failed", error=str(exc))
            return []

    def delete_embedding(self, entity_id: str) -> None:
        """Delete embedding from FalkorDB node."""
        query = """
            MATCH (e {id: $entity_id})
            REMOVE e.embedding, e.embedding_metadata
        """
        try:
            self.graph.execute_query(query, {"entity_id": entity_id})
            logger.debug("Deleted embedding", entity_id=entity_id)
        except Exception as exc:
            logger.error("Failed to delete embedding", entity_id=entity_id, error=str(exc))
            raise

    def batch_store_embeddings(
        self,
        embeddings: list[tuple[str, str, list[float], dict[str, Any] | None]],
    ) -> None:
        """Store multiple embeddings in batch."""
        for entity_id, entity_type, embedding, metadata in embeddings:
            self.store_embedding(entity_id, entity_type, embedding, metadata)

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class ExternalVectorStore(VectorStore):
    """Vector storage using external vector database (Qdrant, Weaviate, etc.).

    This is a placeholder for future implementation with external vector DBs.
    """

    def __init__(self, connection_string: str, collection_name: str = "code_atlas_entities") -> None:
        """Initialize external vector store.

        Args:
            connection_string: Connection string for vector DB.
            collection_name: Name of the collection/index to use.
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        logger.info(
            "External vector store initialized",
            connection=connection_string,
            collection=collection_name,
        )
        # TODO: Initialize connection to external vector DB

    def store_embedding(
        self,
        entity_id: str,
        entity_type: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store embedding in external vector DB."""
        # TODO: Implement external vector DB storage
        raise NotImplementedError("External vector store not yet implemented")

    def get_embedding(self, entity_id: str) -> list[float] | None:
        """Retrieve embedding from external vector DB."""
        # TODO: Implement external vector DB retrieval
        raise NotImplementedError("External vector store not yet implemented")

    def search_similar(
        self,
        query_embedding: list[float],
        entity_type: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[tuple[str, float]]:
        """Search similar embeddings in external vector DB."""
        # TODO: Implement external vector DB search
        raise NotImplementedError("External vector store not yet implemented")

    def delete_embedding(self, entity_id: str) -> None:
        """Delete embedding from external vector DB."""
        # TODO: Implement external vector DB deletion
        raise NotImplementedError("External vector store not yet implemented")

    def batch_store_embeddings(
        self,
        embeddings: list[tuple[str, str, list[float], dict[str, Any] | None]],
    ) -> None:
        """Batch store embeddings in external vector DB."""
        # TODO: Implement batch storage
        raise NotImplementedError("External vector store not yet implemented")


def create_vector_store(
    store_type: str = "falkordb",
    graph_populator: Any | None = None,
    connection_string: str | None = None,
) -> VectorStore:
    """Factory function to create vector store instance.

    Args:
        store_type: Type of vector store ('falkordb' or 'external').
        graph_populator: GraphPopulator instance (required for 'falkordb').
        connection_string: Connection string (required for 'external').

    Returns:
        VectorStore instance.
    """
    if store_type == "falkordb":
        if graph_populator is None:
            raise ValueError("GraphPopulator required for FalkorDB vector store")
        return FalkorDBVectorStore(graph_populator)
    elif store_type == "external":
        if connection_string is None:
            raise ValueError("Connection string required for external vector store")
        return ExternalVectorStore(connection_string)
    else:
        raise ValueError(f"Unknown vector store type: {store_type}")
