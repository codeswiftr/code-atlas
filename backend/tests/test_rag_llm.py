"""Tests for RAG LLM integration."""

from unittest.mock import MagicMock, patch

import pytest

from code_atlas.rag_service import (
    RAGService,
    DEFAULT_RAG_MODEL,
    DEFAULT_MAX_TOKENS,
    HAIKU_INPUT_COST,
    HAIKU_OUTPUT_COST,
)


class MockHybridSearch:
    """Mock hybrid search for testing."""

    def __init__(self, results=None):
        self.results = results or []

    def search(self, query, entity_type=None, limit=5, min_score=0.3):
        return self.results


class MockSearchResult:
    """Mock search result."""

    def __init__(self, entity_id, entity_type, combined_score=0.8):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.combined_score = combined_score


class MockGraphPopulator:
    """Mock graph populator for testing."""

    def execute_query(self, query, params):
        # Return mock entity data
        if "entity_id" in params:
            return [
                {
                    "e": {"id": params["entity_id"], "name": "TestEntity", "description": "A test entity"},
                    "labels": ["Concept"],
                    "relationships": [],
                }
            ]
        return []


class MockAnthropicResponse:
    """Mock Anthropic API response."""

    def __init__(self, text="This is a test answer.", input_tokens=100, output_tokens=50):
        self.content = [MagicMock(text=text)]
        self.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)


class TestRAGWithLLM:
    """Tests for RAG with LLM client."""

    def test_rag_with_llm_client_generates_answer(self):
        """LLM client called and returns answer."""
        # Setup
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockAnthropicResponse(
            text="Based on the context, the answer is XYZ."
        )

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        # Execute
        result = rag_service.answer_question("What is XYZ?")

        # Verify
        assert mock_client.messages.create.called
        assert result["answer"] == "Based on the context, the answer is XYZ."
        assert result["confidence"] > 0

    def test_rag_without_llm_falls_back_to_context(self):
        """Without LLM client, returns context-based answer."""
        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=None,  # No LLM client
        )

        result = rag_service.answer_question("What is XYZ?")

        # Should return fallback answer mentioning entities
        assert "relevant entities" in result["answer"].lower() or "TestEntity" in result["answer"]
        assert result["confidence"] == 0.6  # Lower confidence without LLM

    def test_rag_llm_prompt_includes_context(self):
        """Prompt sent to LLM includes retrieved context."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockAnthropicResponse()

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        rag_service.answer_question("What is TestEntity?")

        # Verify prompt contains context
        call_args = mock_client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        user_content = messages[0]["content"]

        assert "TestEntity" in user_content
        assert "What is TestEntity?" in user_content

    def test_rag_uses_haiku_model(self):
        """RAG uses cost-effective Haiku model."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockAnthropicResponse()

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        rag_service.answer_question("Test question?")

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == DEFAULT_RAG_MODEL
        assert call_args.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    def test_rag_handles_llm_api_error_gracefully(self):
        """API error returns fallback answer."""
        from anthropic import APIError

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = APIError(
            message="Rate limit exceeded",
            request=MagicMock(),
            body=None,
        )

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        result = rag_service.answer_question("What is XYZ?")

        # Should return fallback answer, not raise exception
        assert result["answer"] is not None
        assert "error" not in result["answer"].lower()

    def test_rag_handles_general_exception_gracefully(self):
        """General exception returns fallback answer."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection timeout")

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        result = rag_service.answer_question("What is XYZ?")

        # Should return fallback answer
        assert result["answer"] is not None


class TestRAGCostTracking:
    """Tests for RAG cost estimation."""

    def test_rag_cost_calculation(self):
        """Cost calculated correctly based on token usage."""
        hybrid_search = MockHybridSearch()
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=None,
        )

        # 1000 input tokens, 500 output tokens
        cost = rag_service._estimate_rag_cost(1000, 500)

        expected_input_cost = (1000 / 1_000_000) * HAIKU_INPUT_COST
        expected_output_cost = (500 / 1_000_000) * HAIKU_OUTPUT_COST
        expected_total = expected_input_cost + expected_output_cost

        assert cost == pytest.approx(expected_total)

    def test_rag_cost_logged_after_query(self):
        """Token usage and cost logged after successful LLM call."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockAnthropicResponse(
            input_tokens=150,
            output_tokens=75,
        )

        search_results = [MockSearchResult("entity1", "Concept")]
        hybrid_search = MockHybridSearch(results=search_results)
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=mock_client,
        )

        with patch("code_atlas.rag_service.logger") as mock_logger:
            rag_service.answer_question("Test question?")

            # Verify cost was logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("estimated_cost_usd" in call for call in log_calls)


class TestRAGNoResults:
    """Tests for RAG with no search results."""

    def test_rag_no_results_returns_helpful_message(self):
        """When no entities found, return helpful message."""
        hybrid_search = MockHybridSearch(results=[])  # No results
        graph = MockGraphPopulator()

        rag_service = RAGService(
            graph_populator=graph,
            hybrid_search=hybrid_search,
            llm_client=None,
        )

        result = rag_service.answer_question("What is something nonexistent?")

        assert "couldn't find" in result["answer"].lower()
        assert result["confidence"] == 0.0
        assert result["sources"] == []
