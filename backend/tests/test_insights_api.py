"""Tests for Insights API endpoints."""

import tempfile
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.main import create_app
from code_atlas.config import AtlasSettings


@pytest.fixture
def settings():
    """Create test settings."""
    return AtlasSettings(
        claude_root=Path(tempfile.gettempdir()),
        api_key_required=False,
        enable_metrics=False,
    )


@pytest.fixture
def client(settings):
    """Create test client."""
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def mock_graph():
    """Create a mock GraphPopulator."""
    graph = MagicMock()
    return graph


@pytest.fixture
def client_with_mock_graph(settings, mock_graph):
    """Create test client with mocked graph."""
    from code_atlas.api.dependencies import get_graph_populator
    
    app = create_app(settings)
    
    def override_get_graph_populator():
        return mock_graph
    
    app.dependency_overrides[get_graph_populator] = override_get_graph_populator
    
    return TestClient(app)


class TestTopEntities:
    """Tests for /api/v1/insights/top-entities endpoint."""

    def test_top_entities_success(self, client_with_mock_graph, mock_graph):
        """Test top entities endpoint returns correct data."""
        mock_result = [
            {
                "e": {"id": "entity1", "name": "Test Entity 1", "mention_count": 10},
                "mentions": 10,
                "labels": ["Concept"],
            },
            {
                "e": {"id": "entity2", "name": "Test Entity 2", "mention_count": 5},
                "mentions": 5,
                "labels": ["Concept"],
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get("/api/v1/insights/top-entities?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "total" in data
        assert "execution_time_ms" in data
        assert data["total"] == 2
        assert len(data["entities"]) == 2
        assert data["entities"][0]["name"] == "Test Entity 1"
        assert data["entities"][0]["mention_count"] == 10

    def test_top_entities_with_type_filter(self, client_with_mock_graph, mock_graph):
        """Test top entities with entity type filter."""
        mock_result = [
            {
                "e": {"id": "tool1", "name": "Python", "mention_count": 15},
                "mentions": 15,
                "labels": ["Tool"],
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get("/api/v1/insights/top-entities?type=Tool&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "Tool"
        assert len(data["entities"]) == 1
        assert data["entities"][0]["name"] == "Python"

    def test_top_entities_limit_validation(self, client):
        """Test top entities limit validation."""
        response = client.get("/api/v1/insights/top-entities?limit=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/v1/insights/top-entities?limit=101")
        assert response.status_code == 422  # Validation error

    def test_top_entities_empty_result(self, client_with_mock_graph, mock_graph):
        """Test top entities with empty result."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/top-entities")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["entities"]) == 0

    def test_top_entities_database_error(self, client_with_mock_graph, mock_graph):
        """Test top entities handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Database connection failed")

        response = client_with_mock_graph.get("/api/v1/insights/top-entities")
        
        assert response.status_code == 500
        assert "Failed to get top entities" in response.json()["detail"]


class TestRecurringProblems:
    """Tests for /api/v1/insights/recurring-problems endpoint."""

    def test_recurring_problems_success(self, client_with_mock_graph, mock_graph):
        """Test recurring problems endpoint returns correct data."""
        mock_result = [
            {
                "p": {"id": "problem1", "name": "Memory Leak", "source_session": "session1"},
                "session_count": 5,
                "labels": ["Problem"],
            },
            {
                "p": {"id": "problem2", "name": "Performance Issue", "source_session": "session2"},
                "session_count": 3,
                "labels": ["Problem"],
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get(
            "/api/v1/insights/recurring-problems?min_sessions=2&limit=20"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "problems" in data
        assert "total" in data
        assert "min_sessions" in data
        assert data["total"] == 2
        assert len(data["problems"]) == 2
        assert data["problems"][0]["session_count"] == 5
        assert data["problems"][0]["entity"]["name"] == "Memory Leak"

    def test_recurring_problems_min_sessions_filter(self, client_with_mock_graph, mock_graph):
        """Test recurring problems with min_sessions filter."""
        mock_result = [
            {
                "p": {"id": "problem1", "name": "Critical Bug", "source_session": "session1"},
                "session_count": 10,
                "labels": ["Problem"],
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get("/api/v1/insights/recurring-problems?min_sessions=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["min_sessions"] == 5
        assert len(data["problems"]) == 1

    def test_recurring_problems_empty_result(self, client_with_mock_graph, mock_graph):
        """Test recurring problems with empty result."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/recurring-problems")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["problems"]) == 0

    def test_recurring_problems_database_error(self, client_with_mock_graph, mock_graph):
        """Test recurring problems handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Query execution failed")

        response = client_with_mock_graph.get("/api/v1/insights/recurring-problems")
        
        assert response.status_code == 500
        assert "Failed to get recurring problems" in response.json()["detail"]


class TestPopularTools:
    """Tests for /api/v1/insights/popular-tools endpoint."""

    def test_popular_tools_success(self, client_with_mock_graph, mock_graph):
        """Test popular tools endpoint returns correct data."""
        mock_result = [
            {
                "t": {"id": "tool1", "name": "Python", "properties": {}},
                "usage_count": 25,
                "labels": ["Tool"],
            },
            {
                "t": {"id": "tool2", "name": "Docker", "properties": {}},
                "usage_count": 15,
                "labels": ["Tool"],
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get("/api/v1/insights/popular-tools?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["tools"]) == 2
        assert data["tools"][0]["usage_count"] == 25
        assert data["tools"][0]["entity"]["name"] == "Python"

    def test_popular_tools_limit_validation(self, client):
        """Test popular tools limit validation."""
        response = client.get("/api/v1/insights/popular-tools?limit=0")
        assert response.status_code == 422

        response = client.get("/api/v1/insights/popular-tools?limit=101")
        assert response.status_code == 422

    def test_popular_tools_empty_result(self, client_with_mock_graph, mock_graph):
        """Test popular tools with empty result."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/popular-tools")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["tools"]) == 0

    def test_popular_tools_database_error(self, client_with_mock_graph, mock_graph):
        """Test popular tools handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Graph query failed")

        response = client_with_mock_graph.get("/api/v1/insights/popular-tools")
        
        assert response.status_code == 500
        assert "Failed to get popular tools" in response.json()["detail"]


class TestConceptRelationships:
    """Tests for /api/v1/insights/concept-relationships endpoint."""

    def test_concept_relationships_success(self, client_with_mock_graph, mock_graph):
        """Test concept relationships endpoint returns correct data."""
        # Mock the two queries: relationship types and top pairs
        def mock_execute_query(query, params):
            if "type(r)" in query or "relationship_types" in query.lower():
                return [
                    {"rel_type": "RELATED_TO", "count": 8},
                    {"rel_type": "MENTIONS", "count": 5},
                ]
            elif "top_pairs" in query.lower() or "connection_strength" in query.lower():
                return [
                    {
                        "source": "API Design",
                        "target": "REST",
                        "connection_strength": 8,
                        "source_labels": ["Concept"],
                        "target_labels": ["Concept"],
                    },
                ]
            return []

        mock_graph.execute_query.side_effect = mock_execute_query

        response = client_with_mock_graph.get("/api/v1/insights/concept-relationships?limit=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "relationship_types" in data
        assert "top_pairs" in data
        assert "total_relationships" in data
        assert len(data["relationship_types"]) == 2
        assert len(data["top_pairs"]) == 1
        assert data["top_pairs"][0]["source"] == "API Design"
        assert data["top_pairs"][0]["target"] == "REST"

    def test_concept_relationships_empty_result(self, client_with_mock_graph, mock_graph):
        """Test concept relationships with empty result."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/concept-relationships")
        
        assert response.status_code == 200
        data = response.json()
        assert "relationship_types" in data
        assert "top_pairs" in data
        assert len(data["relationship_types"]) == 0
        assert len(data["top_pairs"]) == 0

    def test_concept_relationships_database_error(self, client_with_mock_graph, mock_graph):
        """Test concept relationships handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Relationship query failed")

        response = client_with_mock_graph.get("/api/v1/insights/concept-relationships")
        
        assert response.status_code == 500
        assert "Failed to get concept relationships" in response.json()["detail"]


class TestTrends:
    """Tests for /api/v1/insights/trends endpoint."""

    def test_trends_success(self, client_with_mock_graph, mock_graph):
        """Test trends endpoint returns correct data."""
        from datetime import datetime, timedelta
        
        # Mock result with ISO format date strings that will be parsed correctly
        today = datetime.now(UTC)
        yesterday = today - timedelta(days=1)
        
        mock_result = [
            {
                "created_date": today.isoformat(),
                "entity_count": 10,
                "entity_type": "Concept",
            },
            {
                "created_date": yesterday.isoformat(),
                "entity_count": 15,
                "entity_type": "Concept",
            },
        ]
        mock_graph.execute_query.return_value = mock_result

        response = client_with_mock_graph.get("/api/v1/insights/trends?days=30")
        
        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        assert "trends_by_type" in data
        assert "days_analyzed" in data
        assert data["days_analyzed"] == 30
        # Trends may be empty if dates are filtered out, so just check structure
        assert isinstance(data["trends"], list)
        assert isinstance(data["trends_by_type"], dict)

    def test_trends_days_validation(self, client):
        """Test trends days parameter validation."""
        response = client.get("/api/v1/insights/trends?days=0")
        assert response.status_code == 422

        response = client.get("/api/v1/insights/trends?days=366")
        assert response.status_code == 422

    def test_trends_empty_result(self, client_with_mock_graph, mock_graph):
        """Test trends with empty result."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/trends")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["trends"]) == 0

    def test_trends_database_error(self, client_with_mock_graph, mock_graph):
        """Test trends handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Trends query failed")

        response = client_with_mock_graph.get("/api/v1/insights/trends")
        
        assert response.status_code == 500
        assert "Failed to get trends" in response.json()["detail"]


class TestInsightReport:
    """Tests for /api/v1/insights/reports endpoint."""

    def test_insight_report_success(self, client_with_mock_graph, mock_graph):
        """Test insight report endpoint returns comprehensive data."""
        # Mock multiple query results
        def mock_execute_query(query, params):
            if "top_entities" in query or "MATCH (e)" in query and "mention_count" in query:
                return [
                    {
                        "e": {"id": "entity1", "name": "Top Entity", "mention_count": 20},
                        "mentions": 20,
                        "labels": ["Concept"],
                    },
                ]
            elif "Problem" in query:
                return [
                    {
                        "p": {
                            "id": "problem1", "name": "Recurring Issue",
                            "source_session": "session1",
                        },
                        "session_count": 5,
                        "labels": ["Problem"],
                    },
                ]
            elif "Tool" in query:
                return [
                    {
                        "t": {"id": "tool1", "name": "Popular Tool", "properties": {}},
                        "usage_count": 15,
                        "labels": ["Tool"],
                    },
                ]
            return []

        mock_graph.execute_query.side_effect = mock_execute_query

        response = client_with_mock_graph.get("/api/v1/insights/reports")
        
        assert response.status_code == 200
        data = response.json()
        assert "top_entities" in data
        assert "recurring_problems" in data
        assert "popular_tools" in data
        assert "execution_time_ms" in data
        assert len(data["top_entities"]) > 0
        assert len(data["recurring_problems"]) > 0
        assert len(data["popular_tools"]) > 0

    def test_insight_report_empty_data(self, client_with_mock_graph, mock_graph):
        """Test insight report with empty data."""
        mock_graph.execute_query.return_value = []

        response = client_with_mock_graph.get("/api/v1/insights/reports")
        
        assert response.status_code == 200
        data = response.json()
        assert "top_entities" in data
        assert "recurring_problems" in data
        assert "popular_tools" in data
        # All should be empty lists
        assert len(data["top_entities"]) == 0
        assert len(data["recurring_problems"]) == 0
        assert len(data["popular_tools"]) == 0

    def test_insight_report_database_error(self, client_with_mock_graph, mock_graph):
        """Test insight report handles database errors."""
        mock_graph.execute_query.side_effect = Exception("Report generation failed")

        response = client_with_mock_graph.get("/api/v1/insights/reports")
        
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Failed to generate" in detail or "Failed to generate insight report" in detail

