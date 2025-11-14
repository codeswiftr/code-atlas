"""Stream-oriented parser for Claude session JSONL files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import ParsedSession, SessionMessage, SessionMetadata


class SessionParser:
    """Stream a Claude session JSONL file and convert it to structured messages."""

    def __init__(self, metadata: SessionMetadata):
        self.metadata = metadata

    def parse(self) -> ParsedSession:
        messages: list[SessionMessage] = []
        referenced_files: set[str] = set()
        total_tokens = 0
        first_ts: datetime | None = None
        last_ts: datetime | None = None

        for payload in self._stream_json(self.metadata.path):
            message_payload = payload.get("message") or payload.get("data", {}).get("message")
            if not message_payload:
                continue

            message = self._convert_message(message_payload, payload)
            messages.append(message)

            if message.timestamp:
                first_ts = first_ts or message.timestamp
                last_ts = message.timestamp

            referenced_files.update(message.files)
            if message.token_count:
                total_tokens += message.token_count

        duration = None
        if first_ts and last_ts:
            duration = (last_ts - first_ts).total_seconds()

        return ParsedSession(
            metadata=self.metadata,
            messages=messages,
            total_tokens=total_tokens,
            referenced_files=sorted(referenced_files),
            duration_seconds=duration,
        )

    def _stream_json(self, path: Path) -> Iterable[dict]:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON line in {path}: {exc}") from exc

    def _convert_message(self, message_payload: dict, envelope: dict) -> SessionMessage:
        role = message_payload.get("role", "assistant")
        message_id = message_payload.get("id") or envelope.get("id") or "unknown"
        timestamp = self._parse_timestamp(
            envelope.get("timestamp") or message_payload.get("timestamp")
        )

        text_segments = message_payload.get("content") or []
        text = "\n".join(
            segment.get("text", "")
            for segment in text_segments
            if isinstance(segment, dict) and segment.get("type") == "text"
        ).strip()

        files = envelope.get("files") or message_payload.get("files") or []
        usage = (
            envelope.get("usage")
            or message_payload.get("usage")
            or message_payload.get("metadata", {}).get("usage")
            or {}
        )
        token_count = _extract_token_usage(usage)

        tool_name = None
        if role == "tool":
            tool_name = message_payload.get("name") or message_payload.get("tool_name")

        return SessionMessage(
            message_id=message_id,
            role=role,
            text=text,
            timestamp=timestamp,
            tool_name=tool_name,
            files=files,
            token_count=token_count,
        )

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def _extract_token_usage(usage_payload: dict | None) -> int | None:
    if not usage_payload:
        return None

    for key in ("output_tokens", "input_tokens", "total_tokens"):
        if key in usage_payload and isinstance(usage_payload[key], int):
            return usage_payload[key]

    if all(isinstance(usage_payload.get(key), int) for key in ("input_tokens", "output_tokens")):
        return int(usage_payload["input_tokens"] + usage_payload["output_tokens"])

    return None
