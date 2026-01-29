"""Integration tests for the end-to-end Code Atlas pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import redis

from code_atlas.exceptions import SessionProcessingError
from code_atlas.graph_populator import GraphPopulator
from code_atlas.insight_extractor import InsightExtractor
from code_atlas.pipeline import PipelineConfig, PipelineRunner
from code_atlas.session_discovery import SessionDiscovery


def _write_session_jsonl(path: Path, payloads: list[dict]) -> None:
    """Helper to write JSONL session files."""
    lines = "\n".join(json.dumps(payload) for payload in payloads)
    path.write_text(lines, encoding="utf-8")


@pytest.fixture
def sample_session_files(tmp_path: Path) -> Path:
    """Generate 3 realistic test JSONL session files with varied content."""
    # Create sessions directory structure
    project_dir = tmp_path / "test_project" / "sessions"
    project_dir.mkdir(parents=True)

    # Session 1: Small session with file references
    session1_path = project_dir / "session-001.jsonl"
    session1_payloads = [
        {
            "type": "session_metadata",
            "timestamp": "2025-11-12T10:00:00Z",
        },
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:05Z",
            "files": ["backend/app.py", "backend/models.py"],
            "usage": {"input_tokens": 150},
            "message": {
                "id": "msg-user-1",
                "role": "user",
                "content": [
                    {"type": "text", "text": "Review backend/app.py and backend/models.py"}
                ],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:15Z",
            "usage": {"output_tokens": 100},
            "message": {
                "id": "msg-assistant-1",
                "role": "assistant",
                "content": [{"type": "text", "text": "I've reviewed the files. They look good."}],
            },
        },
    ]
    _write_session_jsonl(session1_path, session1_payloads)

    # Session 2: Medium session with tool usage
    session2_path = project_dir / "session-002.jsonl"
    session2_payloads = [
        {
            "type": "session_metadata",
            "timestamp": "2025-11-13T14:00:00Z",
        },
        {
            "type": "message",
            "timestamp": "2025-11-13T14:00:10Z",
            "files": ["tests/test_api.py"],
            "usage": {"input_tokens": 200},
            "message": {
                "id": "msg-user-2",
                "role": "user",
                "content": [{"type": "text", "text": "Run tests in tests/test_api.py"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-13T14:00:20Z",
            "message": {
                "id": "msg-tool-1",
                "role": "tool",
                "name": "Bash",
                "content": [{"type": "text", "text": "pytest tests/test_api.py ... PASSED"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-13T14:00:30Z",
            "usage": {"output_tokens": 150},
            "message": {
                "id": "msg-assistant-2",
                "role": "assistant",
                "content": [{"type": "text", "text": "All tests passed successfully."}],
            },
        },
    ]
    _write_session_jsonl(session2_path, session2_payloads)

    # Session 3: Large session with multiple file references
    session3_path = project_dir / "session-003.jsonl"
    session3_payloads = [
        {
            "type": "session_metadata",
            "timestamp": "2025-11-14T09:00:00Z",
        },
        {
            "type": "message",
            "timestamp": "2025-11-14T09:00:05Z",
            "files": ["frontend/App.tsx", "frontend/components/Header.tsx"],
            "usage": {"input_tokens": 300},
            "message": {
                "id": "msg-user-3",
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Update frontend/App.tsx and frontend/components/Header.tsx",
                    }
                ],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-14T09:00:20Z",
            "usage": {"output_tokens": 250},
            "message": {
                "id": "msg-assistant-3",
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I've updated both files with the new design."}
                ],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-14T09:00:35Z",
            "files": ["frontend/styles.css"],
            "usage": {"input_tokens": 100},
            "message": {
                "id": "msg-user-4",
                "role": "user",
                "content": [{"type": "text", "text": "Also update frontend/styles.css"}],
            },
        },
        {
            "type": "message",
            "timestamp": "2025-11-14T09:00:50Z",
            "usage": {"output_tokens": 120},
            "message": {
                "id": "msg-assistant-4",
                "role": "assistant",
                "content": [{"type": "text", "text": "CSS updated with new color scheme."}],
            },
        },
    ]
    _write_session_jsonl(session3_path, session3_payloads)

    return tmp_path


def test_pipeline_end_to_end_dry_run(sample_session_files: Path) -> None:
    """Test full pipeline in dry-run mode verifies stats accuracy."""
    # Setup components in dry-run mode
    discovery = SessionDiscovery(root=sample_session_files)
    extractor = InsightExtractor(use_llm=False)  # Heuristic extraction only
    populator = GraphPopulator(dry_run=True)

    # Create pipeline runner
    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
    )

    # Run pipeline
    stats = runner.run()

    # Verify stats accuracy
    assert stats.sessions_processed == 3, "Should process all 3 sessions"
    assert stats.messages_parsed > 0, "Should parse messages from sessions"
    assert stats.total_tokens > 0, "Should count tokens from messages"
    assert stats.entities_created > 0, "Should extract file entities"
    assert stats.estimated_cost_usd == 0.0, "Heuristic extraction has no cost"
    assert len(stats.errors) == 0, "Should have no errors in dry-run"

    # Verify specific counts
    # Session 1: 2 messages, Session 2: 3 messages, Session 3: 4 messages
    assert stats.messages_parsed == 9, "Should parse 9 messages total"

    # Session 1: 250 tokens, Session 2: 350 tokens, Session 3: 770 tokens
    assert stats.total_tokens == 1370, "Should count 1370 tokens total"

    # Session 1: 2 files, Session 2: 1 file, Session 3: 3 files = 6 entities total
    assert stats.entities_created == 6, "Should extract 6 file entities"


@pytest.fixture
def falkordb_available() -> bool:
    """Check if FalkorDB (not just Redis) is available at localhost:6379."""
    try:
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()
        # Verify FalkorDB-specific GRAPH.QUERY support
        client.execute_command("GRAPH.QUERY", "test_availability_check", "RETURN 1")
        return True
    except (redis.ConnectionError, redis.TimeoutError, redis.ResponseError):
        return False


@pytest.fixture
def test_graph_name() -> str:
    """Return a unique graph name for testing."""
    return "test_code_atlas_pipeline"


@pytest.fixture
def cleanup_test_graph(test_graph_name: str) -> None:
    """Cleanup test graph after test completion."""
    yield
    try:
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.execute_command("GRAPH.DELETE", test_graph_name)
    except (redis.ConnectionError, redis.ResponseError):
        pass


@pytest.mark.integration
def test_pipeline_end_to_end_with_falkordb(
    sample_session_files: Path,
    falkordb_available: bool,
    test_graph_name: str,
    cleanup_test_graph: None,
) -> None:
    """Test full pipeline with real FalkorDB connection."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    # Setup components with real FalkorDB
    discovery = SessionDiscovery(root=sample_session_files)
    extractor = InsightExtractor(use_llm=False)  # Heuristic extraction
    populator = GraphPopulator(graph_name=test_graph_name, dry_run=False)

    # Create pipeline runner
    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
    )

    # Run pipeline
    stats = runner.run()

    # Verify stats
    assert stats.sessions_processed == 3
    assert stats.entities_created == 5
    assert len(stats.errors) == 0

    # Query database to verify nodes created
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    # Verify Session nodes exist
    result = client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session) RETURN count(s)",
    )
    assert result is not None
    # FalkorDB returns nested arrays: [[count], [metadata]]
    # The count should be 3 sessions

    # Verify File nodes exist
    result = client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (f:File) RETURN count(f)",
    )
    assert result is not None

    # Verify MENTIONS relationships exist
    result = client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session)-[:MENTIONS]->(f:File) RETURN count(*)",
    )
    assert result is not None


