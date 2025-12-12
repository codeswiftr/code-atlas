"""Tests for hybrid search functionality."""

import pytest

from code_atlas.hybrid_search import HybridSearch, HybridSearchResult


class TestHybridSearch:
    """Tests for HybridSearch class."""

    def test_init(self):
        """Test HybridSearch initialization."""
        # Mock dependencies
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        class MockVectorStore:
            def search_similar(self, query_embedding, entity_type=None, limit=10, min_similarity=0.0):
                return []

        mock_graph = MockGraph()
        mock_vector_store = MockVectorStore()

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        assert search is not None
        assert search.graph_weight + search.vector_weight == pytest.approx(1.0)

    def test_search_combines_results(self):
        """Test that search combines graph and vector results."""
        # This test would require full implementation
        # For now, we test the structure
        pytest.skip("Requires full implementation with mocked dependencies")

    def test_weight_normalization(self):
        """Test that weights are normalized correctly."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        class MockVectorStore:
            def search_similar(self, query_embedding, entity_type=None, limit=10, min_similarity=0.0):
                return []

        mock_graph = MockGraph()
        mock_vector_store = MockVectorStore()

        # Weights don't sum to 1.0, should be normalized
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            graph_weight=0.3,
            vector_weight=0.9,  # Total = 1.2
        )

        # Should be normalized
        assert search.graph_weight + search.vector_weight == pytest.approx(1.0)


class TestHybridSearchResult:
    """Tests for HybridSearchResult class."""

    def test_init(self):
        """Test HybridSearchResult initialization."""
        result = HybridSearchResult(
            entity_id="test-1",
            entity_name="Test Entity",
            entity_type="Concept",
            graph_score=0.8,
            vector_score=0.7,
            combined_score=0.75,
        )

        assert result.entity_id == "test-1"
        assert result.entity_name == "Test Entity"
        assert result.graph_score == 0.8
        assert result.vector_score == 0.7
        assert result.combined_score == 0.75

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = HybridSearchResult(
            entity_id="test-1",
            entity_name="Test Entity",
            entity_type="Concept",
            graph_score=0.8,
            vector_score=0.7,
            combined_score=0.75,
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["entity_id"] == "test-1"
        assert result_dict["combined_score"] == 0.75
