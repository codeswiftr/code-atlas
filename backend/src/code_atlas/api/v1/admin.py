"""Admin API endpoints for system management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.api_keys import APIKeyManager, get_key_manager
from ...logging_config import get_logger
from ...schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyInfo,
    APIKeyUsageStats,
    TIER_RATE_LIMITS,
)
from ..dependencies import ApiKey

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


def get_key_manager_dependency() -> APIKeyManager:
    """Dependency to get APIKeyManager instance."""
    return get_key_manager()


KeyManager = Annotated[APIKeyManager, Depends(get_key_manager_dependency)]


def _record_to_info(record) -> APIKeyInfo:
    """Convert APIKeyRecord to APIKeyInfo (without sensitive data)."""
    return APIKeyInfo(
        key_id=record.key_id,
        name=record.name,
        key_prefix=record.key_prefix,
        scopes=record.scopes,
        tier=record.tier,
        is_active=record.is_active,
        created_at=record.created_at,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        request_count=record.request_count,
    )


@router.post(
    "/keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Generate a new API key. The raw key is only shown once.",
)
async def create_api_key(
    request: APIKeyCreateRequest,
    api_key: ApiKey,
    key_manager: KeyManager,
) -> APIKeyCreateResponse:
    """Generate new API key.

    Returns raw key ONCE - must be saved by caller.
    Requires admin scope or admin API key.
    """
    logger.info(
        "API key creation requested",
        name=request.name,
        scopes=[s.value for s in request.scopes],
        tier=request.tier.value,
    )

    raw_key, record = key_manager.generate_key(
        name=request.name,
        scopes=request.scopes,
        tier=request.tier,
        expires_in_days=request.expires_in_days,
    )

    return APIKeyCreateResponse(
        key_id=record.key_id,
        raw_key=raw_key,
        name=record.name,
        scopes=record.scopes,
        tier=record.tier,
        expires_at=record.expires_at,
    )


@router.get(
    "/keys",
    response_model=list[APIKeyInfo],
    summary="List API keys",
    description="List all active API keys. Does not include raw key values.",
)
async def list_api_keys(
    api_key: ApiKey,
    key_manager: KeyManager,
    include_revoked: bool = False,
) -> list[APIKeyInfo]:
    """List all active API keys.

    Excludes raw key values, shows metadata only.
    """
    records = key_manager.list_keys(include_revoked=include_revoked)
    return [_record_to_info(r) for r in records]


@router.get(
    "/keys/{key_id}",
    response_model=APIKeyInfo,
    summary="Get API key details",
    description="Get details for a specific API key.",
)
async def get_api_key(
    key_id: str,
    api_key: ApiKey,
    key_manager: KeyManager,
) -> APIKeyInfo:
    """Get API key details by ID."""
    record = key_manager.get_key(key_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key not found: {key_id}",
        )
    return _record_to_info(record)


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
    description="Revoke an API key. The key immediately becomes invalid.",
)
async def revoke_api_key(
    key_id: str,
    api_key: ApiKey,
    key_manager: KeyManager,
) -> None:
    """Revoke API key by ID.

    Key immediately becomes invalid.
    """
    success = key_manager.revoke_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key not found: {key_id}",
        )


@router.get(
    "/keys/{key_id}/usage",
    response_model=APIKeyUsageStats,
    summary="Get API key usage",
    description="Get usage statistics for an API key.",
)
async def get_key_usage(
    key_id: str,
    api_key: ApiKey,
    key_manager: KeyManager,
) -> APIKeyUsageStats:
    """Get usage statistics for API key.

    Shows request counts, rate limit status.
    """
    record = key_manager.get_key(key_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key not found: {key_id}",
        )

    # Calculate requests in last 24 hours (simplified - actual implementation
    # would need to track request timestamps)
    # For now, return placeholder based on last_used_at
    requests_today = 0
    if record.last_used_at:
        now = datetime.now(tz=UTC)
        if (now - record.last_used_at) < timedelta(days=1):
            # Estimate based on recent activity
            requests_today = min(record.request_count, 1000)

    return APIKeyUsageStats(
        key_id=record.key_id,
        name=record.name,
        tier=record.tier,
        request_count=record.request_count,
        last_used_at=record.last_used_at,
        requests_this_hour=requests_today,  # Simplified
        rate_limit_hourly=TIER_RATE_LIMITS.get(record.tier, 10),
        rate_limit_remaining=TIER_RATE_LIMITS.get(record.tier, 10) - requests_today,
    )
