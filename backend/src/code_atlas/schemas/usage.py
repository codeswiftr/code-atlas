"""Usage tracking schemas for billing."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class UsageEventType(str, Enum):
    """Types of usage events to track."""

    REPORT_GENERATED = "report_generated"  # /sessions/report endpoint called
    API_REQUEST = "api_request"  # General API request
    GRAPH_QUERY = "graph_query"  # Cypher query executed


class UsageEvent(BaseModel):
    """A single usage event record."""

    event_id: str = Field(..., description="Unique event identifier")
    key_id: str = Field(..., description="API key that made the request")
    event_type: UsageEventType = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the event occurred")
    endpoint: str | None = Field(None, description="API endpoint called")
    tokens_used: int = Field(default=0, ge=0, description="LLM tokens consumed (if applicable)")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Cost in USD")
    metadata: dict = Field(default_factory=dict, description="Additional event metadata")


class UsageSummary(BaseModel):
    """Daily/period usage summary for a key."""

    key_id: str
    period_start: datetime
    period_end: datetime
    total_requests: int = Field(default=0, ge=0)
    report_count: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    rate_limit_hits: int = Field(default=0, ge=0)


class UsageReport(BaseModel):
    """Usage report for billing."""

    key_id: str
    key_name: str
    tier: str
    period_start: datetime
    period_end: datetime
    total_requests: int
    report_count: int
    total_cost_usd: float
    rate_limit_remaining: int