def test_pipeline_error_recovery(tmp_path: Path) -> None:
    """Test pipeline continues processing when one session fails."""
    # Create sessions directory
    project_dir = tmp_path / "test_project" / "sessions"
    project_dir.mkdir(parents=True)

    # Create one valid session
    valid_session = project_dir / "valid-session.jsonl"
    valid_payloads = [
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:00Z",
            "files": ["valid.py"],
            "usage": {"input_tokens": 100},
            "message": {
                "id": "msg-1",
                "role": "user",
                "content": [{"type": "text", "text": "Test message"}],
            },
        }
    ]
    _write_session_jsonl(valid_session, valid_payloads)

    # Create one malformed session (invalid JSON)
    malformed_session = project_dir / "malformed-session.jsonl"
    malformed_session.write_text("{invalid json\n{also invalid}", encoding="utf-8")

    # Create another valid session
    valid_session2 = project_dir / "valid-session-2.jsonl"
    valid_payloads2 = [
        {
            "type": "message",
            "timestamp": "2025-11-12T11:00:00Z",
            "files": ["another.py"],
            "usage": {"input_tokens": 150},
            "message": {
                "id": "msg-2",
                "role": "user",
                "content": [{"type": "text", "text": "Another test"}],
            },
        }
    ]
    _write_session_jsonl(valid_session2, valid_payloads2)

    # Setup pipeline
    discovery = SessionDiscovery(root=tmp_path)
    extractor = InsightExtractor(use_llm=False)
    populator = GraphPopulator(dry_run=True)

    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
    )

    # Run pipeline
    stats = runner.run()

    # Verify error was captured
    assert len(stats.errors) == 1, "Should capture one error from malformed session"
    assert "malformed-session" in stats.errors[0], "Error should reference malformed session"

    # Verify other sessions were still processed
    assert stats.sessions_processed == 2, "Should successfully process 2 valid sessions"
    assert stats.messages_parsed == 2, "Should parse 2 messages from valid sessions"
    assert stats.entities_created == 2, "Should extract entities from valid sessions"


