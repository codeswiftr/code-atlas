"""Session-related API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .common import BaseResponse


class JobStatus(str, Enum):
    """Processing job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionInfo(BaseModel):
    """Information about a discovered session."""

    path: str
    filename: str
    size_bytes: int
    modified_at: datetime
    project_name: str | None = None
    message_count: int | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "/Users/user/.claude/projects/my-project/session-abc123.jsonl",
                "filename": "session-abc123.jsonl",
                "size_bytes": 45678,
                "modified_at": "2025-01-15T10:30:00Z",
                "project_name": "my-project",
                "message_count": 42,
            }
        }
    }


class SessionDiscoveryRequest(BaseModel):
    """Request to discover available sessions."""

    root_path: str | None = Field(
        default=None,
        description="Root path to search for sessions. Defaults to ~/.claude/projects/",
    )
    project_filter: str | None = Field(
        default=None,
        description="Filter sessions by project name (glob pattern)",
    )
    min_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Minimum session file size in bytes",
    )
    max_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Maximum session file size in bytes",
    )
    modified_after: datetime | None = Field(
        default=None,
        description="Only include sessions modified after this timestamp",
    )
    modified_before: datetime | None = Field(
        default=None,
        description="Only include sessions modified before this timestamp",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of sessions to return",
    )


class SessionDiscoveryResponse(BaseResponse):
    """Response containing discovered sessions."""

    sessions: list[SessionInfo]
    total_found: int
    search_path: str


class SessionProcessRequest(BaseModel):
    """Request to process one or more sessions."""

    session_paths: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of session file paths to process",
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM for insight extraction (vs heuristics only)",
    )
    dry_run: bool = Field(
        default=False,
        description="Validate without writing to graph database",
    )
    max_cost_per_session: float = Field(
        default=0.02,
        ge=0,
        le=1.0,
        description="Maximum cost per session in USD",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_paths": [
                    "/Users/user/.claude/projects/my-project/session-abc123.jsonl"
                ],
                "use_llm": True,
                "dry_run": False,
                "max_cost_per_session": 0.02,
            }
        }
    }


class ProcessingJob(BaseModel):
    """Information about a processing job."""

    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_sessions: int
    processed_sessions: int
    failed_sessions: int
    current_session: str | None = None
    error_message: str | None = None
    stats: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job-abc123",
                "status": "running",
                "created_at": "2025-01-15T10:30:00Z",
                "started_at": "2025-01-15T10:30:01Z",
                "completed_at": None,
                "total_sessions": 10,
                "processed_sessions": 3,
                "failed_sessions": 0,
                "current_session": "session-def456.jsonl",
                "error_message": None,
                "stats": {
                    "entities_created": 45,
                    "relationships_created": 120,
                    "total_cost_usd": 0.015,
                },
            }
        }
    }


class SessionProcessResponse(BaseResponse):
    """Response after submitting sessions for processing."""

    job: ProcessingJob


class ProcessingStatsResponse(BaseResponse):
    """Response with processing statistics."""

    total_jobs: int
    total_sessions_processed: int
    total_entities_created: int
    total_relationships_created: int
    total_cost_usd: float
    avg_processing_time_seconds: float
    success_rate: float
