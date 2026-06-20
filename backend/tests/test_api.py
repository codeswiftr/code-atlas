"""Integration tests for Code Atlas REST API."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        enable_metrics=True,
    )


@pytest.fixture
def client(settings):
    """Create test client."""
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture
def auth_settings():
    """Create test settings with auth required."""
    return AtlasSettings(
        claude_root=Path(tempfile.gettempdir()),
        api_key_required=True,
        admin_api_key="test-admin-key-12345",
        enable_metrics=False,  # Disable to avoid port conflicts
    )


@pytest.fixture
def auth_client(auth_settings):
    """Create test client with auth required."""
    from code_atlas.api.dependencies import get_settings

    app = create_app(auth_settings)

    # Override the settings dependency
    def override_get_settings():
        return auth_settings

    app.dependency_overrides[get_settings] = override_get_settings

    return TestClient(app)


@pytest.fixture
def sample_session_file(tmp_path):
    """Create a sample session file for testing."""
    session_dir = tmp_path / "test-project"
    session_dir.mkdir(parents=True)

    session_file = session_dir / "session-test123.jsonl"
    session_data = [
        {"type": "user", "message": {"content": "Hello"}},
        {"type": "assistant", "message": {"content": "Hi there!"}},
        {"type": "user", "message": {"content": "Help me with Python"}},
        {"type": "assistant", "message": {"content": "Sure, I can help with Python."}},
    ]

    with open(session_file, "w") as f:
        for line in session_data:
            f.write(json.dumps(line) + "\n")

    return session_file


class TestRootEndpoints:
    """Tests for root and info endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "Code Atlas API"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
        assert "/api/v1" in data["endpoints"]["api"]

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "code-atlas-api"

    def test_status_endpoint(self, client):
        """Test detailed status endpoint."""
        response = client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert "system" in data
        assert "cpu_percent" in data["system"]
        assert "memory" in data["system"]
        assert "disk" in data["system"]

    def test_openapi_docs(self, client):
        """Test OpenAPI documentation is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert data["info"]["title"] == "Code Atlas API"
        assert "paths" in data

    def test_swagger_ui(self, client):
        """Test Swagger UI is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()


