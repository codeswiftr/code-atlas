"""Runtime configuration for Code Atlas backend."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Python 3.11+ includes tomllib (required version)
import tomllib


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
    # Database indexing settings
    create_db_indexes: bool = Field(
        default=True,
        description="Create database indexes for optimal query performance.",
        alias="CODE_ATLAS_CREATE_INDEXES",
    )
    db_index_creation_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds for database index creation operations.",
        alias="CODE_ATLAS_INDEX_TIMEOUT",
    )
    verify_indexes: bool = Field(
        default=True,
        description="Verify that database indexes exist after creation.",
        alias="CODE_ATLAS_VERIFY_INDEXES",
    )

    model_config = {
        "env_file": ".env",
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "extra": "allow",
    }

    @classmethod
    def from_toml(cls, path: Path | str) -> AtlasSettings:
        """Load settings from TOML file.

        Args:
            path: Path to .code-atlas.toml file

        Returns:
            AtlasSettings instance with values from TOML

        Raises:
            FileNotFoundError: If config file doesn't exist
            tomllib.TOMLDecodeError: If TOML is malformed
        """
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("rb") as f:
            data = tomllib.load(f)

        # Flatten nested structure: merge all sections into single dict
        flat = {}
        for section, values in data.items():
            if isinstance(values, dict):
                # Expand paths for path-like fields
                for key, value in values.items():
                    path_keys = ("claude_root", "ignore_file", "quarantine_dir")
                    if key in path_keys and isinstance(value, str):
                        flat[key] = str(Path(value).expanduser().resolve())
                    else:
                        flat[key] = value
            else:
                # Handle top-level keys (though our schema uses sections)
                flat[section] = values

        return cls(**flat)

    @classmethod
    def from_toml_with_env_override(cls, path: Path | str) -> AtlasSettings:
        """Load from TOML with environment variable overrides.

        Environment variables take precedence over TOML settings.
        Uses CODE_ATLAS_ prefix for env vars.

        Args:
            path: Path to .code-atlas.toml file

        Returns:
            AtlasSettings with TOML base + env overrides
        """
        # Load base settings from TOML
        toml_settings = cls.from_toml(path)
        toml_dict = toml_settings.model_dump()

        # Load environment variables (Pydantic handles CODE_ATLAS_ prefix via aliases)
        env_settings = cls()
        env_dict = env_settings.model_dump(exclude_unset=True)

        # Merge: env vars override TOML
        merged = {**toml_dict, **env_dict}

        return cls(**merged)


class SessionFilter(BaseModel):
    """Filter knobs for discovery operations."""

    include_projects: set[str] = Field(default_factory=set)
    exclude_projects: set[str] = Field(default_factory=set)
    modified_after: float | None = Field(
        default=None,
        description="Unix timestamp; only newer sessions are returned.",
    )
    limit: int | None = Field(default=None, ge=1)
