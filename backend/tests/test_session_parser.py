from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from code_atlas.models import SessionMetadata
from code_atlas.session_parser import SessionParser


def _write_payloads(path: Path, payloads: list[dict]) -> None:
    lines = "\n".join(json.dumps(payload) for payload in payloads)
    path.write_text(lines, encoding="utf-8")


def test_parser_extracts_messages(tmp_path: Path) -> None:
    session_path = tmp_path / "session.jsonl"
    payloads = [
        {
            "type": "session_metadata",
            "timestamp": "2025-11-12T10:00:00Z",
        },
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:05Z",
            "files": ["app/main.py"],
            "usage": {"input_tokens": 120},
            "message": {
                "id": "msg-user",
                "role": "user",
                "content": [{"type": "text", "text": "Please refactor app/main.py"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:15Z",
            "files": ["app/main.py"],
            "usage": {"output_tokens": 80},
            "message": {
                "id": "msg-assistant",
                "role": "assistant",
                "content": [{"type": "text", "text": "Sure, here is the diff."}],
            },
        },
    ]
    _write_payloads(session_path, payloads)

    metadata = SessionMetadata(
        path=session_path,
        session_id="session",
        project="alpha",
        size_bytes=session_path.stat().st_size,
        modified_at=datetime.now(tz=timezone.utc),
    )

    parsed = SessionParser(metadata=metadata).parse()

    assert len(parsed.messages) == 2
    assert parsed.total_tokens == 200  # 120 + 80 from usage payloads
    assert parsed.referenced_files == ["app/main.py"]
    assert abs(parsed.duration_seconds - 10.0) < 0.1
    assert parsed.messages[0].role == "user"
    assert parsed.messages[1].role == "assistant"