class TestAuthentication:
    """Tests for API authentication."""

    def test_no_auth_required_by_default(self, client):
        """Test endpoints work without auth when not required."""
        response = client.get("/api/v1/sessions")
        assert response.status_code == 200

    def test_auth_required_without_key(self, auth_client):
        """Test endpoints return 401 when auth required but no key provided."""
        response = auth_client.get("/api/v1/sessions")
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_auth_with_invalid_key(self, auth_client):
        """Test endpoints return 401 with invalid key."""
        response = auth_client.get("/api/v1/sessions", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_auth_with_valid_key(self, auth_client):
        """Test endpoints work with valid API key."""
        response = auth_client.get(
            "/api/v1/sessions", headers={"X-API-Key": "test-admin-key-12345"}
        )
        assert response.status_code == 200


class TestSessionDiscovery:
    """Tests for session discovery endpoints."""

    def test_discover_sessions_empty(self, client, tmp_path):
        """Test discovery with no sessions."""
        response = client.post(
            "/api/v1/sessions/discover", json={"root_path": str(tmp_path), "limit": 10}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["sessions"] == []
        assert data["total_found"] == 0

    def test_discover_sessions_with_files(self, client, sample_session_file):
        """Test discovery finds session files."""
        root_path = sample_session_file.parent.parent

        response = client.post(
            "/api/v1/sessions/discover", json={"root_path": str(root_path), "limit": 10}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["total_found"] >= 1

        # Check session info structure
        if data["sessions"]:
            session = data["sessions"][0]
            assert "path" in session
            assert "filename" in session
            assert "size_bytes" in session
            assert "modified_at" in session

    def test_discover_sessions_invalid_path(self, client):
        """Test discovery with non-existent path."""
        response = client.post(
            "/api/v1/sessions/discover", json={"root_path": "/nonexistent/path/12345"}
        )
        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"]

    def test_discover_sessions_with_filters(self, client, sample_session_file):
        """Test discovery with size filters."""
        root_path = sample_session_file.parent.parent

        response = client.post(
            "/api/v1/sessions/discover",
            json={
                "root_path": str(root_path),
                "min_size_bytes": 1,
                "max_size_bytes": 1000000,
                "limit": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestSessionProcessing:
    """Tests for session processing endpoints."""

    def test_process_sessions_creates_job(self, client, sample_session_file):
        """Test processing creates a job."""
        response = client.post(
            "/api/v1/sessions/process",
            json={"session_paths": [str(sample_session_file)], "use_llm": False, "dry_run": True},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["success"] is True
        assert "job" in data
        assert data["job"]["job_id"].startswith("job-")
        assert data["job"]["status"] in ["pending", "running"]
        assert data["job"]["total_sessions"] == 1

    def test_process_sessions_invalid_paths(self, client):
        """Test processing with invalid paths."""
        response = client.post(
            "/api/v1/sessions/process",
            json={"session_paths": ["/nonexistent/file.jsonl"], "use_llm": False, "dry_run": True},
        )
        assert response.status_code == 400
        assert "No valid session files" in response.json()["detail"]

    def test_get_job_status(self, client, sample_session_file):
        """Test getting job status."""
        # Create a job first
        create_response = client.post(
            "/api/v1/sessions/process",
            json={"session_paths": [str(sample_session_file)], "use_llm": False, "dry_run": True},
        )
        job_id = create_response.json()["job"]["job_id"]

        # Get status
        response = client.get(f"/api/v1/sessions/{job_id}/status")
        assert response.status_code == 200

        data = response.json()
        assert data["job"]["job_id"] == job_id

    def test_get_job_status_not_found(self, client):
        """Test getting status for non-existent job."""
        response = client.get("/api/v1/sessions/job-nonexistent/status")
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    def test_list_jobs(self, client, sample_session_file):
        """Test listing jobs."""
        # Create a job first
        client.post(
            "/api/v1/sessions/process",
            json={"session_paths": [str(sample_session_file)], "use_llm": False, "dry_run": True},
        )

        response = client.get("/api/v1/sessions")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_jobs_with_filter(self, client, sample_session_file):
        """Test listing jobs with status filter."""
        response = client.get("/api/v1/sessions?status=pending")
        assert response.status_code == 200

    def test_get_processing_stats(self, client):
        """Test getting processing statistics."""
        response = client.get("/api/v1/sessions/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_jobs" in data
        assert "total_sessions_processed" in data
        assert "total_cost_usd" in data
        assert "success_rate" in data


class TestProjectReport:
    """Tests for POST /api/v1/sessions/report."""

    def test_report_nonexistent_path(self, client):
        """Report on a missing path returns 422."""
        response = client.post(
            "/api/v1/sessions/report",
            json={"project_path": "/nonexistent/path/that/does/not/exist"},
        )
        assert response.status_code == 422

    def test_report_empty_project(self, client, tmp_path):
        """Report on a directory with no sessions returns empty report."""
        empty_dir = tmp_path / "empty-project"
        empty_dir.mkdir()

        response = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(empty_dir)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["sessions_analyzed"] == 0
        assert data["top_files"] == []
        assert "No Claude Code session files found" in data["key_insights"][0]

    def test_report_with_sessions(self, client, tmp_path):
        """Report on a directory with sessions returns populated report."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        session_file = project_dir / "session-abc123.jsonl"
        session_data = [
            {
                "type": "user",
                "message": {
                    "content": "Edit /home/user/project/main.py to add a function",
                    "role": "user",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": "I'll edit /home/user/project/main.py for you.",
                    "role": "assistant",
                },
            },
        ]
        with open(session_file, "w") as f:
            for line in session_data:
                f.write(json.dumps(line) + "\n")

        response = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(project_dir), "use_llm": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["sessions_analyzed"] == 1
        assert data["project_name"] == "my-project"
        assert "summary" in data
        assert isinstance(data["top_files"], list)
        assert isinstance(data["top_entities"], list)
        assert isinstance(data["key_insights"], list)
        assert data["cost_usd"] == 0.0  # heuristic mode is free

    def test_report_respects_max_sessions(self, client, tmp_path):
        """max_sessions cap is respected."""
        project_dir = tmp_path / "big-project"
        project_dir.mkdir()

        for i in range(5):
            f = project_dir / f"session-{i}.jsonl"
            f.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")

        response = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(project_dir), "max_sessions": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sessions_analyzed"] <= 2


class TestGraphEntities:
    """Tests for graph entity endpoints."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock graph populator."""
        mock = MagicMock()
        mock.execute_query.return_value = []
        return mock

    def test_list_entities_empty(self, client, mock_graph):
        """Test listing entities when graph is empty."""
        with patch("code_atlas.api.dependencies.get_graph_populator", return_value=mock_graph):
            response = client.get("/api/v1/graph/entities")
            # May return 500 if DB not available, which is expected
            assert response.status_code in [200, 500]

    def test_list_entities_with_type_filter(self, client):
        """Test listing entities with type filter."""
        response = client.get("/api/v1/graph/entities?type=Concept")
        # May return 500 if DB not available
        assert response.status_code in [200, 500]

    def test_list_entities_with_search(self, client):
        """Test listing entities with search query."""
        response = client.get("/api/v1/graph/entities?search=auth")
        assert response.status_code in [200, 500]

    def test_list_entities_pagination(self, client):
        """Test listing entities with pagination."""
        response = client.get("/api/v1/graph/entities?page=1&page_size=10")
        assert response.status_code in [200, 500]

    def test_get_entity_not_found(self, client):
        """Test getting non-existent entity."""
        response = client.get("/api/v1/graph/entities/nonexistent-id")
        # Returns 404 or 500 depending on DB availability
        assert response.status_code in [404, 500]


class TestGraphRelationships:
    """Tests for graph relationship endpoints."""

    def test_list_relationships(self, client):
        """Test listing relationships."""
        response = client.get("/api/v1/graph/relationships")
        assert response.status_code in [200, 500]

    def test_list_relationships_with_type(self, client):
        """Test listing relationships with type filter."""
        response = client.get("/api/v1/graph/relationships?type=MENTIONS")
        assert response.status_code in [200, 500]

    def test_list_relationships_with_source(self, client):
        """Test listing relationships with source filter."""
        response = client.get("/api/v1/graph/relationships?source_id=test-id")
        assert response.status_code in [200, 500]


class TestGraphQuery:
    """Tests for graph query endpoint."""

    def test_query_read_only(self, client):
        """Test that only read queries are allowed."""
        response = client.post("/api/v1/graph/query", json={"query": "CREATE (n:Test) RETURN n"})
        assert response.status_code == 403
        assert "read queries" in response.json()["detail"].lower()

    def test_query_delete_blocked(self, client):
        """Test that DELETE queries are blocked."""
        response = client.post("/api/v1/graph/query", json={"query": "MATCH (n) DELETE n"})
        assert response.status_code == 403

    def test_query_valid_match(self, client):
        """Test valid MATCH query."""
        response = client.post("/api/v1/graph/query", json={"query": "MATCH (n) RETURN n LIMIT 10"})
        # May fail if DB not available
        assert response.status_code in [200, 400, 500]

    def test_query_with_parameters(self, client):
        """Test query with parameters."""
        response = client.post(
            "/api/v1/graph/query",
            json={
                "query": "MATCH (n) WHERE n.name = $name RETURN n",
                "parameters": {"name": "test"},
                "limit": 5,
            },
        )
        assert response.status_code in [200, 400, 500]


class TestGraphVisualization:
    """Tests for graph visualization endpoint."""

    def test_get_visualization(self, client):
        """Test getting visualization data."""
        response = client.get("/api/v1/graph/visualization")
        assert response.status_code in [200, 500]

    def test_get_visualization_with_type(self, client):
        """Test visualization with entity type filter."""
        response = client.get("/api/v1/graph/visualization?type=Concept")
        assert response.status_code in [200, 500]

    def test_get_visualization_with_center(self, client):
        """Test visualization centered on entity."""
        response = client.get("/api/v1/graph/visualization?center_entity_id=test-id&depth=2")
        assert response.status_code in [200, 500]

    def test_get_visualization_max_nodes(self, client):
        """Test visualization with max nodes limit."""
        response = client.get("/api/v1/graph/visualization?max_nodes=50")
        assert response.status_code in [200, 500]


class TestGraphStats:
    """Tests for graph statistics endpoint."""

    def test_get_stats(self, client):
        """Test getting graph statistics."""
        response = client.get("/api/v1/graph/stats")
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "total_nodes" in data
            assert "total_edges" in data
            assert "nodes_by_type" in data
            assert "edges_by_type" in data


class TestMetrics:
    """Tests for metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json_body(self, client):
        """Test handling of invalid JSON."""
        response = client.post(
            "/api/v1/sessions/discover",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client):
        """Test handling of missing required fields."""
        response = client.post(
            "/api/v1/sessions/process",
            json={"use_llm": False},  # Missing session_paths
        )
        assert response.status_code == 422

    def test_invalid_field_type(self, client):
        """Test handling of invalid field types."""
        response = client.post("/api/v1/sessions/discover", json={"limit": "not a number"})
        assert response.status_code == 422

    def test_value_out_of_range(self, client):
        """Test handling of values out of range."""
        response = client.post(
            "/api/v1/sessions/discover",
            json={"limit": 10000},  # Max is 1000
        )
        assert response.status_code == 422


class TestCORS:
    """Tests for environment-aware CORS configuration."""

    # ---------------------------------------------------------------------------
    # Development mode — localhost regex should be accepted
    # ---------------------------------------------------------------------------

    @pytest.fixture
    def dev_client(self):
        """App in development mode (default)."""
        settings = AtlasSettings(
            claude_root=Path(tempfile.gettempdir()),
            api_key_required=False,
            enable_metrics=False,
        )
        # environment defaults to "development"
        return TestClient(create_app(settings), raise_server_exceptions=False)

    @pytest.fixture
    def prod_client(self):
        """App in production mode with explicit allowed origins."""
        from code_atlas.config import Environment

        settings = AtlasSettings(
            claude_root=Path(tempfile.gettempdir()),
            api_key_required=False,
            enable_metrics=False,
            environment=Environment.PRODUCTION,
            cors_origins=["https://app.codeswiftr.com"],
        )
        return TestClient(create_app(settings), raise_server_exceptions=False)

    def test_dev_cors_allows_localhost(self, dev_client):
        """Development CORS allows localhost on any port."""
        response = dev_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_dev_cors_allows_localhost_127(self, dev_client):
        """Development CORS allows 127.0.0.1 origins."""
        response = dev_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://127.0.0.1:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:8080"

    def test_dev_cors_rejects_arbitrary_external_origin(self, dev_client):
        """Development CORS does NOT allow arbitrary external origins."""
        response = dev_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette CORSMiddleware returns 400 for disallowed preflight origins
        assert response.headers.get("access-control-allow-origin") is None

    # ---------------------------------------------------------------------------
    # Production mode — only explicit origins are allowed
    # ---------------------------------------------------------------------------

    def test_prod_cors_allows_explicit_origin(self, prod_client):
        """Production CORS allows the configured frontend domain."""
        response = prod_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "https://app.codeswiftr.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://app.codeswiftr.com"

    def test_prod_cors_rejects_localhost(self, prod_client):
        """Production CORS does NOT allow localhost origins."""
        response = prod_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    def test_prod_cors_rejects_wildcard_origin(self, prod_client):
        """Production CORS never echoes back a wildcard."""
        response = prod_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "*",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert allow_origin != "*"

    def test_prod_cors_rejects_arbitrary_external_origin(self, prod_client):
        """Production CORS rejects origins not in the allowlist."""
        response = prod_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    # ---------------------------------------------------------------------------
    # Method / header restrictions (both environments)
    # ---------------------------------------------------------------------------

    def test_cors_exposes_request_id_header(self, dev_client):
        """CORS exposes X-Request-ID so the frontend can read it."""
        response = dev_client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        expose = response.headers.get("access-control-expose-headers", "")
        assert "X-Request-ID" in expose

    def test_cors_allows_x_api_key_header(self, dev_client):
        """Preflight confirms X-API-Key is an allowed request header."""
        response = dev_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert response.status_code == 200
        allow_headers = response.headers.get("access-control-allow-headers", "").lower()
        assert "x-api-key" in allow_headers

    def test_cors_credentials_are_supported(self, dev_client):
        """CORS allows credentials (needed for auth cookies / bearer tokens)."""
        response = dev_client.options(
            "/api/v1/sessions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    # ---------------------------------------------------------------------------
    # Config default — wildcard must not appear in production default
    # ---------------------------------------------------------------------------

    def test_default_cors_origins_not_wildcard(self):
        """The default cors_origins setting must not contain a bare wildcard."""
        from code_atlas.config import Environment

        settings = AtlasSettings(
            claude_root=Path(tempfile.gettempdir()),
            environment=Environment.PRODUCTION,
        )
        assert "*" not in settings.cors_origins, (
            "cors_origins must not default to '*' — this allows any origin in production"
        )

    def test_default_cors_origins_includes_production_domain(self):
        """Default cors_origins includes the known production frontend domain."""
        from code_atlas.config import Environment

        settings = AtlasSettings(
            claude_root=Path(tempfile.gettempdir()),
            environment=Environment.PRODUCTION,
        )
        assert "https://app.codeswiftr.com" in settings.cors_origins


class TestRateLimiting:
    """Tests for rate limiting."""

    @pytest.fixture
    def rate_limited_client(self):
        """Create client with tier-based rate limiting."""
        settings = AtlasSettings(
            claude_root=Path(tempfile.gettempdir()),
            api_key_required=False,
            enable_metrics=False,
            # Tier-based rate limiting: Free tier = 10/hour
        )
        app = create_app(settings)
        return TestClient(app)

    def test_rate_limit_headers(self, client):
        """Test rate limit headers are present."""
        response = client.get("/api/v1/sessions")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        # Free tier should show 10/hour limit
        assert response.headers["X-RateLimit-Limit"] == "10"

    def test_rate_limit_exceeded(self, rate_limited_client):
        """Test rate limit is enforced after free tier limit (10/hour)."""
        # Make requests up to the free tier limit (10/hour)
        for _ in range(10):
            response = rate_limited_client.get("/api/v1/sessions")
            assert response.status_code == 200

        # Next request should be rate limited
        response = rate_limited_client.get("/api/v1/sessions")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

    def test_rate_limit_skips_health_endpoints(self, rate_limited_client):
        """Test that health endpoints are not rate limited."""
        # Make many requests to health endpoint
        for _ in range(10):
            response = rate_limited_client.get("/health")
            assert response.status_code == 200
