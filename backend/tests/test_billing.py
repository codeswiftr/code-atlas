"""Tests for billing API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.v1.billing import _get_tier_price, router
from code_atlas.schemas.auth import APITier


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)  # Router already has /billing prefix
    return TestClient(app)


class TestBillingCheckout:
    """Tests for POST /billing/checkout."""

    def test_checkout_pro_tier(self, client):
        """Test checkout for Pro tier in development mode."""
        response = client.post(
            "/billing/checkout",
            json={"tier": "pro"},
        )
        # Development mode doesn't require auth
        assert response.status_code == 201
        data = response.json()
        assert data["tier"] == "pro"
        assert "session_id" in data
        assert data["amount_cents"] == 2900

    def test_checkout_team_tier(self, client):
        """Test checkout for Team tier."""
        response = client.post(
            "/billing/checkout",
            json={"tier": "team"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tier"] == "team"
        assert data["amount_cents"] == 9900

    def test_checkout_free_tier(self, client):
        """Test checkout for Free tier."""
        response = client.post(
            "/billing/checkout",
            json={"tier": "free"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tier"] == "free"
        assert data["amount_cents"] == 0

    def test_checkout_invalid_tier(self, client):
        """Test checkout with invalid tier."""
        response = client.post(
            "/billing/checkout",
            json={"tier": "invalid"},
        )
        # Should fail validation
        assert response.status_code == 422


class TestBillingWebhook:
    """Tests for POST /billing/webhook."""

    def test_webhook_returns_200_dev_mode(self):
        """Test webhook endpoint returns 200 in dev mode."""
        with patch("code_atlas.api.v1.billing.STRIPE_WEBHOOK_SECRET", "test_secret"):
            with patch("code_atlas.api.v1.billing.STRIPE_SECRET_KEY", "sk_test_"):
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                from code_atlas.api.v1.billing import router

                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                response = client.post("/billing/webhook", json={})
                assert response.status_code == 200

    def test_webhook_handles_checkout_completed(self):
        """Test handling checkout.session.completed event."""
        with patch("code_atlas.api.v1.billing.STRIPE_WEBHOOK_SECRET", "test_secret"):
            with patch("code_atlas.api.v1.billing.STRIPE_SECRET_KEY", "sk_test_"):
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                from code_atlas.api.v1.billing import router

                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                event = {
                    "type": "checkout.session.completed",
                    "data": {
                        "customer": "cus_test123",
                        "subscription": "sub_test123",
                        "metadata": {"tier": "pro"},
                    },
                }
                response = client.post("/billing/webhook", json=event)
                assert response.status_code == 200

    def test_webhook_handles_subscription_deleted(self):
        """Test handling customer.subscription.deleted event."""
        with patch("code_atlas.api.v1.billing.STRIPE_WEBHOOK_SECRET", "test_secret"):
            with patch("code_atlas.api.v1.billing.STRIPE_SECRET_KEY", "sk_test_"):
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                from code_atlas.api.v1.billing import router

                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                event = {
                    "type": "customer.subscription.deleted",
                    "data": {
                        "id": "sub_test123",
                        "customer": "cus_test123",
                    },
                }
                response = client.post("/billing/webhook", json=event)
                assert response.status_code == 200

    def test_webhook_handles_payment_failed(self):
        """Test handling invoice.payment_failed event."""
        with patch("code_atlas.api.v1.billing.STRIPE_WEBHOOK_SECRET", "test_secret"):
            with patch("code_atlas.api.v1.billing.STRIPE_SECRET_KEY", "sk_test_"):
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                from code_atlas.api.v1.billing import router

                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                event = {
                    "type": "invoice.payment_failed",
                    "data": {
                        "customer": "cus_test123",
                        "attempt_count": 1,
                    },
                }
                response = client.post("/billing/webhook", json=event)
                assert response.status_code == 200


class TestSubscriptionStatus:
    """Tests for GET /billing/subscription/{key_prefix}."""

    def test_get_subscription_default_tier(self):
        """Test default subscription is Free tier."""
        with patch("code_atlas.usage_tracker.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_hourly_usage.return_value = 5

            from fastapi import FastAPI
            from fastapi.testclient import TestClient

            from code_atlas.api.v1.billing import _require_admin_key, router

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[_require_admin_key] = lambda: "test-admin-key"
            client = TestClient(app)

            response = client.get("/billing/subscription/test-key")
            assert response.status_code == 200
            data = response.json()
            assert data["tier"] == "free"
            assert data["requests_limit"] == 10
            assert data["requests_used"] == 5
            app.dependency_overrides.clear()


class TestTierPricing:
    """Tests for tier pricing."""

    def test_free_tier_price(self):
        """Test Free tier is $0."""
        assert _get_tier_price(APITier.FREE) == 0

    def test_pro_tier_price(self):
        """Test Pro tier is $29."""
        assert _get_tier_price(APITier.PRO) == 2900

    def test_team_tier_price(self):
        """Test Team tier is $99."""
        assert _get_tier_price(APITier.TEAM) == 9900
