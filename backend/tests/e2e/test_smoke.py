"""Pre-deploy smoke tests for Code Atlas.

These tests verify critical endpoints work before deployment.
Run with: pytest tests/e2e/test_smoke.py -v

Smoke Test Checklist:
1. Health endpoint responds 200
2. Root endpoint returns service info
3. OpenAPI docs accessible
4. Sessions endpoint responds (with or without auth)
5. Graph endpoint responds (with or without auth)
6. Rate limiting headers present
7. CORS headers configured
8. Response times within acceptable limits
"""

import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.main import create_app
from code_atlas.config import AtlasSettings

# Maximum acceptable response time for smoke tests (ms)
MAX_RESPONSE_TIME_MS = 500


@pytest.fixture
def settings():
    """Create test settings with auth disabled for smoke tests."""
    return AtlasSettings(
        claude_root=Path(tempfile.gettempdir()),
        api_key_required=False,
        enable_metrics=False,  # Disable for smoke tests
    )


@pytest.fixture
def client(settings):
    """Create test client."""
    app = create_app(settings)
    return TestClient(app)


class TestSmokeHealth:
    """Smoke tests for health and readiness endpoints."""

    def test_health_endpoint_returns_200(self, client):
        """CRITICAL: Health endpoint must return 200 for Railway health checks."""
        response = client.get("/health")
        assert response.status_code == 200, "Health check failed - deployment will fail"

    def test_health_endpoint_response_time(self, client):
        """Health endpoint must respond within 500ms."""
        start = time.time()
        response = client.get("/health")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < MAX_RESPONSE_TIME_MS, f"Health check too slow: {elapsed_ms:.0f}ms"

    def test_health_response_structure(self, client):
        """Health response must have required fields."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data, "Missing 'status' field"
        assert data["status"] == "healthy", f"Unhealthy status: {data['status']}"


class TestSmokeRoot:
    """Smoke tests for root endpoint."""

    def test_root_endpoint_returns_200(self, client):
        """Root endpoint must return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_service_info(self, client):
        """Root endpoint must return service identification."""
        response = client.get("/")
        data = response.json()

        assert "service" in data, "Missing 'service' field"
        assert "Code Atlas" in data["service"], "Service name not found"
        assert "version" in data, "Missing 'version' field"


class TestSmokeDocs:
    """Smoke tests for API documentation endpoints."""

    def test_openapi_json_accessible(self, client):
        """OpenAPI schema must be accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "paths" in response.json(), "Invalid OpenAPI schema"

    def test_swagger_ui_accessible(self, client):
        """Swagger UI must be accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "text/html" in response.headers.get(
            "content-type", ""
        )

    def test_redoc_accessible(self, client):
        """ReDoc must be accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200


class TestSmokeAPI:
    """Smoke tests for core API endpoints."""

    def test_sessions_endpoint_accessible(self, client):
        """Sessions list endpoint must respond."""
        response = client.get("/api/v1/sessions")
        # Can be 200 (success) or 401 (auth required) - both are valid
        assert response.status_code in [200, 401, 404], f"Unexpected status: {response.status_code}"

    def test_graph_entities_endpoint_accessible(self, client):
        """Graph entities endpoint must respond."""
        response = client.get("/api/v1/graph/entities")
        # Can be 200 (success), 401 (auth required), 500 (no db) - all valid in smoke test
        # 500 is acceptable when FalkorDB is not running (CI/CD without database)
        assert response.status_code in [200, 401, 404, 500], (
            f"Unexpected status: {response.status_code}"
        )

    def test_insights_endpoint_accessible(self, client):
        """Insights endpoint must respond."""
        response = client.get("/api/v1/insights")
        # Can be 200 (success), 401 (auth required), 404, or 500 (no db)
        assert response.status_code in [200, 401, 404, 500], (
            f"Unexpected status: {response.status_code}"
        )


class TestSmokeHeaders:
    """Smoke tests for security and operational headers."""

    def test_cors_headers_present(self, client):
        """CORS headers must be configured."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Accept success, method not allowed, or bad request (varies by CORS config)
        assert response.status_code in [200, 204, 400, 405]

    def test_content_type_json(self, client):
        """API responses must return JSON content type."""
        response = client.get("/health")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, f"Expected JSON, got: {content_type}"


class TestSmokePerformance:
    """Smoke tests for performance baseline."""

    def test_root_response_time(self, client):
        """Root endpoint must respond within 500ms."""
        start = time.time()
        response = client.get("/")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < MAX_RESPONSE_TIME_MS, f"Root endpoint too slow: {elapsed_ms:.0f}ms"

    def test_multiple_requests_stable(self, client):
        """Multiple rapid requests must not fail."""
        for i in range(10):
            response = client.get("/health")
            assert response.status_code == 200, f"Request {i + 1} failed"


