"""Runtime configuration for Code Atlas backend."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AtlasSettings(BaseSettings):
    """Environment-driven settings with safe defaults."""

    claude_root: Path = Field(
        default=Path("~/.claude/projects").expanduser(),
        description="Root directory that contains Claude Code project folders.",
        alias="CODE_ATLAS_CLAUDE_ROOT",
    )
    ignore_file: Path | None = Field(
        default=None,
        description="Optional gitignore-style file that lists session paths to skip.",
        alias="CODE_ATLAS_IGNORE_FILE",
    )
    max_session_size_mb: int = Field(
        default=50,
        ge=1,
        description="Skip sessions larger than this size to protect memory usage.",
        alias="CODE_ATLAS_MAX_SESSION_MB",
    )
    max_cost_per_session_usd: float = Field(
        default=0.02,
        ge=0.0,
        description="Maximum allowed cost per session extraction.",
        alias="CODE_ATLAS_MAX_COST_PER_SESSION",
    )
    max_cumulative_cost_usd: float = Field(
        default=10.00,
        ge=0.0,
        description="Maximum total cost for pipeline run.",
        alias="CODE_ATLAS_MAX_CUMULATIVE_COST",
    )

    model_config = {
        "env_file": ".env",
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "extra": "allow",
    }


class SessionFilter(BaseModel):
    """Filter knobs for discovery operations."""

    include_projects: set[str] = Field(default_factory=set)
    exclude_projects: set[str] = Field(default_factory=set)
    modified_after: float | None = Field(
        default=None,
        description="Unix timestamp; only newer sessions are returned.",
    )
    limit: int | None = Field(default=None, ge=1)
