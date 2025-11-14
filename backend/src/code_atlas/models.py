"""Typed models shared across the Code Atlas backend."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Lightweight description of a Claude Code session file."""

    path: Path
    session_id: str
    project: str
    size_bytes: int
    modified_at: datetime


class SessionMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant", "system", "tool"]
    text: str
    timestamp: datetime | None = None
    tool_name: str | None = None
    files: list[str] = Field(default_factory=list)
    token_count: int | None = None


class ParsedSession(BaseModel):
    metadata: SessionMetadata
    messages: list[SessionMessage]
    total_tokens: int
    referenced_files: list[str]
    duration_seconds: float | None = None
