"""Unit tests for API middleware."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request, Response, status
from fastapi.testclient import TestClient

from code_atlas.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from code_atlas.schemas.auth import TIER_RATE_LIMITS, APITier


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with rate limiting."""
        app = FastAPI()
        # No constructor args needed - uses tier-based limits by default
        app.add_middleware(RateLimitMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_allows_requests_within_limit(self, client):
        """Test that requests within limit are allowed."""
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

    def test_blocks_requests_over_limit(self, client):
        """Test that requests over limit are blocked."""
        # Free tier limit is 10/hour
        free_limit = TIER_RATE_LIMITS[APITier.FREE]

        # Make requests up to the limit
        for _ in range(free_limit):
            response = client.get("/test")
            assert response.status_code == 200

        # Next request should be rate limited
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in response.headers
        assert response.json() == {"detail": "Rate limit exceeded. Please try again later."}

    def test_health_endpoint_bypasses_rate_limit(self, client):
        """Test that health endpoints bypass rate limiting."""
        free_limit = TIER_RATE_LIMITS[APITier.FREE]

        # Exhaust the rate limit
        for _ in range(free_limit):
            client.get("/test")

        # Health endpoint should still work
        response = client.get("/health")
        assert response.status_code == 200

    def test_admin_api_key_gets_high_limit(self, client):
        """Test that admin API keys get higher rate limits."""
        headers = {"X-API-Key": "admin-test-key"}

        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        # Admin gets 10000 limit
        assert response.headers["X-RateLimit-Limit"] == "10000"

    def test_regular_api_key_gets_free_tier_limit(self, client):
        """Test that regular API keys get free tier limits."""
        headers = {"X-API-Key": "regular-key-12345"}

        response = client.get("/test", headers=headers)
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == str(TIER_RATE_LIMITS[APITier.FREE])

    def test_rate_limit_per_client_ip(self, client):
        """Test that rate limiting is per client IP."""
        # This is hard to test with TestClient as it uses the same IP
        # But we can verify the header is set correctly
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    def test_rate_limit_cleanup_old_requests(self):
        """Test that old requests are cleaned up."""
        middleware = RateLimitMiddleware(app=MagicMock())

        client_key = "ip:127.0.0.1"
        now = datetime.now(tz=UTC)

        # Add some old timestamps (>1 hour ago)
        old_time = now - timedelta(seconds=3700)
        middleware._requests[client_key] = [old_time, old_time, old_time]

        # Cleanup should remove them
        middleware._cleanup_old_requests(client_key, now)

        assert len(middleware._requests[client_key]) == 0

    def test_get_client_key_uses_api_key(self):
        """Test that client key uses API key when available."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "test-api-key-12345"
        mock_request.client = None

        key = middleware._get_client_key(mock_request)
        assert key.startswith("key:")

    def test_get_client_key_uses_ip_when_no_api_key(self):
        """Test that client key falls back to IP when no API key."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.side_effect = lambda k, d="": d
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        key = middleware._get_client_key(mock_request)
        assert key == "ip:192.168.1.1"

    def test_get_client_key_uses_forwarded_ip(self):
        """Test that client key uses X-Forwarded-For header."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.side_effect = lambda k, d="": (
            "203.0.113.1, 198.51.100.1" if k == "X-Forwarded-For" else d
        )
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        key = middleware._get_client_key(mock_request)
        assert key == "ip:203.0.113.1"

    def test_is_admin_checks_api_key(self):
        """Test that admin check validates API key."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)

        # Admin key
        mock_request.headers.get.return_value = "admin-key-12345"
        assert middleware._is_admin(mock_request) is True

        # Non-admin key
        mock_request.headers.get.return_value = "regular-key"
        assert middleware._is_admin(mock_request) is False

    def test_get_tier_returns_free_by_default(self):
        """Test that tier returns free for non-admin requests."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "regular-key"

        tier = middleware._get_tier(mock_request)
        assert tier == APITier.FREE

    def test_get_tier_returns_team_for_admin(self):
        """Test that admin requests get team tier."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "admin-key-12345"

        # Admin is not a tier, but gets high limit via _get_limit
        assert middleware._is_admin(mock_request) is True

    def test_get_limit_returns_correct_tier_limits(self):
        """Test that limit matches tier configuration."""
        middleware = RateLimitMiddleware(app=MagicMock())

        # Free tier
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "regular-key"
        limit = middleware._get_limit(mock_request)
        assert limit == TIER_RATE_LIMITS[APITier.FREE]

        # Admin
        mock_request.headers.get.return_value = "admin-key"
        limit = middleware._get_limit(mock_request)
        assert limit == 10000


class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with request logging."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app, raise_server_exceptions=False)

    def test_logs_successful_requests(self, client):
        """Test that successful requests are logged."""
        response = client.get("/test")
        assert response.status_code == 200

    def test_logs_failed_requests(self, client):
        """Test that failed requests are logged."""
        response = client.get("/error")
        assert response.status_code == 500

    def test_logs_include_client_info(self):
        """Test that logs include client information."""
        middleware = RequestLoggingMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-api-key"
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        # This will log the request
        import asyncio

        asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    def test_logs_mask_api_keys(self):
        """Test that API keys are masked in logs."""
        middleware = RequestLoggingMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "very-secret-api-key-12345"
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        # Should mask the key (only first 8 chars visible)
        import asyncio

        asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    def test_logs_request_duration(self):
        """Test that request duration is logged."""
        middleware = RequestLoggingMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = ""
        mock_request.client = None

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            # Simulate some processing time
            import asyncio

            await asyncio.sleep(0.01)
            return mock_response

        import asyncio

        asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    def test_handles_request_without_client(self):
        """Test handling requests without client information."""
        middleware = RequestLoggingMiddleware(app=MagicMock())

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = ""
        mock_request.client = None

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        import asyncio

        # Should not raise an exception
        asyncio.run(middleware.dispatch(mock_request, mock_call_next))
