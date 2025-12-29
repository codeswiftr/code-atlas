"""Tests for security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from code_atlas.api.middleware import SecurityHeadersMiddleware


def create_test_app(middleware_kwargs: dict | None = None) -> FastAPI:
    """Create a test FastAPI app with security headers middleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "ok"}

    @app.get("/api/v1/entities")
    async def api_endpoint():
        return {"entities": []}

    app.add_middleware(SecurityHeadersMiddleware, **(middleware_kwargs or {}))
    return app


class TestSecurityHeaders:
    """Tests for security headers presence."""

    def test_response_includes_hsts_header(self):
        """HSTS header present with max-age."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    def test_response_includes_hsts_with_subdomains(self):
        """HSTS header includes subDomains directive."""
        app = create_test_app({"include_subdomains": True})
        client = TestClient(app)

        response = client.get("/test")

        assert "includeSubDomains" in response.headers["Strict-Transport-Security"]

    def test_response_includes_csp_header(self):
        """CSP header present."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "Content-Security-Policy" in response.headers
        assert "default-src" in response.headers["Content-Security-Policy"]

    def test_response_includes_frame_options(self):
        """X-Frame-Options DENY present."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_response_includes_content_type_options(self):
        """X-Content-Type-Options nosniff present."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_response_includes_referrer_policy(self):
        """Referrer-Policy header present."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_response_includes_permissions_policy(self):
        """Permissions-Policy header present."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/test")

        assert "Permissions-Policy" in response.headers
        assert "geolocation=()" in response.headers["Permissions-Policy"]


class TestSecurityHeadersOnAPIEndpoints:
    """Tests for security headers on API endpoints."""

    def test_security_headers_on_api_endpoints(self):
        """All /api/ paths have security headers."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/entities")

        # All security headers should be present
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "Referrer-Policy" in response.headers


class TestSecurityHeadersConfiguration:
    """Tests for configurable security headers."""

    def test_security_headers_configurable_hsts(self):
        """Custom HSTS max-age applied."""
        app = create_test_app({"hsts_max_age": 86400})  # 1 day
        client = TestClient(app)

        response = client.get("/test")

        assert "max-age=86400" in response.headers["Strict-Transport-Security"]

    def test_security_headers_configurable_csp(self):
        """Custom CSP policy applied."""
        custom_csp = "default-src 'none'"
        app = create_test_app({"csp_policy": custom_csp})
        client = TestClient(app)

        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_security_headers_configurable_frame_options(self):
        """Custom frame options applied."""
        app = create_test_app({"frame_options": "SAMEORIGIN"})
        client = TestClient(app)

        response = client.get("/test")

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_security_headers_disabled(self):
        """Headers not added when disabled."""
        app = create_test_app({"enabled": False})
        client = TestClient(app)

        response = client.get("/test")

        # Security headers should NOT be present when disabled
        assert "Strict-Transport-Security" not in response.headers
        assert "Content-Security-Policy" not in response.headers
        assert "X-Frame-Options" not in response.headers

    def test_security_headers_without_subdomains(self):
        """HSTS without includeSubDomains when configured."""
        app = create_test_app({"include_subdomains": False})
        client = TestClient(app)

        response = client.get("/test")

        assert "includeSubDomains" not in response.headers["Strict-Transport-Security"]
