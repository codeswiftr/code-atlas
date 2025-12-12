"""FastAPI dependencies for Code Atlas API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from ..config import AtlasSettings
from ..graph_populator import GraphPopulator
from ..logging_config import get_logger
from ..session_discovery import SessionDiscovery

logger = get_logger(__name__)


@lru_cache
def get_settings() -> AtlasSettings:
    """Get cached settings instance."""
    return AtlasSettings()


def get_session_discovery(
    settings: Annotated[AtlasSettings, Depends(get_settings)]
) -> SessionDiscovery:
    """Get session discovery instance."""
    return SessionDiscovery(settings)


def get_graph_populator(
    settings: Annotated[AtlasSettings, Depends(get_settings)]
) -> GraphPopulator:
    """Get graph populator instance."""
    return GraphPopulator(
        graph_name="code_atlas",
        redis_url="redis://localhost:6379",
        dry_run=False,
        create_indexes=settings.create_db_indexes,
    )


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Annotated[AtlasSettings, Depends(get_settings)] = ...,  # type: ignore[assignment]
) -> str:
    """Verify API key from header.

    For now, this is a simple check. In production, this should
    validate against a database of API keys.
    """
    if not settings.api_key_required:
        return "anonymous"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
        )

    # Check against configured admin key
    # NOTE: For multi-tenant or high-security deployments, consider replacing
    # with database-backed API key management (key rotation, per-key rate limits)
    if x_api_key == settings.admin_api_key:
        return "admin"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )


# Type aliases for dependency injection
Settings = Annotated[AtlasSettings, Depends(get_settings)]
Discovery = Annotated[SessionDiscovery, Depends(get_session_discovery)]
Graph = Annotated[GraphPopulator, Depends(get_graph_populator)]
ApiKey = Annotated[str, Depends(verify_api_key)]
