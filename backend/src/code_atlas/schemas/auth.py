"""Authentication schemas for API key management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class APIKeyScope(str, Enum):
    """Available API key scopes."""

    READ = "read"  # Read entities, graphs, stats
    WRITE = "write"  # Create/update entities
    PROCESS = "process"  # Submit processing jobs
    ADMIN = "admin"  # Manage API keys, system config


class APITier(str, Enum):
    """Subscription tiers with different rate limits."""

    FREE = "free"  # 10 reports/hour
    PRO = "pro"  # 100 reports/hour
    TEAM = "team"  # 1000 reports/hour


# Tier rate limits (requests per hour)
TIER_RATE_LIMITS: dict[APITier, int] = {
    APITier.FREE: 10,
    APITier.PRO: 100,
    APITier.TEAM: 1000,
}


class APIKeyRecord(BaseModel):
    """API key record stored in database."""

    key_id: str = Field(..., description="Unique key identifier")
    name: str = Field(..., description="Human-readable name for the key")
    key_hash: str = Field(..., description="Hashed API key (never store raw)")
    key_prefix: str = Field(..., description="First 8 chars of key for identification")
    scopes: list[APIKeyScope] = Field(default_factory=list, description="Granted scopes")
    tier: APITier = Field(default=APITier.FREE, description="Subscription tier")
    is_active: bool = Field(default=True, description="Whether key is active")
    created_at: datetime = Field(..., description="When key was created")
    expires_at: datetime | None = Field(None, description="Expiration time (None = never)")
    last_used_at: datetime | None = Field(None, description="Last usage time")
    request_count: int = Field(default=0, description="Total requests made with key")


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Name for the key")
    scopes: list[APIKeyScope] = Field(
        default=[APIKeyScope.READ],
        description="Scopes to grant",
    )
    tier: APITier = Field(default=APITier.FREE, description="Subscription tier")
    expires_in_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Days until expiration (None = never)",
    )


class APIKeyCreateResponse(BaseModel):
    """Response after creating an API key."""

    key_id: str = Field(..., description="Key identifier for management")
    raw_key: str = Field(
        ...,
        description="The API key - SAVE THIS! It will not be shown again.",
    )
    name: str
    scopes: list[APIKeyScope]
    tier: APITier
    expires_at: datetime | None
    message: str = Field(
        default="API key created. Save the raw_key - it cannot be retrieved later."
    )


class APIKeyInfo(BaseModel):
    """API key information (without raw key or hash)."""

    key_id: str
    name: str
    key_prefix: str
    scopes: list[APIKeyScope]
    tier: APITier
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    request_count: int


class APIKeyUsageStats(BaseModel):
    """Usage statistics for an API key."""

    key_id: str
    name: str
    tier: APITier
    request_count: int
    last_used_at: datetime | None
    requests_this_hour: int = Field(default=0, description="Requests in current hour window")
    rate_limit_hourly: int = Field(default=10, description="Hourly rate limit for tier")
    rate_limit_remaining: int = Field(default=0, description="Requests remaining in current window")
