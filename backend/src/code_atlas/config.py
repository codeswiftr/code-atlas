"""Runtime configuration for Code Atlas backend."""

from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Python 3.11+ includes tomllib (required version)


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AtlasSettings(BaseSettings):
    """Environment-driven settings with safe defaults."""

    # Environment detection
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment: development, staging, or production.",
        alias="CODE_ATLAS_ENV",
    )

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
    # LLM provider settings
    llm_provider: str = Field(
        default="anthropic",
        description="LLM provider to use: 'anthropic' or 'openrouter'.",
        alias="CODE_ATLAS_LLM_PROVIDER",
    )
    openrouter_api_key: str | None = Field(
        default=None,
        description="OpenRouter API key (from OPENROUTER_API_KEY env var).",
    )
    openrouter_model: str | None = Field(
        default=None,
        description="OpenRouter model to use (from OPENROUTER_MODEL env var).",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL.",
        alias="CODE_ATLAS_OPENROUTER_BASE_URL",
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
    # Monitoring settings
    enable_metrics: bool = Field(
        default=False,
        description="Enable Prometheus metrics collection and HTTP server.",
        alias="CODE_ATLAS_ENABLE_METRICS",
    )
    metrics_host: str = Field(
        default="0.0.0.0",
        description="Host address for metrics HTTP server.",
        alias="CODE_ATLAS_METRICS_HOST",
    )
    metrics_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for metrics HTTP server.",
        alias="CODE_ATLAS_METRICS_PORT",
    )
    metrics_path: str = Field(
        default="/metrics",
        description="Path for Prometheus metrics endpoint.",
        alias="CODE_ATLAS_METRICS_PATH",
    )
    health_path: str = Field(
        default="/health",
        description="Path for health check endpoint.",
        alias="CODE_ATLAS_HEALTH_PATH",
    )
    status_path: str = Field(
        default="/status",
        description="Path for detailed status endpoint.",
        alias="CODE_ATLAS_STATUS_PATH",
    )
    metrics_collection_interval: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Interval in seconds for collecting system metrics.",
        alias="CODE_ATLAS_METRICS_INTERVAL",
    )
    prometheus_namespace: str = Field(
        default="code_atlas",
        description="Prometheus metrics namespace prefix.",
        alias="CODE_ATLAS_PROMETHEUS_NAMESPACE",
    )
    # API settings
    api_key_required: bool = Field(
        default=False,
        description="Require API key for all API endpoints.",
        alias="CODE_ATLAS_API_KEY_REQUIRED",
    )
    admin_api_key: str | None = Field(
        default=None,
        description="Admin API key for full access.",
        alias="CODE_ATLAS_ADMIN_API_KEY",
    )
    cors_origins: list[str] = Field(
        default=["https://app.codeswiftr.com"],
        description=(
            "Allowed CORS origins for production. "
            "Set CODE_ATLAS_CORS_ORIGINS as a comma-separated list of origins. "
            "In development the app uses a localhost regex instead of this list. "
            "Example: https://app.codeswiftr.com,https://www.codeswiftr.com"
        ),
        alias="CODE_ATLAS_CORS_ORIGINS",
    )
    rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Rate limit for standard API keys (requests per minute).",
        alias="CODE_ATLAS_RATE_LIMIT",
    )
    admin_rate_limit_per_minute: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Rate limit for admin API keys (requests per minute).",
        alias="CODE_ATLAS_ADMIN_RATE_LIMIT",
    )
    # Graph database settings
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis/FalkorDB connection URL.",
        alias="CODE_ATLAS_REDIS_URL",
    )
    graph_name: str = Field(
        default="code_atlas",
        description="Name of the graph in FalkorDB.",
        alias="CODE_ATLAS_GRAPH_NAME",
    )
    # Graph backend selection
    graph_backend: str = Field(
        default="auto",
        description=(
            "Graph store backend to use. "
            "'sqlite' — always use SQLite (no Redis needed, deploy anywhere); "
            "'falkordb' — always use FalkorDB (requires redis_url / falkordb_url); "
            "'auto' — use FalkorDB when falkordb_url is set, else SQLite."
        ),
        alias="GRAPH_BACKEND",
    )
    falkordb_url: str | None = Field(
        default=None,
        description=(
            "Explicit FalkorDB connection URL. "
            "When set and graph_backend='auto', FalkorDB is selected. "
            "Falls back to redis_url when this is unset."
        ),
        alias="CODE_ATLAS_FALKORDB_URL",
    )
    sqlite_graph_path: str | None = Field(
        default=None,
        description=(
            "File-system path for the SQLite graph database. "
            "Defaults to 'graph.db' in the current working directory."
        ),
        alias="CODE_ATLAS_SQLITE_GRAPH_PATH",
    )
    # PostHog Analytics
    posthog_api_key: str | None = Field(
        default=None,
        description="PostHog API key for product analytics.",
        alias="CODE_ATLAS_POSTHOG_API_KEY",
    )
    posthog_host: str = Field(
        default="https://eu.posthog.com",
        description="PostHog host URL.",
        alias="CODE_ATLAS_POSTHOG_HOST",
    )
    # Stripe Billing
    stripe_api_key: str | None = Field(
        default=None,
        description="Stripe API secret key for billing.",
        alias="STRIPE_API_KEY",
    )
    stripe_webhook_secret: str | None = Field(
        default=None,
        description="Stripe webhook signing secret.",
        alias="STRIPE_WEBHOOK_SECRET",
    )
    stripe_price_pro: str | None = Field(
        default=None,
        description="Stripe price ID for Pro tier.",
        alias="STRIPE_PRICE_PRO",
    )
    stripe_price_team: str | None = Field(
        default=None,
        description="Stripe price ID for Team tier.",
        alias="STRIPE_PRICE_TEAM",
    )

    @property
    def session_root(self) -> Path:
        """Alias for claude_root for API consistency."""
        return self.claude_root

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == Environment.STAGING

    @property
    def debug(self) -> bool:
        """Enable debug mode in development only."""
        return self.is_development

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
