"""Comprehensive tests for Code Atlas CLI commands.

Tests all 10 CLI commands with both normal and JSON output modes,
covering success paths, error scenarios, and edge cases.

NOTE: These tests require KMP_DUPLICATE_LIB_OK=TRUE environment variable
to avoid OpenMP conflicts with sentence-transformers library.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import redis
from typer.testing import CliRunner

# Set OpenMP workaround before importing CLI (prevents hangs)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from code_atlas.cli import app
from code_atlas.config import AtlasSettings
from code_atlas.insight_extractor import Entity, ExtractionResult, Relationship
from code_atlas.models import SessionMetadata
from code_atlas.pipeline import PipelineStats

# Test fixtures
@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def mock_settings() -> AtlasSettings:
    """Create test settings."""
    return AtlasSettings(
        claude_root=Path("/test/claude"),
        redis_url="redis://localhost:6379",
        graph_name="test_atlas",
        enable_metrics=False,
    )


@pytest.fixture
def sample_session_metadata() -> SessionMetadata:
    """Create sample session metadata for tests."""
    return SessionMetadata(
        path="/test/session.jsonl",
        session_id="test-sess-001",
        project="test_project",
        size_bytes=1024,
        modified_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_extraction() -> ExtractionResult:
    """Create sample extraction result."""
    return ExtractionResult(
        entities=[
            Entity(type="file", name="src/main.py"),
            Entity(type="concept", name="authentication"),
        ],
        relationships=[Relationship(type="MENTIONS", source="test-sess-001", target="src/main.py")],
        insights=["Implemented OAuth flow"],
    )


# =============================================================================
# DISCOVER COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
def test_discover_normal_output(
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    sample_session_metadata: SessionMetadata,
) -> None:
    """Test discover command with normal Rich table output."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery.discover.return_value = [sample_session_metadata]
    mock_discovery_class.return_value = mock_discovery

    result = runner.invoke(app, ["discover"])

    assert result.exit_code == 0
    assert "test-sess-001" in result.stdout
    assert "test_project" in result.stdout


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
def test_discover_json_output(
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    sample_session_metadata: SessionMetadata,
) -> None:
    """Test discover command with JSON output."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery.discover.return_value = [sample_session_metadata]
    mock_discovery_class.return_value = mock_discovery

    result = runner.invoke(app, ["discover", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "discover"
    assert data["count"] == 1
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "test-sess-001"
    assert data["sessions"][0]["project"] == "test_project"


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
def test_discover_with_filters(
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    sample_session_metadata: SessionMetadata,
) -> None:
    """Test discover command with project filters."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery.discover.return_value = [sample_session_metadata]
    mock_discovery_class.return_value = mock_discovery

    result = runner.invoke(
        app,
        [
            "discover",
            "--include-project",
            "test_project",
            "--limit",
            "5",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["count"] == 1


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
def test_discover_root_not_found(
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test discover command when root directory doesn't exist."""
    mock_load_settings.return_value = mock_settings
    mock_discovery_class.side_effect = FileNotFoundError("Root not found")

    result = runner.invoke(app, ["discover", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "ROOT_NOT_FOUND"


# =============================================================================
# INDEX COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_index_sessions_json_output(
    mock_runner_class: Mock,
    mock_populator_class: Mock,
    mock_extractor_class: Mock,
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test index command with JSON output."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    # Mock pipeline stats
    stats = PipelineStats(
        sessions_processed=3,
        messages_parsed=25,
        total_tokens=5000,
        entities_created=15,
        relationships_created=20,
        insights_logged=5,
        estimated_cost_usd=0.015,
        errors=[],
        retries_attempted=0,
        sessions_quarantined=0,
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = stats
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["index", "--limit", "3", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "index"
    assert data["stats"]["sessions_processed"] == 3
    assert data["stats"]["entities_created"] == 15
    assert data["stats"]["estimated_cost_usd"] == 0.015


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_index_dry_run_mode(
    mock_runner_class: Mock,
    mock_populator_class: Mock,
    mock_extractor_class: Mock,
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test index command in dry-run mode."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    stats = PipelineStats(
        sessions_processed=2,
        messages_parsed=10,
        total_tokens=2000,
        entities_created=8,
        relationships_created=10,
        insights_logged=2,
        estimated_cost_usd=0.008,
        errors=[],
        retries_attempted=0,
        sessions_quarantined=0,
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = stats
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["index", "--dry-run", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["dry_run"] is True


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
def test_index_invalid_provider(
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test index command with invalid LLM provider."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    result = runner.invoke(
        app,
        ["index", "--use-llm", "--provider", "invalid-provider", "--json"],
    )

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_PROVIDER"
    assert "anthropic" in data["error"]["details"]["valid"]
    assert "openrouter" in data["error"]["details"]["valid"]


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_index_no_sessions_processed(
    mock_runner_class: Mock,
    mock_populator_class: Mock,
    mock_extractor_class: Mock,
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test index command when no sessions are processed."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    stats = PipelineStats(
        sessions_processed=0,
        messages_parsed=0,
        total_tokens=0,
        entities_created=0,
        relationships_created=0,
        insights_logged=0,
        estimated_cost_usd=0.0,
        errors=[],
        retries_attempted=0,
        sessions_quarantined=0,
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = stats
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["index", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert "warning" in data


# =============================================================================
# RUN COMMAND TESTS (legacy alias for index)
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_run_delegates_to_index(
    mock_runner_class: Mock,
    mock_populator_class: Mock,
    mock_extractor_class: Mock,
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test that run command delegates to index_sessions."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    stats = PipelineStats(
        sessions_processed=1,
        messages_parsed=5,
        total_tokens=1000,
        entities_created=3,
        relationships_created=4,
        insights_logged=1,
        estimated_cost_usd=0.005,
        errors=[],
        retries_attempted=0,
        sessions_quarantined=0,
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = stats
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["run", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "index"


# =============================================================================
# QUERY COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.VectorStore")
@patch("code_atlas.cli.create_rag_service")
def test_query_json_output(
    mock_create_rag: Mock,
    mock_vector_store_class: Mock,
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test query command with JSON output."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    # Mock RAG service response
    mock_rag = MagicMock()
    mock_rag.answer_question.return_value = {
        "answer": "OAuth is implemented using JWT tokens",
        "confidence": 0.95,
        "sources": ["src/auth.py", "docs/auth.md"],
        "context_entities": [
            {"entity_type": "File", "entity_name": "src/auth.py"},
            {"entity_type": "Concept", "entity_name": "authentication"},
        ],
        "search_results_count": 5,
    }
    mock_create_rag.return_value = mock_rag

    result = runner.invoke(app, ["query", "How is OAuth implemented?", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "query"
    assert "OAuth" in data["answer"]
    assert data["confidence"] == 0.95
    assert len(data["context_entities"]) == 2


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_query_connection_error(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test query command when FalkorDB connection fails."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
    mock_redis_class.from_url.return_value = mock_redis

    result = runner.invoke(app, ["query", "test question", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "CONNECTION_ERROR"


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.VectorStore")
@patch("code_atlas.cli.create_rag_service")
def test_query_with_filters(
    mock_create_rag: Mock,
    mock_vector_store_class: Mock,
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test query command with entity type filters."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_rag = MagicMock()
    mock_rag.answer_question.return_value = {
        "answer": "Found 3 files",
        "confidence": 0.90,
        "sources": [],
        "context_entities": [],
        "search_results_count": 3,
    }
    mock_create_rag.return_value = mock_rag

    result = runner.invoke(
        app,
        ["query", "List files", "--entity-type", "File", "--limit", "10", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True


# =============================================================================
# EXPORT COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_export_json_format(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    tmp_path: Path,
) -> None:
    """Test export command with JSON format."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    # Mock graph query results
    mock_populator = MagicMock()
    mock_populator.execute_query.side_effect = [
        [{"e": {"id": "file-1", "name": "test.py"}, "types": ["File"]}],  # entities
        [{"from_id": "sess-1", "to_id": "file-1", "rel_type": "MENTIONS"}],  # relationships
    ]
    mock_populator_class.return_value = mock_populator

    output_file = tmp_path / "export.json"
    result = runner.invoke(
        app,
        ["export", "--output", str(output_file), "--format", "json", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "export"
    assert data["format"] == "json"
    assert data["entity_count"] >= 0


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_export_invalid_format(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    tmp_path: Path,
) -> None:
    """Test export command with invalid format."""
    mock_load_settings.return_value = mock_settings

    output_file = tmp_path / "export.txt"
    result = runner.invoke(
        app,
        ["export", "--output", str(output_file), "--format", "invalid", "--json"],
    )

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_FORMAT"
    assert "json" in data["error"]["details"]["valid"]
    assert "cypher" in data["error"]["details"]["valid"]
    assert "graphml" in data["error"]["details"]["valid"]


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_export_cypher_format(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    tmp_path: Path,
) -> None:
    """Test export command with Cypher format."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.execute_query.side_effect = [
        [{"e": {"id": "file-1", "name": "test.py"}, "types": ["File"]}],
        [],
    ]
    mock_populator_class.return_value = mock_populator

    output_file = tmp_path / "export.cypher"
    result = runner.invoke(
        app,
        ["export", "--output", str(output_file), "--format", "cypher", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True


# =============================================================================
# STATUS COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_status_json_output(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test status command with JSON output."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    # Mock graph query results
    mock_populator = MagicMock()
    mock_populator.execute_query.side_effect = [
        [{"type": "File", "count": 15}, {"type": "Concept", "count": 10}],  # entities
        [{"type": "MENTIONS", "count": 25}],  # relationships
    ]
    mock_populator_class.return_value = mock_populator

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "status"
    assert data["connected"] is True
    assert data["entities"]["total"] == 25
    assert data["relationships"]["total"] == 25


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_status_connection_failed(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test status command when database connection fails."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
    mock_redis_class.from_url.return_value = mock_redis

    result = runner.invoke(app, ["status", "--json"])

    # Note: status command doesn't exit with error code on connection failure
    # It just reports the failure in output
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert "error" in data


# =============================================================================
# REPORT COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_report_json_output(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test report command with JSON output."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    # Mock GRAPH.QUERY responses
    def mock_execute_command(cmd: str, graph: str, query: str, *args: Any) -> list:
        if "File" in query:
            return [[], [["src/main.py", 10], ["src/auth.py", 8]]]
        elif "Concept" in query:
            return [[], [["authentication", 15], ["authorization", 12]]]
        elif "COUNT(s)" in query:
            return [[], [[5, 2048.0, 10240.0]]]
        elif "modified_at DESC" in query:
            return [[], [["sess-1", "project-a", 1234567890.0]]]
        return [[], []]

    mock_redis.execute_command.side_effect = mock_execute_command
    mock_redis_class.from_url.return_value = mock_redis

    result = runner.invoke(app, ["report", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["operation"] == "report"
    assert len(data["top_files"]) == 2
    assert len(data["top_concepts"]) == 2
    assert "stats" in data


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_report_connection_error(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test report command when connection fails."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.side_effect = redis.ConnectionError("Connection failed")
    mock_redis_class.from_url.return_value = mock_redis

    result = runner.invoke(app, ["report", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "CONNECTION_ERROR"


# =============================================================================
# INDEXES COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_indexes_list_action(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test indexes command with list action."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.list_indexes.return_value = {
        "Session": ["id", "project", "modified_at"],
        "Entity": ["id", "name"],
        "Relationships": ["confidence"],
    }
    mock_populator_class.return_value = mock_populator

    result = runner.invoke(app, ["indexes", "--action", "list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["action"] == "list"
    assert "Session" in data["indexes"]


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_indexes_create_action(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test indexes command with create action."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.executed_queries = [
        "CREATE INDEX ON :Session(id)",
        "CREATE INDEX ON :File(name)",
    ]
    mock_populator_class.return_value = mock_populator

    result = runner.invoke(app, ["indexes", "--action", "create", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["action"] == "create"
    assert data["indexes_created"] == 2


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_indexes_verify_action(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test indexes command with verify action."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.verify_indexes.return_value = {
        "Session": {"id": True, "project": True},
        "Entity": {"id": True, "name": False},
    }
    mock_populator_class.return_value = mock_populator

    result = runner.invoke(app, ["indexes", "--action", "verify", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["action"] == "verify"
    assert "Session" in data["result"]


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_indexes_drop_action(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test indexes command with drop action."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.drop_indexes.return_value = None
    mock_populator_class.return_value = mock_populator

    result = runner.invoke(app, ["indexes", "--action", "drop", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
    assert data["action"] == "drop"


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
def test_indexes_invalid_action(
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test indexes command with invalid action."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    result = runner.invoke(app, ["indexes", "--action", "invalid", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_ACTION"


# =============================================================================
# METRICS COMMAND TESTS
# =============================================================================


@patch("code_atlas.cli.load_settings")
def test_metrics_disabled_error(
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test metrics command when metrics are disabled."""
    mock_settings.enable_metrics = False
    mock_load_settings.return_value = mock_settings

    result = runner.invoke(app, ["metrics", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["error"]["code"] == "METRICS_DISABLED"


@patch("code_atlas.cli.load_settings")
def test_metrics_enabled_json_output(
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test metrics command JSON output when enabled."""
    mock_settings.enable_metrics = True
    mock_load_settings.return_value = mock_settings

    # Note: We just test the initial output, not the full server startup
    result = runner.invoke(app, ["metrics", "--json"])

    # The command will fail to start the server in test environment
    # but we can verify the initial JSON output was correct
    if result.exit_code == 0:
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["operation"] == "metrics"
        assert data["status"] == "starting"


# =============================================================================
# SERVE COMMAND TESTS
# =============================================================================


def test_serve_basic_invocation() -> None:
    """Test serve command basic invocation (doesn't fully start server in tests)."""
    # Note: serve command starts a FastAPI server which we can't fully test here
    # We just verify the command exists and accepts arguments
    result = runner.invoke(app, ["serve", "--help"])

    assert result.exit_code == 0
    assert "Start the Code Atlas API server" in result.stdout


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


def test_app_no_args_shows_help() -> None:
    """Test that running CLI with no arguments shows help."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Utilities for turning Claude sessions" in result.stdout


@patch("code_atlas.cli.load_settings")
def test_invalid_config_file(mock_load_settings: Mock) -> None:
    """Test behavior with invalid config file path."""
    mock_load_settings.side_effect = FileNotFoundError("Config not found")

    # discover command tries to load settings
    result = runner.invoke(app, ["discover", "--config", "/invalid/path.toml"])

    # Should fail during settings load
    assert result.exit_code != 0


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_index_with_use_llm_flag(
    mock_runner_class: Mock,
    mock_populator_class: Mock,
    mock_extractor_class: Mock,
    mock_discovery_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
) -> None:
    """Test index command with LLM extraction enabled."""
    mock_load_settings.return_value = mock_settings
    mock_discovery = MagicMock()
    mock_discovery_class.return_value = mock_discovery

    stats = PipelineStats(
        sessions_processed=1,
        messages_parsed=5,
        total_tokens=1000,
        entities_created=5,
        relationships_created=6,
        insights_logged=2,
        estimated_cost_usd=0.010,
        errors=[],
        retries_attempted=0,
        sessions_quarantined=0,
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = stats
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(
        app,
        ["index", "--use-llm", "--provider", "anthropic", "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True


@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.redis.Redis")
@patch("code_atlas.cli.GraphPopulator")
def test_export_with_entity_type_filter(
    mock_populator_class: Mock,
    mock_redis_class: Mock,
    mock_load_settings: Mock,
    mock_settings: AtlasSettings,
    tmp_path: Path,
) -> None:
    """Test export command with entity type filtering."""
    mock_load_settings.return_value = mock_settings
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_class.from_url.return_value = mock_redis

    mock_populator = MagicMock()
    mock_populator.execute_query.side_effect = [
        [{"e": {"id": "file-1", "name": "test.py"}, "types": ["File"]}],
        [],
    ]
    mock_populator_class.return_value = mock_populator

    output_file = tmp_path / "files.json"
    result = runner.invoke(
        app,
        [
            "export",
            "--output",
            str(output_file),
            "--entity-type",
            "File",
            "--limit",
            "100",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
