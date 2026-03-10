"""Tests for POST /api/v1/sessions/report — project intelligence report endpoint."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from code_atlas.api.main import create_app
from code_atlas.config import AtlasSettings


@pytest.fixture
def settings(tmp_path):
    return AtlasSettings(
        claude_root=tmp_path,
        api_key_required=False,
        enable_metrics=False,
    )


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture
def session_dir_with_file(tmp_path):
    """A temp directory containing one valid .jsonl session file."""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    session_file = project_dir / "session-abc123.jsonl"
    messages = [
        {
            "type": "user",
            "message": {"role": "user", "content": "Implement a Flask API"},
            "timestamp": "2026-03-10T08:00:00Z",
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": "I'll implement a Flask API. Let me edit app.py and routes.py.",
            },
            "timestamp": "2026-03-10T08:00:05Z",
        },
        {
            "type": "tool_use",
            "message": {"name": "Edit", "input": {"file_path": "app.py"}},
            "timestamp": "2026-03-10T08:00:10Z",
        },
    ]
    with open(session_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return project_dir


class TestReportEndpoint:
    """Tests for POST /api/v1/sessions/report."""

    def test_nonexistent_path_returns_422(self, client):
        """Non-existent project_path → 422 Unprocessable Entity."""
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": "/nonexistent/path/that/does/not/exist"},
        )
        assert resp.status_code == 422

    def test_empty_dir_returns_empty_report(self, client, tmp_path):
        """Valid path with no .jsonl files → 200, sessions_analyzed=0."""
        empty_dir = tmp_path / "empty-project"
        empty_dir.mkdir()

        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(empty_dir)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions_analyzed"] == 0
        assert data["total_messages"] == 0
        assert data["project_name"] == "empty-project"
        assert "No" in data["summary"] or data["sessions_analyzed"] == 0

    def test_with_session_file_returns_report(self, client, session_dir_with_file):
        """Valid path with .jsonl session → 200 with populated report."""
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(session_dir_with_file)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions_analyzed"] == 1
        assert data["project_name"] == "my-project"
        assert data["project_path"] == str(session_dir_with_file)
        assert isinstance(data["top_files"], list)
        assert isinstance(data["top_entities"], list)
        assert isinstance(data["key_insights"], list)
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0
        assert data["cost_usd"] == 0.0  # heuristic mode — no cost

    def test_heuristic_mode_by_default(self, client, session_dir_with_file):
        """Default use_llm=False → cost_usd is 0.0."""
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(session_dir_with_file), "use_llm": False},
        )
        assert resp.status_code == 200
        assert resp.json()["cost_usd"] == 0.0

    def test_response_schema_fields_present(self, client, session_dir_with_file):
        """All required response fields are present."""
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(session_dir_with_file)},
        )
        assert resp.status_code == 200
        data = resp.json()
        required_fields = [
            "project_name", "project_path", "sessions_analyzed",
            "total_messages", "total_tokens", "top_files",
            "top_entities", "key_insights", "summary", "cost_usd",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_max_sessions_param_accepted(self, client, tmp_path):
        """max_sessions parameter is accepted without error."""
        empty_dir = tmp_path / "proj"
        empty_dir.mkdir()
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(empty_dir), "max_sessions": 10},
        )
        assert resp.status_code == 200

    def test_invalid_max_sessions_rejected(self, client, tmp_path):
        """max_sessions=0 is below minimum (1) → 422."""
        any_dir = tmp_path / "proj"
        any_dir.mkdir()
        resp = client.post(
            "/api/v1/sessions/report",
            json={"project_path": str(any_dir), "max_sessions": 0},
        )
        assert resp.status_code == 422
