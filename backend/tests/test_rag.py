"""Tests for RAG service functionality."""

import pytest

from code_atlas.rag_service import RAGService, create_rag_service


class TestRAGService:
    """Tests for RAGService class."""

    def test_init(self):
        """Test RAGService initialization."""
        # Mock dependencies
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        class MockHybridSearch:
            def search(self, query, entity_type=None, limit=10, min_score=0.0, use_graph_structure=True, use_vector_search=True):
                return []

        mock_graph = MockGraph()
        mock_hybrid_search = MockHybridSearch()

        rag_service = RAGService(
            graph_populator=mock_graph,
            hybrid_search=mock_hybrid_search,
        )

        assert rag_service is not None
        assert rag_service.context_limit == 5

    def test_answer_question_no_results(self):
        """Test answering question when no results found."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        class MockHybridSearch:
            def search(self, query, entity_type=None, limit=10, min_score=0.0, use_graph_structure=True, use_vector_search=True):
                return []

        mock_graph = MockGraph()
        mock_hybrid_search = MockHybridSearch()

        rag_service = RAGService(
            graph_populator=mock_graph,
            hybrid_search=mock_hybrid_search,
        )

        result = rag_service.answer_question("What is authentication?")

        assert "couldn't find" in result["answer"].lower()
        assert result["confidence"] == 0.0
        assert len(result["sources"]) == 0

    def test_answer_question_with_results(self):
        """Test answering question with search results."""
        # This test requires full implementation with mocked search results
        pytest.skip("Requires full implementation with mocked dependencies")


class TestCreateRAGService:
    """Tests for RAG service factory function."""

    def test_create_rag_service(self):
        """Test creating RAG service."""
        class MockGraph:
            def execute_query(self, query: str, params: dict) -> list:
                return []

        class MockVectorStore:
            def search_similar(self, query_embedding, entity_type=None, limit=10, min_similarity=0.0):
                return []

        mock_graph = MockGraph()
        mock_vector_store = MockVectorStore()

        rag_service = create_rag_service(
            graph_populator=mock_graph,
            vector_store=mock_vector_store,
        )

        assert isinstance(rag_service, RAGService)