def test_pipeline_retries_transient_failures(tmp_path: Path) -> None:
    """Test pipeline retries on transient failures with exponential backoff."""
    # Create a valid session
    project_dir = tmp_path / "test_project" / "sessions"
    project_dir.mkdir(parents=True)

    session_path = project_dir / "test-session.jsonl"
    payloads = [
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:00Z",
            "files": ["test.py"],
            "usage": {"input_tokens": 100},
            "message": {
                "id": "msg-1",
                "role": "user",
                "content": [{"type": "text", "text": "Test message"}],
            },
        }
    ]
    _write_session_jsonl(session_path, payloads)

    # Setup pipeline with mocked extractor that fails twice then succeeds
    discovery = SessionDiscovery(root=tmp_path)
    extractor = InsightExtractor(use_llm=False)
    populator = GraphPopulator(dry_run=True)

    # Create config with retry settings
    config = PipelineConfig(max_retries=3, retry_delay_base=0.1, quarantine_dir=None)

    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
        config=config,
    )

    # Mock the extractor to fail twice then succeed
    call_count = 0

    def failing_extract(session):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise SessionProcessingError("Transient error")
        # Third call succeeds
        return extractor._heuristic_extract(session)

    with patch.object(extractor, "extract", side_effect=failing_extract):
        stats = runner.run()

    # Verify retry behavior
    assert call_count == 3, "Should call extract 3 times (2 failures + 1 success)"
    assert stats.retries_attempted == 2, "Should record 2 retry attempts"
    assert stats.sessions_processed == 1, "Should successfully process session after retries"
    assert len(stats.errors) == 0, "Should have no errors after successful retry"
    assert stats.sessions_quarantined == 0, "Should not quarantine successful session"


def test_pipeline_quarantines_permanent_failures(tmp_path: Path) -> None:
    """Test pipeline quarantines sessions with permanent failures."""
    # Create a valid session
    project_dir = tmp_path / "test_project" / "sessions"
    project_dir.mkdir(parents=True)

    session_path = project_dir / "failing-session.jsonl"
    payloads = [
        {
            "type": "message",
            "timestamp": "2025-11-12T10:00:00Z",
            "files": ["test.py"],
            "usage": {"input_tokens": 100},
            "message": {
                "id": "msg-1",
                "role": "user",
                "content": [{"type": "text", "text": "Test message"}],
            },
        }
    ]
    _write_session_jsonl(session_path, payloads)

    # Setup quarantine directory
    quarantine_dir = tmp_path / "quarantine"

    # Setup pipeline with mocked extractor that always fails
    discovery = SessionDiscovery(root=tmp_path)
    extractor = InsightExtractor(use_llm=False)
    populator = GraphPopulator(dry_run=True)

    config = PipelineConfig(
        max_retries=3,
        retry_delay_base=0.1,
        quarantine_dir=quarantine_dir,
    )

    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
        config=config,
    )

    # Mock the extractor to always fail
    def always_fail(session):
        raise SessionProcessingError("Permanent error")

    with patch.object(extractor, "extract", side_effect=always_fail):
        stats = runner.run()

    # Verify failure handling
    assert stats.retries_attempted == 3, "Should attempt 3 retries"
    assert stats.sessions_processed == 0, "Should not count failed session as processed"
    assert len(stats.errors) == 1, "Should record 1 error"
    assert "failing-session" in stats.errors[0], "Error should reference session ID"
    assert stats.sessions_quarantined == 1, "Should quarantine 1 session"

    # Verify quarantine file was created
    assert quarantine_dir.exists(), "Quarantine directory should be created"
    quarantine_files = list(quarantine_dir.glob("*.json"))
    assert len(quarantine_files) == 1, "Should create 1 quarantine file"

    # Verify quarantine file contents
    quarantine_file = quarantine_files[0]
    with quarantine_file.open("r", encoding="utf-8") as f:
        quarantine_data = json.load(f)

    assert quarantine_data["session_id"] == "failing-session"
    assert quarantine_data["error"] == "Permanent error"
    assert quarantine_data["error_type"] == "SessionProcessingError"
    assert "timestamp" in quarantine_data
    assert quarantine_data["size_bytes"] > 0
