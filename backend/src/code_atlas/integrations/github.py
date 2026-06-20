"""GitHub integration service for Code Atlas.

Fetches repository context (README, PRs, issues) and extracts code entities
that can be ingested into the knowledge graph.

All HTTP calls use ``httpx`` in async mode.  Rate-limit errors (HTTP 403/429)
are retried with exponential back-off up to ``max_retries`` attempts.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import httpx

from ..logging_config import get_logger
from .models import GitHubIssue, GitHubPR, GitHubRepo, RepoContext

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"
_DEFAULT_TIMEOUT = 30.0  # seconds
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt


class GitHubAuthError(Exception):
    """Raised when the OAuth token is missing, invalid, or revoked."""


class GitHubNotFoundError(Exception):
    """Raised when the requested resource does not exist on GitHub."""


class GitHubRateLimitError(Exception):
    """Raised when the GitHub API rate limit has been exhausted."""


class GitHubTimeoutError(Exception):
    """Raised when the GitHub API does not respond within the timeout."""


# ---------------------------------------------------------------------------
# Entity extraction helpers
# ---------------------------------------------------------------------------

# Patterns that look like file-system paths or qualified names in PR text
_FILE_PATH_RE = re.compile(r"[`'\"]([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,6})[`'\"]")
_FUNC_NAME_RE = re.compile(r"\b(def |function |func |async def )([a-zA-Z_][a-zA-Z0-9_]{2,})\s*\(")


def _extract_entities_from_text(text: str) -> list[dict[str, str]]:
    """Extract code entity hints from free-form text.

    Returns a list of ``{"name": ..., "type": ...}`` dicts.
    """
    entities: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in _FILE_PATH_RE.finditer(text):
        name = match.group(1)
        if name not in seen:
            entities.append({"name": name, "type": "file"})
            seen.add(name)

    for match in _FUNC_NAME_RE.finditer(text):
        name = match.group(2)
        if name not in seen:
            entities.append({"name": name, "type": "function"})
            seen.add(name)

    return entities


# ---------------------------------------------------------------------------
# GitHub API client
# ---------------------------------------------------------------------------


class GitHubClient:
    """Async client for the GitHub REST API v3.

    Args:
        token: OAuth personal-access token or fine-grained token.
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries on rate-limit or transient errors.
    """

    def __init__(
        self,
        token: str,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        if not token:
            raise GitHubAuthError("GitHub OAuth token must not be empty.")
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> GitHubClient:
        self._client = httpx.AsyncClient(
            base_url=_GITHUB_API,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Low-level request helper with retry
    # ------------------------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GitHubClient must be used as an async context manager.")
        return self._client

    async def _get(self, path: str, **params: Any) -> Any:
        """Issue a GET request, retrying on rate-limit responses.

        Args:
            path: API path relative to ``https://api.github.com``.
            **params: Query parameters forwarded to httpx.

        Returns:
            Decoded JSON body.

        Raises:
            GitHubAuthError: 401 Unauthorized.
            GitHubNotFoundError: 404 Not Found.
            GitHubRateLimitError: 403/429 after all retries exhausted.
            GitHubTimeoutError: Request timed out after all retries exhausted.
        """
        client = self._ensure_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = await client.get(path, params=params or None)
                self._handle_status(response)
                return response.json()
            except GitHubRateLimitError as exc:
                last_exc = exc
                retry_after = self._parse_retry_after(exc)
                delay = retry_after or (_RETRY_BASE_DELAY * (2**attempt))
                logger.warning(
                    "GitHub rate limit hit — retrying",
                    path=path,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            except httpx.TimeoutException:
                last_exc = GitHubTimeoutError(f"Request to {path} timed out after {self._timeout}s")
                delay = _RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "GitHub API timeout — retrying",
                    path=path,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)

        raise last_exc or GitHubRateLimitError("Rate limit exhausted; all retries failed.")

    # ------------------------------------------------------------------
    # Status handling
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_status(response: httpx.Response) -> None:
        """Raise typed exceptions for non-2xx responses."""
        if response.is_success:
            return

        code = response.status_code
        if code == 401:
            raise GitHubAuthError(
                "GitHub API returned 401 Unauthorized. "
                "Check that your OAuth token is valid and has not been revoked."
            )
        if code == 404:
            raise GitHubNotFoundError(f"GitHub resource not found: {response.url}")
        if code in (403, 429):
            raise GitHubRateLimitError(
                f"GitHub rate limit exceeded (HTTP {code}). "
                f"Retry-After: {response.headers.get('Retry-After', 'unknown')}s. "
                "To fix: wait for the rate-limit window to reset or use a token "
                "with higher rate-limit quota."
            )
        response.raise_for_status()

    @staticmethod
    def _parse_retry_after(exc: GitHubRateLimitError) -> float | None:
        """Extract numeric seconds from a rate-limit error message."""
        match = re.search(r"Retry-After: (\d+)", str(exc))
        if match:
            return float(match.group(1))
        return None

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_authenticated_user(self) -> dict[str, Any]:
        """Return the authenticated user's profile.

        Raises:
            GitHubAuthError: If the token is invalid.
        """
        return await self._get("/user")

    async def list_repos(
        self,
        per_page: int = 30,
        sort: str = "updated",
    ) -> list[GitHubRepo]:
        """List repositories accessible to the authenticated user.

        Args:
            per_page: Number of repos per page (GitHub max is 100).
            sort: Sort field — ``updated``, ``created``, ``pushed``, ``full_name``.

        Returns:
            List of :class:`GitHubRepo` instances.
        """
        data = await self._get(
            "/user/repos",
            per_page=per_page,
            sort=sort,
            affiliation="owner,collaborator,organization_member",
        )
        repos = []
        for raw in data:
            visibility: str = raw.get("visibility", "public")
            if visibility not in ("public", "private", "internal"):
                visibility = "public"
            repos.append(
                GitHubRepo(
                    full_name=raw["full_name"],
                    description=raw.get("description"),
                    language=raw.get("language"),
                    stargazers_count=raw.get("stargazers_count", 0),
                    open_issues_count=raw.get("open_issues_count", 0),
                    default_branch=raw.get("default_branch", "main"),
                    visibility=visibility,  # type: ignore[arg-type]
                    html_url=raw["html_url"],
                )
            )
        return repos

    async def fetch_repo_context(
        self,
        owner: str,
        repo: str,
        max_prs: int = 20,
        max_issues: int = 20,
        include_readme: bool = True,
        include_prs: bool = True,
        include_issues: bool = True,
    ) -> RepoContext:
        """Fetch aggregated context for a repository.

        Fetches README, recent PRs, and open issues in parallel where possible.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            max_prs: Maximum number of pull requests to fetch.
            max_issues: Maximum number of issues to fetch.
            include_readme: Whether to fetch the README content.
            include_prs: Whether to fetch pull requests.
            include_issues: Whether to fetch open issues.

        Returns:
            :class:`RepoContext` with all requested data.

        Raises:
            GitHubNotFoundError: If the repository does not exist.
        """
        slug = f"{owner}/{repo}"
        logger.info("Fetching repo context", slug=slug)

        readme: str | None = None
        prs: list[GitHubPR] = []
        issues: list[GitHubIssue] = []

        # Gather README and issue/PR lists concurrently
        tasks: list[Any] = []
        task_labels: list[str] = []

        if include_readme:
            tasks.append(self._fetch_readme(owner, repo))
            task_labels.append("readme")
        if include_prs:
            tasks.append(self._fetch_pull_requests(owner, repo, max_prs))
            task_labels.append("prs")
        if include_issues:
            tasks.append(self._fetch_issues(owner, repo, max_issues))
            task_labels.append("issues")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for label, result in zip(task_labels, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to fetch repo context component",
                    slug=slug,
                    component=label,
                    error=str(result),
                )
                continue
            if label == "readme":
                readme = result  # type: ignore[assignment]
            elif label == "prs":
                prs = result  # type: ignore[assignment]
            elif label == "issues":
                issues = result  # type: ignore[assignment]

        logger.info(
            "Repo context fetched",
            slug=slug,
            readme_chars=len(readme) if readme else 0,
            pr_count=len(prs),
            issue_count=len(issues),
        )
        return RepoContext(owner=owner, repo=repo, readme=readme, prs=prs, issues=issues)

    async def fetch_pr_context(self, owner: str, repo: str, pr_number: int) -> GitHubPR:
        """Fetch full context for a single pull request.

        Fetches PR metadata, file list, and comments concurrently.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            :class:`GitHubPR` with enriched context.
        """
        slug = f"{owner}/{repo}#{pr_number}"
        logger.info("Fetching PR context", slug=slug)

        pr_path = f"/repos/{owner}/{repo}/pulls/{pr_number}"
        files_path = f"{pr_path}/files"
        comments_path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        reviews_path = f"{pr_path}/reviews"

        pr_data, files_data, comments_data, reviews_data = await asyncio.gather(
            self._get(pr_path),
            self._get(files_path, per_page=100),
            self._get(comments_path, per_page=100),
            self._get(reviews_path, per_page=100),
            return_exceptions=True,
        )

        # Build file list
        files_changed: list[str] = []
        if not isinstance(files_data, Exception):
            files_changed = [f["filename"] for f in files_data if "filename" in f]

        # Collect comment bodies
        comments: list[str] = []
        if not isinstance(comments_data, Exception):
            comments += [c["body"] for c in comments_data if c.get("body")]
        if not isinstance(reviews_data, Exception):
            comments += [r["body"] for r in reviews_data if r.get("body")]

        # Fall back gracefully when the main PR call failed
        if isinstance(pr_data, Exception):
            raise pr_data

        state_raw = pr_data.get("state", "open")
        if pr_data.get("merged_at"):
            state_raw = "merged"
        if state_raw not in ("open", "closed", "merged"):
            state_raw = "open"

        return GitHubPR(
            number=pr_data["number"],
            title=pr_data["title"],
            body=pr_data.get("body"),
            state=state_raw,  # type: ignore[arg-type]
            author=pr_data.get("user", {}).get("login", "unknown"),
            created_at=datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(pr_data["updated_at"].replace("Z", "+00:00")),
            files_changed=files_changed,
            comments=comments,
        )

    async def extract_entities_from_pr(self, pr_data: GitHubPR) -> list[dict[str, str]]:
        """Extract code entities from a pull request's textual content.

        Scans the PR title, description, and comments for file paths and
        function names.  Also promotes every changed file to an entity.

        Args:
            pr_data: A :class:`GitHubPR` instance.

        Returns:
            List of ``{"name": ..., "type": ...}`` dicts, deduplicated.
        """
        seen: set[str] = set()
        entities: list[dict[str, str]] = []

        def _add(name: str, etype: str) -> None:
            if name not in seen:
                entities.append({"name": name, "type": etype})
                seen.add(name)

        # Every file that changed is definitely a file entity
        for path in pr_data.files_changed:
            _add(path, "file")

        # Mine text for additional references
        sources = [pr_data.title or "", pr_data.body or ""] + list(pr_data.comments)
        for text in sources:
            for entity in _extract_entities_from_text(text):
                _add(entity["name"], entity["type"])

        logger.debug(
            "Entities extracted from PR",
            pr_number=pr_data.number,
            total=len(entities),
        )
        return entities

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_readme(self, owner: str, repo: str) -> str | None:
        """Fetch and decode the repository README."""
        try:
            data = await self._get(f"/repos/{owner}/{repo}/readme")
        except GitHubNotFoundError:
            return None

        import base64 as _base64

        content = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and content:
            return _base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
        return content or None

    async def _fetch_pull_requests(self, owner: str, repo: str, max_prs: int) -> list[GitHubPR]:
        """Fetch up to *max_prs* recent pull requests (open + closed)."""
        data = await self._get(
            f"/repos/{owner}/{repo}/pulls",
            state="all",
            sort="updated",
            direction="desc",
            per_page=min(max_prs, 100),
        )
        prs = []
        for raw in data[:max_prs]:
            state_raw = raw.get("state", "open")
            if raw.get("merged_at"):
                state_raw = "merged"
            if state_raw not in ("open", "closed", "merged"):
                state_raw = "open"
            prs.append(
                GitHubPR(
                    number=raw["number"],
                    title=raw["title"],
                    body=raw.get("body"),
                    state=state_raw,  # type: ignore[arg-type]
                    author=raw.get("user", {}).get("login", "unknown"),
                    created_at=datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00")),
                )
            )
        return prs

    async def _fetch_issues(self, owner: str, repo: str, max_issues: int) -> list[GitHubIssue]:
        """Fetch up to *max_issues* open issues."""
        data = await self._get(
            f"/repos/{owner}/{repo}/issues",
            state="open",
            sort="updated",
            direction="desc",
            per_page=min(max_issues, 100),
        )
        issues = []
        for raw in data[:max_issues]:
            # GitHub returns PRs in the issues endpoint; filter them out
            if raw.get("pull_request"):
                continue
            labels = [lbl["name"] for lbl in raw.get("labels", []) if "name" in lbl]
            state_raw = raw.get("state", "open")
            if state_raw not in ("open", "closed"):
                state_raw = "open"
            issues.append(
                GitHubIssue(
                    number=raw["number"],
                    title=raw["title"],
                    body=raw.get("body"),
                    state=state_raw,  # type: ignore[arg-type]
                    author=raw.get("user", {}).get("login", "unknown"),
                    labels=labels,
                    created_at=datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00")),
                )
            )
        return issues
