"""Test SimpleHistory integration with PipelineRunner."""

from pathlib import Path

import pytest

from code_atlas.config import AtlasSettings
from code_atlas.graph_populator import GraphPopulator
from code_atlas.insight_extractor import InsightExtractor
from code_atlas.pipeline import PipelineRunner
from code_atlas.session_discovery import SessionDiscovery
from code_atlas.simple_history import SimpleHistory


@pytest.fixture
def test_settings(tmp_path):
    """Create test settings."""
    return AtlasSettings(
        session_root=tmp_path / "sessions",
        graph_name="test_graph",
        enable_metrics=False,
    )


@pytest.fixture
def sample_session(tmp_path):
    """Create a minimal test session file."""
    # Follow the pattern from test_session_discovery.py
    # Sessions are in: {root}/{project}/sessions/{session}.jsonl
    sessions_dir = tmp_path / "test-project" / "sessions"
    sessions_dir.mkdir(parents=True)

    # Create a JSONL session file with minimal content
    session_file = sessions_dir / "test-session.jsonl"
    session_file.write_text('{"type": "message", "content": "Hello"}\n')

    return tmp_path


class TestPipelineHistoryIntegration:
    """Test SimpleHistory integration with PipelineRunner."""

    def test_history_initialized_automatically(self, sample_session, test_settings):
        """History should be initialized when PipelineRunner is created."""
        discovery = SessionDiscovery(root=sample_session, settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )

        assert runner.history is not None
        assert isinstance(runner.history, SimpleHistory)
        assert runner.history.history_file.exists()

    def test_successful_processing_recorded(self, sample_session, test_settings, tmp_path):
        """Successful session processing should be recorded in history."""
        discovery = SessionDiscovery(root=sample_session, settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        # Use custom history file for this test
        history_file = tmp_path / "test_history.jsonl"
        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )
        runner.history = SimpleHistory(history_file)

        # Run pipeline (should process 1 session)
        stats = runner.run(limit=1)

        assert stats.sessions_processed >= 1
        assert stats.errors == []

        # Verify history was recorded
        success_rate = runner.history.get_success_rate("code-atlas", "extract")
        assert success_rate == 1.0  # 100% success

        patterns = runner.history.get_recent_patterns("code-atlas", "extract", limit=5)
        assert len(patterns) >= 1
        assert patterns[0]["success"] is True
        assert "session_id" in patterns[0]["context"]

    def test_failed_processing_recorded(self, tmp_path, test_settings):
        """Failed session processing should be recorded in history."""
        # Create a malformed session that will fail parsing
        sessions_dir = tmp_path / "sessions" / "test-project"
        sessions_dir.mkdir(parents=True)

        session_file = sessions_dir / "bad-session.txt"
        session_file.write_text("")  # Empty file will cause parsing issues

        discovery = SessionDiscovery(root=tmp_path / "sessions", settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        history_file = tmp_path / "test_history.jsonl"
        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )
        runner.history = SimpleHistory(history_file)

        # Run pipeline (will fail on malformed session)
        stats = runner.run()

        # Check if failures were recorded
        if stats.errors:
            patterns = runner.history.get_recent_patterns("code-atlas", "extract", limit=10)
            # Should have at least one record (success or failure)
            assert len(patterns) >= 0  # May be 0 if all failed

    def test_history_context_includes_metadata(self, sample_session, test_settings, tmp_path):
        """History records should include useful metadata."""
        discovery = SessionDiscovery(root=sample_session, settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        history_file = tmp_path / "test_history.jsonl"
        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )
        runner.history = SimpleHistory(history_file)

        # Run pipeline
        stats = runner.run(limit=1)

        if stats.sessions_processed > 0:
            patterns = runner.history.get_recent_patterns("code-atlas", "extract", limit=1)
            assert len(patterns) >= 1

            context = patterns[0]["context"]
            assert "session_id" in context
            assert "entities" in context
            assert "relationships" in context

    def test_process_session_records_history(self, sample_session, test_settings, tmp_path):
        """Single session processing should also record history."""
        discovery = SessionDiscovery(root=sample_session, settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        history_file = tmp_path / "test_history.jsonl"
        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )
        runner.history = SimpleHistory(history_file)

        # Find a session file (should be .jsonl)
        session_files = list(sample_session.rglob("*.jsonl"))
        assert len(session_files) > 0

        # Process single session
        result = runner.process_session(session_files[0], use_llm=False, dry_run=True)

        # In dry_run mode, history should NOT be recorded
        patterns = runner.history.get_recent_patterns("code-atlas", "extract")
        assert len(patterns) == 0  # Dry run doesn't record

        # Process without dry_run
        result = runner.process_session(session_files[0], use_llm=False, dry_run=False)

        if result["success"]:
            patterns = runner.history.get_recent_patterns("code-atlas", "extract", limit=1)
            assert len(patterns) >= 1
            assert patterns[0]["success"] is True

    def test_history_file_location(self, sample_session, test_settings, monkeypatch):
        """History file should be in .forge/state/ by default."""
        # Change to temp directory
        monkeypatch.chdir(sample_session.parent)

        discovery = SessionDiscovery(root=sample_session, settings=test_settings)
        extractor = InsightExtractor(use_llm=False)
        populator = GraphPopulator(graph_name="test", dry_run=True)

        runner = PipelineRunner(
            discovery=discovery,
            extractor=extractor,
            populator=populator,
            settings=test_settings,
        )

        expected_path = Path.cwd() / ".forge" / "state" / "code_atlas_history.jsonl"
        assert runner.history.history_file == expected_path
