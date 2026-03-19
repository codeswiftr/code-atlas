"""Pydantic models for GitHub/GitLab integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GitHubConnection(BaseModel):
    """Stored connection record for a GitHub OAuth token.

    The access_token field holds the encrypted ciphertext; the raw token
    is never persisted. Use :func:`~code_atlas.integrations.crypto.encrypt_token`
    and :func:`~code_atlas.integrations.crypto.decrypt_token` to round-trip.
    """

    user_id: str = Field(description="Opaque user/API-key identifier.")
    access_token: str = Field(
        description="Encrypted OAuth token (ciphertext, base64-encoded)."
    )
    connected_at: datetime = Field(
        description="UTC timestamp when the connection was established."
    )
    github_login: str | None = Field(
        default=None,
        description="GitHub username, populated after first successful API call.",
    )


class RepoImportRequest(BaseModel):
    """Request body for importing a GitHub repository into the knowledge graph."""

    owner: str = Field(description="Repository owner (user or org).")
    repo: str = Field(description="Repository name (without owner prefix).")
    import_prs: bool = Field(
        default=True,
        description="Include recent pull requests (up to 20).",
    )
    import_issues: bool = Field(
        default=True,
        description="Include open issues (up to 20).",
    )
    import_readme: bool = Field(
        default=True,
        description="Include the default-branch README.",
    )
    max_prs: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of pull requests to import.",
    )
    max_issues: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of issues to import.",
    )


class ImportResult(BaseModel):
    """Summary returned after a successful repository import."""

    owner: str
    repo: str
    entities_found: int = Field(
        description="Total code entities extracted (files, functions, concepts)."
    )
    relationships_created: int = Field(
        description="Graph relationships written during import.",
    )
    duration_ms: int = Field(description="Wall-clock time for the full import.")
    prs_imported: int = Field(default=0)
    issues_imported: int = Field(default=0)
    readme_imported: bool = Field(default=False)


class GitHubRepo(BaseModel):
    """Lightweight representation of a GitHub repository listing."""

    full_name: str = Field(description="'owner/repo' slug.")
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    open_issues_count: int = 0
    default_branch: str = "main"
    visibility: Literal["public", "private", "internal"] = "public"
    html_url: str


class GitHubPR(BaseModel):
    """Pull request context extracted from the GitHub API."""

    number: int
    title: str
    body: str | None = None
    state: Literal["open", "closed", "merged"]
    author: str
    created_at: datetime
    updated_at: datetime
    files_changed: list[str] = Field(default_factory=list)
    comments: list[str] = Field(
        default_factory=list,
        description="Concatenated comment bodies (review + issue comments).",
    )


class GitHubIssue(BaseModel):
    """Issue context extracted from the GitHub API."""

    number: int
    title: str
    body: str | None = None
    state: Literal["open", "closed"]
    author: str
    labels: list[str] = Field(default_factory=list)
    created_at: datetime


class RepoContext(BaseModel):
    """Aggregated context fetched for a single repository."""

    owner: str
    repo: str
    readme: str | None = None
    prs: list[GitHubPR] = Field(default_factory=list)
    issues: list[GitHubIssue] = Field(default_factory=list)


class GitHubStatus(BaseModel):
    """Connection status for the GitHub integration."""

    connected: bool
    github_login: str | None = None
    connected_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
