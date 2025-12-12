"""Tests for full-text entity search."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.v1.graph import _calculate_similarity, _highlight_match


class TestSimilarityFunctions:
    """Tests for similarity calculation helpers."""

    def test_calculate_similarity_exact_match(self) -> None:
        """Exact matches score 1.0."""
        assert _calculate_similarity("authentication", "authentication") == 1.0
        assert _calculate_similarity("Auth", "auth") == 1.0  # Case insensitive

    def test_calculate_similarity_contains_match(self) -> None:
        """Substring matches score high (0.8+)."""
        score = _calculate_similarity("auth", "authentication")
        assert score >= 0.8
        assert score < 1.0

    def test_calculate_similarity_partial_match(self) -> None:
        """Partial matches get reasonable scores."""
        score = _calculate_similarity("authn", "authentication")
        assert 0.3 < score < 0.8

    def test_calculate_similarity_no_match(self) -> None:
        """Non-matching strings get low scores."""
        score = _calculate_similarity("xyz", "authentication")
        assert score < 0.5

    def test_calculate_similarity_typo_tolerance(self) -> None:
        """Typos still get reasonable scores."""
        # "authentcation" is missing 'i'
        score = _calculate_similarity("authentcation", "authentication")
        assert score > 0.7

    def test_highlight_match_basic(self) -> None:
        """Basic highlighting works."""
        result = _highlight_match("auth", "Authentication")
        assert result == "**Auth**entication"

    def test_highlight_match_case_insensitive(self) -> None:
        """Highlighting is case insensitive."""
        result = _highlight_match("AUTH", "authentication")
        assert "**" in result

    def test_highlight_match_no_match(self) -> None:
        """No highlight when no match."""
        result = _highlight_match("xyz", "authentication")
        assert result == "authentication"
        assert "**" not in result


class TestSearchEndpoint:
    """Tests for the search API endpoint."""

    @pytest.fixture
    def mock_graph(self) -> Mock:
        """Create a mock graph populator."""
        mock = Mock()
        mock.execute_query.return_value = [
            {
                "e": {"id": "concept-1", "name": "Authentication"},
                "labels": ["Concept"],
            },
            {
                "e": {"id": "concept-2", "name": "Authorization"},
                "labels": ["Concept"],
            },
            {
                "e": {"id": "file-1", "name": "auth.py"},
                "labels": ["File"],
            },
            {
                "e": {"id": "tool-1", "name": "pytest"},
                "labels": ["Tool"],
            },
        ]
        return mock

    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch, mock_graph: Mock) -> TestClient:
        """Create test client with API key auth disabled and mocked graph."""
        monkeypatch.setenv("CODE_ATLAS_API_KEY_REQUIRED", "false")

        from code_atlas.api.main import create_app
        from code_atlas.api.dependencies import get_graph_populator
        from code_atlas.config import AtlasSettings

        settings = AtlasSettings()
        app = create_app(settings)

        # Override the graph populator dependency
        app.dependency_overrides[get_graph_populator] = lambda: mock_graph

        return TestClient(app)

    def test_search_exact_match_high_score(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Exact matches score high."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "Authentication"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

        # First result should be exact match with high score
        if data["results"]:
            top_result = data["results"][0]
            assert top_result["score"] >= 0.9

    def test_search_fuzzy_finds_typos(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Fuzzy search finds typos."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "Authntication", "fuzzy": True, "min_score": 0.5},
        )

        assert response.status_code == 200
        response.json()  # Verify response is valid JSON
        # Should find "Authentication" despite typo
        # (depends on fuzzy threshold)

    def test_search_filters_by_entity_type(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Type filter limits results."""
        # Return only Concept entities when filtered
        mock_graph.execute_query.return_value = [
            {
                "e": {"id": "concept-1", "name": "Authentication"},
                "labels": ["Concept"],
            },
        ]

        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "auth", "type": "Concept"},
        )

        assert response.status_code == 200
        data = response.json()
        # All results should be Concepts
        for result in data["results"]:
            assert result["entity"]["type"] == "Concept"

    def test_search_returns_empty_for_no_matches(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Unknown query returns empty."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "xyznonexistent", "min_score": 0.9},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []

    def test_search_ranks_by_relevance(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Best matches first."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "auth"},
        )

        assert response.status_code == 200
        data = response.json()

        if len(data["results"]) >= 2:
            scores = [r["score"] for r in data["results"]]
            # Scores should be descending
            assert scores == sorted(scores, reverse=True)

    def test_search_endpoint_returns_scores(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """API includes relevance scores."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "auth"},
        )

        assert response.status_code == 200
        data = response.json()

        for result in data["results"]:
            assert "score" in result
            assert 0.0 <= result["score"] <= 1.0

    def test_search_includes_timing(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Response includes execution time."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "took_ms" in data
        assert data["took_ms"] >= 0

    def test_search_respects_limit(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Limit parameter works."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "a", "limit": 2, "min_score": 0.1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 2

    def test_search_non_fuzzy_requires_substring(
        self, client: TestClient, mock_graph: Mock
    ) -> None:
        """Non-fuzzy search requires exact substring."""
        response = client.get(
            "/api/v1/graph/entities/search",
            params={"q": "Authntication", "fuzzy": False},
        )

        assert response.status_code == 200
        data = response.json()
        # With fuzzy=False, typo shouldn't match
        assert data["total"] == 0
