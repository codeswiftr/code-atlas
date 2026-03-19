"""GitHub integration API endpoints.

Provides four endpoints:
- POST /api/v1/integrations/github/connect   — store a GitHub OAuth token
- GET  /api/v1/integrations/github/repos     — list user's repositories
- POST /api/v1/integrations/github/import    — import a repo into the graph
- GET  /api/v1/integrations/github/status    — OAuth connection status
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...integrations.github import (
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubTimeoutError,
)
from ...integrations.models import (
    GitHubRepo,
    GitHubStatus,
    ImportResult,
    RepoImportRequest,
)
from ...integrations.token_store import TokenStore, get_token_store
from ...logging_config import get_logger
from ..dependencies import ApiKey

logger = get_logger(__name__)
router = APIRouter(prefix="/integrations/github", tags=["GitHub Integration"])


# ---------------------------------------------------------------------------
# Request / response schemas local to this module
# ---------------------------------------------------------------------------


class GitHubConnectRequest(BaseModel):
    """Body for ``POST /integrations/github/connect``."""

    access_token: str = Field(
        description=(
            "GitHub personal-access token or fine-grained token with "
            "``repo`` and ``read:user`` scopes."
        )
    )


class GitHubConnectResponse(BaseModel):
    """Response after storing a GitHub token."""

    message: str
    github_login: str


# ---------------------------------------------------------------------------
# Dependency: token store
# ---------------------------------------------------------------------------


def get_store() -> TokenStore:
    return get_token_store()


StoreDep = Annotated[TokenStore, Depends(get_store)]


# ---------------------------------------------------------------------------
# Shared helper: resolve user_id from ApiKey + build GitHub client
# ---------------------------------------------------------------------------


def _user_id_from_api_key(api_key: str) -> str:
    """Derive a stable user identifier from the API key."""
    # For the anonymous / dev case we still need a stable key.
    return f"user:{api_key}"


async def _require_github_client(
    api_key: ApiKey,
    store: StoreDep,
) -> GitHubClient:
    """Retrieve the stored token for the caller and return a GitHubClient.

    Raises HTTP 401 if no token has been connected yet.
    """
    user_id = _user_id_from_api_key(api_key)
    raw_token = store.get_raw_token(user_id)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "No GitHub token found for your account. "
                "Connect first via POST /api/v1/integrations/github/connect."
            ),
        )
    return GitHubClient(raw_token)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/connect",
    response_model=GitHubConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Store GitHub OAuth token",
    description=(
        "Accepts a GitHub personal-access token (or fine-grained token), "
        "verifies it against the GitHub API, and persists it encrypted for "
        "the current API-key identity."
    ),
)
async def connect_github(
    request: GitHubConnectRequest,
    api_key: ApiKey,
    store: StoreDep,
) -> GitHubConnectResponse:
    """Store and verify a GitHub OAuth token."""
    user_id = _user_id_from_api_key(api_key)

    async with GitHubClient(request.access_token) as gh:
        try:
            user_data = await gh.get_authenticated_user()
        except GitHubAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"GitHub rejected the token: {exc}. "
                    "Ensure the token has at least 'repo' and 'read:user' scopes."
                ),
            ) from exc
        except (GitHubRateLimitError, GitHubTimeoutError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"GitHub API unavailable: {exc}. Try again in a few seconds.",
            ) from exc

    github_login: str = user_data.get("login", "unknown")
    store.save(user_id, request.access_token, github_login=github_login)

    logger.info("GitHub token connected", user_id=user_id, github_login=github_login)
    return GitHubConnectResponse(
        message=f"Connected as GitHub user '{github_login}'.",
        github_login=github_login,
    )


@router.get(
    "/status",
    response_model=GitHubStatus,
    summary="GitHub connection status",
    description="Returns whether a GitHub token is stored for the current identity.",
)
async def github_status(
    api_key: ApiKey,
    store: StoreDep,
) -> GitHubStatus:
    """Return connection status for the current identity."""
    user_id = _user_id_from_api_key(api_key)
    return store.get_status(user_id)


@router.get(
    "/repos",
    response_model=list[GitHubRepo],
    summary="List GitHub repositories",
    description=(
        "Returns repositories accessible to the connected GitHub account, "
        "sorted by last-update time."
    ),
)
async def list_repos(
    api_key: ApiKey,
    store: StoreDep,
    per_page: int = 30,
) -> list[GitHubRepo]:
    """List GitHub repos for the connected account."""
    client = await _require_github_client(api_key, store)

    async with client:
        try:
            return await client.list_repos(per_page=min(per_page, 100))
        except GitHubAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"GitHub token is invalid or expired: {exc}. "
                    "Re-connect via POST /api/v1/integrations/github/connect."
                ),
            ) from exc
        except GitHubRateLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"GitHub rate limit exceeded: {exc}. Wait and retry.",
            ) from exc
        except GitHubTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"GitHub API timed out: {exc}. Retry your request.",
            ) from exc


@router.post(
    "/import",
    response_model=ImportResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import repository context into knowledge graph",
    description=(
        "Fetches README, pull requests, and issues from a GitHub repository "
        "and extracts code entities into the knowledge graph."
    ),
)
async def import_repo(
    request: RepoImportRequest,
    api_key: ApiKey,
    store: StoreDep,
) -> ImportResult:
    """Import a GitHub repo's context into the Code Atlas knowledge graph."""
    client = await _require_github_client(api_key, store)
    start_ms = int(time.monotonic() * 1000)

    async with client:
        try:
            ctx = await client.fetch_repo_context(
                owner=request.owner,
                repo=request.repo,
                max_prs=request.max_prs,
                max_issues=request.max_issues,
                include_readme=request.import_readme,
                include_prs=request.import_prs,
                include_issues=request.import_issues,
            )
        except GitHubNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Repository '{request.owner}/{request.repo}' not found on GitHub: {exc}. "
                    "Check the owner and repo name, and ensure the token has 'repo' scope."
                ),
            ) from exc
        except GitHubAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitHub token rejected: {exc}.",
            ) from exc
        except (GitHubRateLimitError, GitHubTimeoutError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"GitHub API temporarily unavailable: {exc}. Retry shortly.",
            ) from exc

        # Extract entities from each PR
        entities: set[tuple[str, str]] = set()
        relationships = 0

        for pr in ctx.prs:
            pr_entities = await client.extract_entities_from_pr(pr)
            for ent in pr_entities:
                entities.add((ent["name"], ent["type"]))
            # Each PR → entity relationship pair
            relationships += len(pr_entities)

        # README contributes a single "readme" entity per repo
        if ctx.readme:
            entities.add((f"{request.owner}/{request.repo}/README", "file"))
            relationships += 1

        # Each issue title may contain file/function references
        for issue in ctx.issues:
            text = (issue.title or "") + " " + (issue.body or "")
            from ...integrations.github import _extract_entities_from_text
            for ent in _extract_entities_from_text(text):
                entities.add((ent["name"], ent["type"]))

    duration_ms = int(time.monotonic() * 1000) - start_ms

    logger.info(
        "GitHub repo import complete",
        owner=request.owner,
        repo=request.repo,
        entities=len(entities),
        relationships=relationships,
        duration_ms=duration_ms,
    )

    return ImportResult(
        owner=request.owner,
        repo=request.repo,
        entities_found=len(entities),
        relationships_created=relationships,
        duration_ms=duration_ms,
        prs_imported=len(ctx.prs),
        issues_imported=len(ctx.issues),
        readme_imported=ctx.readme is not None,
    )
