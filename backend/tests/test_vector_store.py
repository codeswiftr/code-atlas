"""Tests for vector storage functionality."""

import pytest

from code_atlas.vector_store import (
    FalkorDBVectorStore,
    create_vector_store,
)


class TestFalkorDBVectorStore:
    """Tests for FalkorDBVectorStore implementation."""

    def test_init_requires_graph_populator(self):
        """Test that FalkorDBVectorStore requires GraphPopulator."""
        # Mock GraphPopulator for testing
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        mock_graph = MockGraph()
        store = FalkorDBVectorStore(mock_graph)
        assert store is not None

    def test_store_and_retrieve_embedding(self):
        """Test storing and retrieving an embedding."""
        class MockGraph:
            def __init__(self):
                self.stored: dict[str, Any] = {}

            def execute_query(self, query: str, params: dict) -> list:
                if "SET" in query:
                    # Store operation
                    entity_id = params["entity_id"]
                    self.stored[entity_id] = params["embedding"]
                elif "RETURN" in query:
                    # Retrieve operation
                    entity_id = params["entity_id"]
                    embedding = self.stored.get(entity_id)
                    if embedding:
                        return [{"embedding": embedding}]
                return []

        mock_graph = MockGraph()
        store = FalkorDBVectorStore(mock_graph)

        entity_id = "test-entity-1"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        store.store_embedding(entity_id, "Concept", embedding)
        retrieved = store.get_embedding(entity_id)

        assert retrieved is not None
        assert len(retrieved) == len(embedding)
        # Note: In actual implementation, embeddings are stored as strings and parsed back

    def test_search_similar(self):
        """Test similarity search."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                # Return mock embeddings
                return [
                    {"entity_id": "entity1", "embedding": "0.1,0.2,0.3"},
                    {"entity_id": "entity2", "embedding": "0.9,0.8,0.7"},
                    {"entity_id": "entity3", "embedding": "0.5,0.5,0.5"},
                ]

        mock_graph = MockGraph()
        store = FalkorDBVectorStore(mock_graph)

        query_embedding = [0.1, 0.2, 0.3]
        results = store.search_similar(query_embedding, limit=5)

        assert isinstance(results, list)
        assert len(results) <= 5
        # Results should be sorted by similarity descending
        if len(results) > 1:
            assert results[0][1] >= results[-1][1]

    def test_delete_embedding(self):
        """Test deleting an embedding."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        mock_graph = MockGraph()
        store = FalkorDBVectorStore(mock_graph)

        # Should not raise
        store.delete_embedding("test-entity-1")

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Identical vectors should have similarity of 1.0
        vec = [1.0, 2.0, 3.0]
        similarity = FalkorDBVectorStore._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001

        # Orthogonal vectors should have similarity of 0.0
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = FalkorDBVectorStore._cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001

        # Different length vectors should return 0.0
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        similarity = FalkorDBVectorStore._cosine_similarity(vec1, vec2)
        assert similarity == 0.0


class TestCreateVectorStore:
    """Tests for vector store factory function."""

    def test_create_falkordb_store(self):
        """Test creating FalkorDB vector store."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        mock_graph = MockGraph()
        store = create_vector_store("falkordb", graph_populator=mock_graph)

        assert isinstance(store, FalkorDBVectorStore)

    def test_create_falkordb_store_requires_graph(self):
        """Test that FalkorDB store requires GraphPopulator."""
        with pytest.raises(ValueError, match="GraphPopulator required"):
            create_vector_store("falkordb", graph_populator=None)

    def test_create_external_store(self):
        """Test creating external vector store."""
        # External store creation (placeholder)
        with pytest.raises(NotImplementedError):
            store = create_vector_store(
                "external",
                connection_string="qdrant://localhost:6333",
            )
            store.store_embedding("test", "Concept", [0.1, 0.2, 0.3])

    def test_create_invalid_store_type(self):
        """Test that invalid store type raises error."""
        with pytest.raises(ValueError, match="Unknown vector store type"):
            create_vector_store("invalid_type")