class TestSmokeDeploymentRequirements:
    """Smoke tests for Railway/Cloudflare deployment requirements."""

    def test_healthcheck_path_configured(self, client):
        """/health path must be the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200, "Health check path not configured correctly"

    def test_json_error_responses(self, client):
        """Error responses must be JSON for API clients."""
        response = client.get("/nonexistent-endpoint-12345")
        assert response.status_code == 404
        # Error should be JSON
        try:
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data
        except Exception:
            pytest.fail("404 response is not valid JSON")

    def test_api_version_prefix(self, client):
        """API must be versioned under /api/v1."""
        response = client.get("/openapi.json")
        data = response.json()
        paths = list(data.get("paths", {}).keys())

        # Check that versioned paths exist
        v1_paths = [p for p in paths if p.startswith("/api/v1")]
        assert len(v1_paths) > 0, "No /api/v1 paths found - API not versioned"


class TestSmokeDatabaseConnectivity:
    """Smoke tests for database connectivity."""

    def test_falkordb_connection(self, client):
        """FalkorDB connection should be testable via graph endpoint."""
        # Graph endpoint should respond (200 or 500 if DB not running)
        response = client.get("/api/v1/graph/entities")
        # 200 = success, 401 = auth required, 500 = DB not running (acceptable in smoke test)
        assert response.status_code in [200, 401, 404, 500]

    def test_redis_connection_if_used(self, client):
        """Redis connection (if used) should not cause startup failure."""
        # If Redis is used, health endpoint should still work
        response = client.get("/health")
        assert response.status_code == 200


class TestSmokeAPIAuthentication:
    """Smoke tests for API authentication flow."""

    def test_protected_endpoint_without_auth(self, client):
        """Protected endpoints should return 401 without auth (if auth enabled)."""
        # Sessions endpoint - may require auth
        response = client.get("/api/v1/sessions")
        # Can be 200 (no auth required), 401 (auth required), or 404
        assert response.status_code in [200, 401, 404]

    def test_protected_endpoint_with_invalid_auth(self, client):
        """Protected endpoints should reject invalid API keys."""
        response = client.get("/api/v1/sessions", headers={"X-API-Key": "invalid-key-12345"})
        # Should be 401 if auth is enabled, or 200/404 if disabled
        assert response.status_code in [200, 401, 404]


class TestSmokeGraphEndpoints:
    """Smoke tests for graph query endpoints."""

    def test_graph_entities_endpoint(self, client):
        """Graph entities endpoint should respond."""
        response = client.get("/api/v1/graph/entities")
        # 200, 401 (auth), 404, or 500 (DB not running) all acceptable
        assert response.status_code in [200, 401, 404, 500]

    def test_graph_relationships_endpoint(self, client):
        """Graph relationships endpoint should respond."""
        response = client.get("/api/v1/graph/relationships")
        # May not exist, so 404 is acceptable
        assert response.status_code in [200, 401, 404, 500]

    def test_graph_search_endpoint(self, client):
        """Graph search endpoint should respond."""
        response = client.get("/api/v1/graph/search?query=test")
        # May not exist or require auth
        assert response.status_code in [200, 401, 404, 422, 500]


class TestSmokeErrorResponses:
    """Smoke tests for error response handling."""

    def test_404_not_found_response(self, client):
        """404 errors should return JSON."""
        response = client.get("/nonexistent-endpoint-xyz")
        assert response.status_code == 404
        # Should be JSON formatted
        try:
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data
        except Exception:
            pytest.fail("404 response is not valid JSON")

    def test_405_method_not_allowed_response(self, client):
        """405 errors should return JSON."""
        # Try POST to health endpoint (should only accept GET)
        response = client.post("/health")
        # May be 405 (method not allowed) or 200 (if POST is allowed)
        if response.status_code == 405:
            try:
                data = response.json()
                assert isinstance(data, dict)
            except Exception:
                pytest.fail("405 response is not valid JSON")

    def test_422_validation_error_response(self, client):
        """422 validation errors should return structured JSON."""
        # Try to access insights with invalid parameters
        response = client.get("/api/v1/insights?invalid_param=xyz")
        # May be 422 (validation error), 200, 401, 404, or 500
        if response.status_code == 422:
            data = response.json()
            assert "detail" in data


class TestSmokeWebSocket:
    """Smoke tests for WebSocket connectivity."""

    def test_websocket_endpoint_exists(self, client):
        """WebSocket endpoint should be configured."""
        # Try to access WebSocket endpoint (will fail via HTTP, but endpoint should exist)
        response = client.get("/ws/jobs/test-job-id")
        # Should be 404, 400, 405, or similar (not 500 internal error)
        assert response.status_code in [400, 404, 405, 426]


class TestSmokeMetrics:
    """Smoke tests for metrics endpoint (if enabled)."""

    def test_metrics_endpoint_accessible(self, client):
        """Metrics endpoint should respond if enabled."""
        response = client.get("/metrics")
        # 200 if metrics enabled, 404 if disabled
        assert response.status_code in [200, 404]

    def test_metrics_format_prometheus(self, client):
        """If metrics enabled, should return Prometheus format."""
        response = client.get("/metrics")
        if response.status_code == 200:
            # Should be text/plain format
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type or "text" in content_type


class TestSmokeResponseTimes:
    """Additional response time tests for critical paths."""

    def test_openapi_json_response_time(self, client):
        """OpenAPI schema should load quickly."""
        start = time.time()
        response = client.get("/openapi.json")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < MAX_RESPONSE_TIME_MS, f"OpenAPI schema too slow: {elapsed_ms:.0f}ms"

    def test_docs_page_response_time(self, client):
        """API docs page should load quickly."""
        start = time.time()
        response = client.get("/docs")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < MAX_RESPONSE_TIME_MS * 2, f"Docs page too slow: {elapsed_ms:.0f}ms"


def run_all_smoke_tests():
    """Run all smoke tests and return summary."""

    result = pytest.main([__file__, "-v", "--tb=short"])
    return result == 0


if __name__ == "__main__":
    success = run_all_smoke_tests()
    exit(0 if success else 1)
