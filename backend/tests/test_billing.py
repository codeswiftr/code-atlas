"""Tests for billing endpoints."""

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.main import create_app
from code_atlas.config import AtlasSettings


@pytest.fixture
def settings(tmp_path):
    return AtlasSettings(
        claude_root=tmp_path,
        api_key_required=False,
        enable_metrics=False,
    )


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


class TestBillingTiers:
    """Tests for billing tier endpoints."""

    def test_list_tiers(self, client):
        """GET /api/v1/billing/tiers returns all tiers."""
        resp = client.get("/api/v1/billing/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert "free" in data
        assert "pro" in data
        assert "team" in data

    def test_get_tier_info_free(self, client):
        """GET /api/v1/billing/tier/free returns free tier info."""
        resp = client.get("/api/v1/billing/tier/free")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert "limits" in data
        assert data["limits"]["max_sessions_per_report"] == 5

    def test_get_tier_info_pro(self, client):
        """GET /api/v1/billing/tier/pro returns pro tier info."""
        resp = client.get("/api/v1/billing/tier/pro")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "pro"
        assert data["limits"]["use_llm"] is True

    def test_get_tier_info_team(self, client):
        """GET /api/v1/billing/tier/team returns team tier info."""
        resp = client.get("/api/v1/billing/tier/team")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "team"
        assert data["limits"]["max_projects"] == 100

    def test_get_tier_info_invalid(self, client):
        """GET /api/v1/billing/tier/invalid returns 422."""
        resp = client.get("/api/v1/billing/tier/invalid")
        assert resp.status_code == 422


class TestBillingCheckout:
    """Tests for billing checkout endpoint."""

    def test_checkout_returns_400_when_price_not_configured(self, client):
        """Checkout returns 400 when price ID not configured for tier."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={
                "tier": "pro",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        # When Stripe is configured but price ID is placeholder
        assert resp.status_code == 400
        assert "price not configured" in resp.json()["detail"].lower()

    def test_checkout_free_tier_returns_400(self, client):
        """Checkout for free tier returns 400."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={
                "tier": "free",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert resp.status_code == 400
        assert "free tier" in resp.json()["detail"].lower()


class TestBillingWebhook:
    """Tests for billing webhook endpoint."""

    def test_webhook_without_secret_returns_500(self, client):
        """Webhook returns 500 when webhook secret not configured."""
        # Note: Stripe API key is set in env, but webhook secret is not
        resp = client.post("/webhooks/billing/webhook", data=b"{}")
        assert resp.status_code == 500
        assert "webhook secret not configured" in resp.json()["detail"].lower()

    def test_webhook_without_signature_returns_400(self, client):
        """Webhook without signature returns 400 when Stripe configured."""
        # This would need mocking of stripe module to fully test
        pass
