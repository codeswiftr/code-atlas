"""Tests for hybrid search functionality."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from code_atlas.hybrid_search import HybridSearch, HybridSearchResult


@pytest.fixture
def mock_graph():
    """Create a mock graph populator."""
    mock = MagicMock()
    mock.query = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    mock = MagicMock()
    mock.search_similar = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_embedding_generator():
    """Create a mock embedding generator."""
    mock = MagicMock()
    mock.generate_embedding = MagicMock(return_value=np.random.rand(384).tolist())
    return mock


class TestHybridSearch:
    """Tests for HybridSearch class."""

    def test_init(self, mock_graph, mock_vector_store):
        """Test HybridSearch initialization."""
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        assert search is not None
        assert search.graph is mock_graph
        assert search.vector_store is mock_vector_store
        assert search.graph_weight + search.vector_weight == pytest.approx(1.0)

    def test_init_with_custom_weights(self, mock_graph, mock_vector_store):
        """Test initialization with custom weights."""
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            graph_weight=0.7,
            vector_weight=0.3,
        )

        assert search.graph_weight == pytest.approx(0.7)
        assert search.vector_weight == pytest.approx(0.3)

    def test_weight_normalization(self, mock_graph, mock_vector_store):
        """Test that weights are normalized correctly."""
        # Weights don't sum to 1.0, should be normalized
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            graph_weight=0.3,
            vector_weight=0.9,  # Total = 1.2
        )

        # Should be normalized to sum to 1.0
        assert search.graph_weight + search.vector_weight == pytest.approx(1.0)
        assert search.graph_weight == pytest.approx(0.25)  # 0.3 / 1.2
        assert search.vector_weight == pytest.approx(0.75)  # 0.9 / 1.2

    def test_search_vector_only(self, mock_graph, mock_vector_store, mock_embedding_generator):
        """Test search with vector search only."""
        mock_vector_store.search_similar.return_value = [
            ("entity-1", 0.85),
            ("entity-2", 0.75),
        ]

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
        )

        with patch.object(search, "_get_entity_details") as mock_get_details:
            mock_get_details.return_value = {
                "name": "Test Entity",
                "type": "Concept",
            }

            results = search.search(
                query="test query",
                use_graph_structure=False,
                use_vector_search=True,
            )

            assert len(results) == 2
            assert results[0].entity_id == "entity-1"
            assert results[0].vector_score == 0.85
            mock_embedding_generator.generate_embedding.assert_called_once()

    def test_search_graph_only(self, mock_graph, mock_vector_store):
        """Test search with graph search only."""
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        with patch.object(search, "_graph_search") as mock_graph_search:
            with patch.object(search, "_get_entity_details") as mock_get_details:
                mock_graph_search.return_value = [
                    ("entity-1", 0.9, "Graph Entity", "Concept"),
                ]
                mock_get_details.return_value = {"name": "Graph Entity"}

                results = search.search(
                    query="test query",
                    use_graph_structure=True,
                    use_vector_search=False,
                )

                assert len(results) == 1
                assert results[0].entity_id == "entity-1"
                assert results[0].graph_score == 0.9

    def test_search_hybrid(self, mock_graph, mock_vector_store, mock_embedding_generator):
        """Test hybrid search combining graph and vector results."""
        mock_vector_store.search_similar.return_value = [
            ("entity-1", 0.85),
            ("entity-2", 0.75),
        ]

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            graph_weight=0.4,
            vector_weight=0.6,
        )

        with patch.object(search, "_graph_search") as mock_graph_search:
            with patch.object(search, "_get_entity_details") as mock_get_details:
                mock_graph_search.return_value = [
                    ("entity-1", 0.9, "Entity 1", "Concept"),
                    ("entity-3", 0.8, "Entity 3", "Tool"),
                ]
                mock_get_details.return_value = {"name": "Test", "type": "Concept"}

                results = search.search(query="test query")

                # Should have 3 unique entities
                assert len(results) == 3

                # Entity-1 appears in both, so should have highest combined score
                entity_1 = next((r for r in results if r.entity_id == "entity-1"), None)
                assert entity_1 is not None
                assert entity_1.graph_score == 0.9
                assert entity_1.vector_score == 0.85
                # Combined: 0.4 * 0.9 + 0.6 * 0.85 = 0.87
                assert entity_1.combined_score == pytest.approx(0.87)

    def test_search_filters_by_min_score(self, mock_graph, mock_vector_store, mock_embedding_generator):
        """Test that search filters by minimum score."""
        mock_vector_store.search_similar.return_value = [
            ("entity-1", 0.85),
            ("entity-2", 0.45),
        ]

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
        )

        with patch.object(search, "_get_entity_details") as mock_get_details:
            mock_get_details.return_value = {"name": "Test", "type": "Concept"}

            results = search.search(
                query="test query",
                use_graph_structure=False,
                min_score=0.5,
            )

            # Only entity-1 should pass the threshold
            assert len(results) == 1
            assert results[0].entity_id == "entity-1"

    def test_search_respects_limit(self, mock_graph, mock_vector_store, mock_embedding_generator):
        """Test that search respects result limit."""
        mock_vector_store.search_similar.return_value = [
            (f"entity-{i}", 0.9 - i * 0.1) for i in range(10)
        ]

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
        )

        with patch.object(search, "_get_entity_details") as mock_get_details:
            mock_get_details.return_value = {"name": "Test", "type": "Concept"}

            results = search.search(
                query="test query",
                use_graph_structure=False,
                limit=5,
            )

            assert len(results) <= 5

    def test_search_handles_vector_search_error(self, mock_graph, mock_vector_store):
        """Test that search handles vector search errors gracefully."""
        mock_vector_store.search_similar.side_effect = Exception("Vector search failed")

        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        with patch.object(search, "_graph_search") as mock_graph_search:
            mock_graph_search.return_value = []

            # Should not raise an exception
            results = search.search(query="test query")
            assert isinstance(results, list)

    def test_search_handles_graph_search_error(self, mock_graph, mock_vector_store):
        """Test that search handles graph search errors gracefully."""
        search = HybridSearch(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        with patch.object(search, "_graph_search") as mock_graph_search:
            mock_graph_search.side_effect = Exception("Graph query failed")

            # Should not raise an exception
            results = search.search(query="test query", use_vector_search=False)
            assert isinstance(results, list)


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
