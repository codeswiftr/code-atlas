"""Tests for the GitHub integration service and API endpoints.

All GitHub API calls are mocked via ``unittest.mock``.  No network access is
required to run this suite.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.main import create_app
from code_atlas.config import AtlasSettings
from code_atlas.integrations.crypto import decrypt_token, encrypt_token
from code_atlas.integrations.github import (
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubTimeoutError,
    _extract_entities_from_text,
)
from code_atlas.integrations.models import (
    GitHubIssue,
    GitHubPR,
    ImportResult,
    RepoImportRequest,
)
from code_atlas.integrations.token_store import TokenStore, reset_token_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_store_singleton():
    """Ensure the token-store singleton is reset between tests."""
    reset_token_store()
    yield
    reset_token_store()


@pytest.fixture()
def in_memory_store() -> TokenStore:
    return TokenStore(db_path=None)  # :memory:


@pytest.fixture()
def settings(tmp_path: Path) -> AtlasSettings:
    return AtlasSettings(
        claude_root=tmp_path,
        api_key_required=False,
        enable_metrics=False,
    )


@pytest.fixture()
def client(settings: AtlasSettings) -> TestClient:
    from code_atlas.api.dependencies import get_settings
    from code_atlas.integrations.token_store import get_token_store

    app = create_app(settings)

    # Use an in-memory store for tests
    test_store = TokenStore(db_path=None)

    def _override_settings():
        return settings

    def _override_store():
        return test_store

    from code_atlas.api.v1.integrations import get_store

    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_store] = _override_store

    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Token encryption round-trip
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    raw = "ghp_TestTokenABCDE12345"
    ciphertext = encrypt_token(raw)
    assert ciphertext != raw, "Ciphertext must differ from plaintext."
    assert decrypt_token(ciphertext) == raw


def test_different_plaintexts_produce_different_ciphertexts():
    c1 = encrypt_token("token-one")
    c2 = encrypt_token("token-two")
    assert c1 != c2


def test_same_plaintext_produces_different_ciphertexts():
    """Nonce randomness means the same input never produces the same output."""
    token = "ghp_SameToken"
    c1 = encrypt_token(token)
    c2 = encrypt_token(token)
    # Different nonces → different ciphertexts
    assert c1 != c2
    # But both decrypt correctly
    assert decrypt_token(c1) == token
    assert decrypt_token(c2) == token


def test_decrypt_malformed_raises_value_error():
    with pytest.raises(ValueError, match="Malformed ciphertext"):
        decrypt_token("!!!not-base64!!!")


# ---------------------------------------------------------------------------
# 2. Token store persistence
# ---------------------------------------------------------------------------


def test_token_store_save_and_retrieve(in_memory_store: TokenStore):
    conn = in_memory_store.save("user-1", "ghp_mytoken", github_login="alice")
    assert conn.user_id == "user-1"
    assert conn.github_login == "alice"

    raw = in_memory_store.get_raw_token("user-1")
    assert raw == "ghp_mytoken"


def test_token_store_overwrite(in_memory_store: TokenStore):
    in_memory_store.save("user-1", "old-token")
    in_memory_store.save("user-1", "new-token", github_login="bob")
    assert in_memory_store.get_raw_token("user-1") == "new-token"


def test_token_store_get_status_connected(in_memory_store: TokenStore):
    in_memory_store.save("user-1", "ghp_tok", github_login="alice")
    status = in_memory_store.get_status("user-1")
    assert status.connected is True
    assert status.github_login == "alice"


def test_token_store_get_status_not_connected(in_memory_store: TokenStore):
    status = in_memory_store.get_status("nonexistent-user")
    assert status.connected is False
    assert status.github_login is None


def test_token_store_delete(in_memory_store: TokenStore):
    in_memory_store.save("user-1", "ghp_tok")
    assert in_memory_store.delete("user-1") is True
    assert in_memory_store.get_raw_token("user-1") is None


# ---------------------------------------------------------------------------
# 3. GitHub client — repo listing (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_repos_success():
    raw_repos = [
        {
            "full_name": "alice/my-repo",
            "description": "A cool repo",
            "language": "Python",
            "stargazers_count": 10,
            "open_issues_count": 2,
            "default_branch": "main",
            "visibility": "public",
            "html_url": "https://github.com/alice/my-repo",
        }
    ]

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = raw_repos
    mock_response.raise_for_status = MagicMock()

    async with GitHubClient("ghp_faketoken") as gh:
        gh._client = AsyncMock()
        gh._client.get = AsyncMock(return_value=mock_response)

        repos = await gh.list_repos()

    assert len(repos) == 1
    assert repos[0].full_name == "alice/my-repo"
    assert repos[0].language == "Python"


# ---------------------------------------------------------------------------
# 4. PR context extraction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_pr_context_extracts_files():
    pr_data = {
        "number": 42,
        "title": "Add authentication module",
        "body": "Updated `auth/service.py` and `auth/models.py`.",
        "state": "open",
        "merged_at": None,
        "user": {"login": "bob"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }
    files_data = [{"filename": "auth/service.py"}, {"filename": "auth/models.py"}]
    comments_data: list = []
    reviews_data: list = []

    mock_responses = [
        _mock_json_response(pr_data),
        _mock_json_response(files_data),
        _mock_json_response(comments_data),
        _mock_json_response(reviews_data),
    ]

    async with GitHubClient("ghp_faketoken") as gh:
        gh._client = AsyncMock()
        gh._client.get = AsyncMock(side_effect=mock_responses)

        pr = await gh.fetch_pr_context("alice", "repo", 42)

    assert pr.number == 42
    assert "auth/service.py" in pr.files_changed
    assert "auth/models.py" in pr.files_changed


@pytest.mark.asyncio
async def test_extract_entities_from_pr_data():
    pr = GitHubPR(
        number=1,
        title="Refactor pipeline",
        body="Modified `src/pipeline.py` and `def process_session` helper.",
        state="open",
        author="alice",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
        files_changed=["src/pipeline.py", "tests/test_pipeline.py"],
        comments=["See also `src/config.py` changes."],
    )

    async with GitHubClient("ghp_faketoken") as gh:
        entities = await gh.extract_entities_from_pr(pr)

    names = {e["name"] for e in entities}
    types_map = {e["name"]: e["type"] for e in entities}

    # Files from files_changed are always included
    assert "src/pipeline.py" in names
    assert "tests/test_pipeline.py" in names
    assert types_map["src/pipeline.py"] == "file"

    # Inline references in body/comments
    assert "src/config.py" in names


# ---------------------------------------------------------------------------
# 5. Entity extraction from text
# ---------------------------------------------------------------------------


def test_extract_entities_finds_file_paths():
    text = 'The fix is in `src/auth/service.py` and "tests/test_auth.py".'
    entities = _extract_entities_from_text(text)
    names = [e["name"] for e in entities]
    assert "src/auth/service.py" in names
    assert "tests/test_auth.py" in names


def test_extract_entities_finds_function_names():
    text = "Refactored `def process_session(path)` and `async def run_pipeline()`."
    entities = _extract_entities_from_text(text)
    func_names = [e["name"] for e in entities if e["type"] == "function"]
    assert "process_session" in func_names
    assert "run_pipeline" in func_names


def test_extract_entities_deduplicates():
    text = "`auth.py` mentioned twice: `auth.py` is the main file."
    entities = _extract_entities_from_text(text)
    names = [e["name"] for e in entities]
    assert names.count("auth.py") == 1


# ---------------------------------------------------------------------------
# 6. Rate-limit handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_raises_after_retries():
    """GitHubClient should raise GitHubRateLimitError after max retries."""
    rate_limit_response = MagicMock()
    rate_limit_response.is_success = False
    rate_limit_response.status_code = 429
    rate_limit_response.headers = {"Retry-After": "0"}
    rate_limit_response.url = "https://api.github.com/user/repos"

    async with GitHubClient("ghp_faketoken", max_retries=2) as gh:
        gh._client = AsyncMock()
        # Every call returns the rate-limit response
        gh._client.get = AsyncMock(return_value=rate_limit_response)

        with pytest.raises(GitHubRateLimitError):
            with patch("asyncio.sleep", new=AsyncMock()):
                await gh.list_repos()


# ---------------------------------------------------------------------------
# 7. Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_token_raises_auth_error():
    unauth_response = MagicMock()
    unauth_response.is_success = False
    unauth_response.status_code = 401
    unauth_response.url = "https://api.github.com/user"

    async with GitHubClient("ghp_invalid") as gh:
        gh._client = AsyncMock()
        gh._client.get = AsyncMock(return_value=unauth_response)

        with pytest.raises(GitHubAuthError):
            await gh.get_authenticated_user()


@pytest.mark.asyncio
async def test_repo_not_found_raises_not_found_error():
    not_found_response = MagicMock()
    not_found_response.is_success = False
    not_found_response.status_code = 404
    not_found_response.url = "https://api.github.com/repos/alice/missing/readme"

    async with GitHubClient("ghp_faketoken") as gh:
        gh._client = AsyncMock()
        gh._client.get = AsyncMock(return_value=not_found_response)

        with pytest.raises(GitHubNotFoundError):
            await gh._get("/repos/alice/missing/readme")


@pytest.mark.asyncio
async def test_api_timeout_raises_timeout_error():
    import httpx

    async with GitHubClient("ghp_faketoken", max_retries=1) as gh:
        gh._client = AsyncMock()
        gh._client.get = AsyncMock(
            side_effect=httpx.TimeoutException("timed out", request=MagicMock())
        )

        with pytest.raises(GitHubTimeoutError):
            with patch("asyncio.sleep", new=AsyncMock()):
                await gh._get("/user")


# ---------------------------------------------------------------------------
# 8. API endpoint integration tests
# ---------------------------------------------------------------------------


def _make_user_response(login: str = "alice") -> dict:
    return {"login": login, "id": 1, "name": "Alice"}


def test_github_status_not_connected(client: TestClient):
    resp = client.get("/api/v1/integrations/github/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False


def test_github_connect_stores_token(client: TestClient):
    user_resp = _mock_json_response(_make_user_response("alice"))

    with patch(
        "code_atlas.api.v1.integrations.GitHubClient.__aenter__",
        new_callable=AsyncMock,
    ) as mock_enter:
        mock_gh = AsyncMock()
        mock_gh.get_authenticated_user = AsyncMock(return_value=_make_user_response())
        mock_enter.return_value = mock_gh

        with patch(
            "code_atlas.api.v1.integrations.GitHubClient.__aexit__",
            new_callable=AsyncMock,
        ):
            resp = client.post(
                "/api/v1/integrations/github/connect",
                json={"access_token": "ghp_realtoken"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["github_login"] == "alice"


def test_github_list_repos_requires_token(client: TestClient):
    """Listing repos without a stored token returns 401."""
    resp = client.get("/api/v1/integrations/github/repos")
    assert resp.status_code == 401


def test_github_import_requires_token(client: TestClient):
    """Importing without a stored token returns 401."""
    resp = client.post(
        "/api/v1/integrations/github/import",
        json={"owner": "alice", "repo": "my-repo"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_json_response(data: object) -> MagicMock:
    """Create a mock httpx Response whose .json() returns *data*."""
    resp = MagicMock()
    resp.is_success = True
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp
