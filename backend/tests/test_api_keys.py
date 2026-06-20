"""Tests for API key management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from code_atlas.auth.api_keys import (
    APIKeyManager,
    get_key_manager,
    reset_key_manager,
)
from code_atlas.schemas.auth import APIKeyScope


@pytest.fixture
def key_manager() -> APIKeyManager:
    """Create a fresh in-memory key manager for each test."""
    return APIKeyManager()


@pytest.fixture
def sample_scopes() -> list[APIKeyScope]:
    """Default scopes for testing."""
    return [APIKeyScope.READ, APIKeyScope.WRITE]


class TestAPIKeyManager:
    """Tests for APIKeyManager class."""

    def test_generate_key_returns_prefixed_key(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Key starts with 'cat_' prefix."""
        raw_key, record = key_manager.generate_key(
            name="Test Key",
            scopes=sample_scopes,
        )

        assert raw_key.startswith("cat_")
        assert len(raw_key) > 10
        assert record.key_prefix.startswith("cat_")

    def test_validate_key_accepts_valid(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Valid keys pass validation."""
        raw_key, _ = key_manager.generate_key(
            name="Test Key",
            scopes=sample_scopes,
        )

        record = key_manager.validate_key(raw_key)
        assert record is not None
        assert record.name == "Test Key"
        assert record.scopes == sample_scopes

    def test_validate_key_rejects_invalid(self, key_manager: APIKeyManager) -> None:
        """Invalid keys return None."""
        assert key_manager.validate_key("invalid-key") is None
        assert key_manager.validate_key("cat_invalid") is None
        assert key_manager.validate_key("") is None

    def test_validate_key_rejects_expired(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Expired keys fail validation."""
        # Create key that expires immediately
        raw_key, record = key_manager.generate_key(
            name="Expiring Key",
            scopes=sample_scopes,
            expires_in_days=0,  # Will set to None, so let's test differently
        )

        # Manually expire the key
        conn = key_manager._get_connection()
        past_date = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()
        conn.execute(
            "UPDATE api_keys SET expires_at = ? WHERE key_id = ?",
            (past_date, record.key_id),
        )
        conn.commit()

        # Validation should fail
        assert key_manager.validate_key(raw_key) is None

    def test_revoke_key_invalidates_immediately(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Revoked keys fail validation."""
        raw_key, record = key_manager.generate_key(
            name="Revocable Key",
            scopes=sample_scopes,
        )

        # Verify key works before revocation
        assert key_manager.validate_key(raw_key) is not None

        # Revoke
        success = key_manager.revoke_key(record.key_id)
        assert success is True

        # Verify key fails after revocation
        assert key_manager.validate_key(raw_key) is None

    def test_scopes_enforced_correctly(self, key_manager: APIKeyManager) -> None:
        """Scope checks work correctly."""
        # Create key with read-only scope
        raw_key, record = key_manager.generate_key(
            name="Read Only Key",
            scopes=[APIKeyScope.READ],
        )

        # Read scope should pass
        assert key_manager.has_scope(record, APIKeyScope.READ) is True

        # Write scope should fail
        assert key_manager.has_scope(record, APIKeyScope.WRITE) is False

        # Admin scope should fail
        assert key_manager.has_scope(record, APIKeyScope.ADMIN) is False

    def test_admin_scope_grants_all(self, key_manager: APIKeyManager) -> None:
        """Admin scope grants access to everything."""
        _, record = key_manager.generate_key(
            name="Admin Key",
            scopes=[APIKeyScope.ADMIN],
        )

        assert key_manager.has_scope(record, APIKeyScope.READ) is True
        assert key_manager.has_scope(record, APIKeyScope.WRITE) is True
        assert key_manager.has_scope(record, APIKeyScope.PROCESS) is True
        assert key_manager.has_scope(record, APIKeyScope.ADMIN) is True

    def test_usage_tracking_increments(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Each request increments count."""
        _, record = key_manager.generate_key(
            name="Tracked Key",
            scopes=sample_scopes,
        )

        # Initial count is 0
        assert record.request_count == 0

        # Record usage
        key_manager.record_usage(record.key_id)
        key_manager.record_usage(record.key_id)
        key_manager.record_usage(record.key_id)

        # Check updated count
        updated = key_manager.get_key(record.key_id)
        assert updated is not None
        assert updated.request_count == 3
        assert updated.last_used_at is not None

    def test_list_keys_excludes_revoked_by_default(
        self, key_manager: APIKeyManager, sample_scopes: list[APIKeyScope]
    ) -> None:
        """Revoked hidden unless requested."""
        # Create active key
        _, active_record = key_manager.generate_key(
            name="Active Key",
            scopes=sample_scopes,
        )

        # Create and revoke another key
        _, revoked_record = key_manager.generate_key(
            name="Revoked Key",
            scopes=sample_scopes,
        )
        key_manager.revoke_key(revoked_record.key_id)

        # Default listing excludes revoked
        active_keys = key_manager.list_keys()
        assert len(active_keys) == 1
        assert active_keys[0].key_id == active_record.key_id

        # Include revoked shows both
        all_keys = key_manager.list_keys(include_revoked=True)
        assert len(all_keys) == 2

    def test_key_persists_to_file(self, tmp_path: Path) -> None:
        """Keys persist across manager instances."""
        db_path = tmp_path / "keys.db"

        # Create manager and key
        manager1 = APIKeyManager(db_path)
        raw_key, _ = manager1.generate_key(
            name="Persistent Key",
            scopes=[APIKeyScope.READ],
        )
        manager1.close()

        # New manager should find the key
        manager2 = APIKeyManager(db_path)
        record = manager2.validate_key(raw_key)
        assert record is not None
        assert record.name == "Persistent Key"
        manager2.close()

    def test_global_singleton(self) -> None:
        """Global key manager is singleton."""
        reset_key_manager()

        manager1 = get_key_manager()
        manager2 = get_key_manager()

        assert manager1 is manager2

        reset_key_manager()


class TestAdminAPIEndpoints:
    """Tests for admin API endpoints."""

    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        """Create test client with API key auth disabled."""
        # Disable API key requirement for testing
        monkeypatch.setenv("CODE_ATLAS_API_KEY_REQUIRED", "false")

        # Reset any existing key manager
        reset_key_manager()

        from code_atlas.api.main import create_app
        from code_atlas.config import AtlasSettings

        settings = AtlasSettings()
        app = create_app(settings)
        return TestClient(app)

    def test_admin_create_key_endpoint(self, client: TestClient) -> None:
        """API returns raw key once."""
        response = client.post(
            "/api/v1/admin/keys",
            json={
                "name": "Test API Key",
                "scopes": ["read", "write"],
                "expires_in_days": 30,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "raw_key" in data
        assert data["raw_key"].startswith("cat_")
        assert data["name"] == "Test API Key"
        assert "read" in data["scopes"]
        assert "write" in data["scopes"]

    def test_admin_list_keys_hides_raw_values(self, client: TestClient) -> None:
        """Response has no raw keys."""
        # Create a key first
        client.post(
            "/api/v1/admin/keys",
            json={"name": "Listed Key", "scopes": ["read"]},
        )

        response = client.get("/api/v1/admin/keys")
        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 1
        for key_info in data:
            assert "raw_key" not in key_info
            assert "key_hash" not in key_info
            assert "key_prefix" in key_info

    def test_admin_revoke_key_endpoint(self, client: TestClient) -> None:
        """Key can be revoked via API."""
        # Create key
        create_response = client.post(
            "/api/v1/admin/keys",
            json={"name": "Revocable Key", "scopes": ["read"]},
        )
        key_id = create_response.json()["key_id"]

        # Revoke
        revoke_response = client.delete(f"/api/v1/admin/keys/{key_id}")
        assert revoke_response.status_code == 204

        # Verify revoked
        list_response = client.get("/api/v1/admin/keys")
        key_ids = [k["key_id"] for k in list_response.json()]
        assert key_id not in key_ids

    def test_admin_get_key_usage(self, client: TestClient) -> None:
        """Usage stats available via API."""
        # Create key
        create_response = client.post(
            "/api/v1/admin/keys",
            json={"name": "Usage Key", "scopes": ["read"]},
        )
        key_id = create_response.json()["key_id"]

        # Get usage
        usage_response = client.get(f"/api/v1/admin/keys/{key_id}/usage")
        assert usage_response.status_code == 200
        data = usage_response.json()

        assert data["key_id"] == key_id
        assert "request_count" in data
        assert "last_used_at" in data

    def test_admin_revoke_nonexistent_returns_404(self, client: TestClient) -> None:
        """Revoking nonexistent key returns 404."""
        response = client.delete("/api/v1/admin/keys/nonexistent-key")
        assert response.status_code == 404


@pytest.fixture(autouse=True)
def cleanup_key_manager():
    """Clean up global key manager after each test."""
    yield
    reset_key_manager()
