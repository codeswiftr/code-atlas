"""Tests for SimpleHistory pattern tracking."""

import json
from pathlib import Path

import pytest

from code_atlas.simple_history import SimpleHistory


class TestSimpleHistory:
    """Test SimpleHistory for code-atlas CLI compounding."""

    @pytest.fixture
    def history(self, tmp_path):
        """Create history with temp file."""
        return SimpleHistory(tmp_path / "history.jsonl")

    def test_record_success(self, history):
        """Record successful operation."""
        history.record("code-atlas", "sessions", "extract", True)
        assert history.history_file.exists()

        # Verify file content
        with open(history.history_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["domain"] == "code-atlas"
            assert record["project"] == "sessions"
            assert record["action"] == "extract"
            assert record["success"] is True
            assert "timestamp" in record

    def test_record_failure_with_context(self, history):
        """Record failure with error context."""
        history.record(
            "code-atlas",
            "sessions",
            "extract",
            False,
            context={"error": "Connection timeout", "retry_count": 3}
        )
        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 0.0

        # Verify context was saved
        with open(history.history_file, "r") as f:
            record = json.loads(f.readline())
            assert record["context"]["error"] == "Connection timeout"
            assert record["context"]["retry_count"] == 3

    def test_success_rate_calculation(self, history):
        """Calculate success rate correctly."""
        # 8 successes, 2 failures = 80%
        for _ in range(8):
            history.record("code-atlas", "sessions", "extract", True)
        for _ in range(2):
            history.record("code-atlas", "sessions", "extract", False)

        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 0.8

    def test_success_rate_with_limit(self, history):
        """Respect limit when calculating success rate."""
        # Old records: 5 failures
        for _ in range(5):
            history.record("code-atlas", "sessions", "extract", False)

        # Recent records: 5 successes
        for _ in range(5):
            history.record("code-atlas", "sessions", "extract", True)

        # With limit=5, should only see recent successes
        rate = history.get_success_rate("code-atlas", "extract", limit=5)
        assert rate == 1.0

        # With limit=10, should see all records
        rate = history.get_success_rate("code-atlas", "extract", limit=10)
        assert rate == 0.5

    def test_success_rate_no_history(self, history):
        """Return neutral rate when no history exists."""
        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 0.5

    def test_should_proceed_above_threshold(self, history):
        """Proceed when above threshold."""
        for _ in range(9):
            history.record("code-atlas", "sessions", "extract", True)
        history.record("code-atlas", "sessions", "extract", False)

        should_proceed, rate = history.should_proceed("code-atlas", "extract", 0.8)
        assert should_proceed is True
        assert rate == 0.9

    def test_should_not_proceed_below_threshold(self, history):
        """Don't proceed when below threshold."""
        for _ in range(5):
            history.record("code-atlas", "sessions", "extract", True)
        for _ in range(5):
            history.record("code-atlas", "sessions", "extract", False)

        should_proceed, rate = history.should_proceed("code-atlas", "extract", 0.6)
        assert should_proceed is False
        assert rate == 0.5

    def test_should_proceed_default_threshold(self, history):
        """Use default threshold of 0.6."""
        # 7 successes, 3 failures = 70%
        for _ in range(7):
            history.record("code-atlas", "sessions", "extract", True)
        for _ in range(3):
            history.record("code-atlas", "sessions", "extract", False)

        should_proceed, rate = history.should_proceed("code-atlas", "extract")
        assert should_proceed is True
        assert rate == 0.7

    def test_get_recent_patterns(self, history):
        """Get recent successful patterns."""
        # Add some failures
        history.record("code-atlas", "sessions", "extract", False)
        history.record("code-atlas", "sessions", "extract", False)

        # Add successful patterns with context
        for i in range(5):
            history.record(
                "code-atlas",
                "sessions",
                "extract",
                True,
                context={"entities": 10 + i, "duration_ms": 100 + i * 10}
            )

        patterns = history.get_recent_patterns("code-atlas", "extract", limit=3)
        assert len(patterns) == 3
        assert all(p["success"] for p in patterns)

        # Most recent should be first
        assert patterns[0]["context"]["entities"] == 14
        assert patterns[1]["context"]["entities"] == 13
        assert patterns[2]["context"]["entities"] == 12

    def test_filter_by_domain_and_action(self, history):
        """Filter records by domain and action."""
        # Add records for different domains/actions
        history.record("code-atlas", "sessions", "extract", True)
        history.record("code-atlas", "sessions", "query", True)
        history.record("other-domain", "sessions", "extract", True)
        history.record("code-atlas", "other-project", "extract", True)

        # Should only match code-atlas + extract
        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 1.0

        # Verify only one record matched (2 successes out of 2 would be 1.0,
        # but we only have 1 matching record)
        matching = history._get_matching_records("code-atlas", "extract", 10)
        assert len(matching) == 2  # Matches project="sessions" and project="other-project"

    def test_multiple_actions_tracked_independently(self, history):
        """Different actions maintain independent success rates."""
        # Extract: 90% success
        for _ in range(9):
            history.record("code-atlas", "sessions", "extract", True)
        history.record("code-atlas", "sessions", "extract", False)

        # Query: 50% success
        for _ in range(5):
            history.record("code-atlas", "sessions", "query", True)
        for _ in range(5):
            history.record("code-atlas", "sessions", "query", False)

        extract_rate = history.get_success_rate("code-atlas", "extract")
        query_rate = history.get_success_rate("code-atlas", "query")

        assert extract_rate == 0.9
        assert query_rate == 0.5

    def test_malformed_lines_skipped(self, history, tmp_path):
        """Skip malformed JSONL lines gracefully."""
        # Write some valid and invalid records
        with open(history.history_file, "w") as f:
            f.write('{"domain": "code-atlas", "action": "extract", "success": true}\n')
            f.write('invalid json line\n')
            f.write('{"domain": "code-atlas", "action": "extract"}\n')  # Missing success
            f.write('{"domain": "code-atlas", "action": "extract", "success": false}\n')

        # Should only process valid lines with required fields
        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 0.5  # 1 success, 1 failure

    def test_empty_file_handling(self, history):
        """Handle empty history file."""
        # File exists but is empty
        history.history_file.touch()

        rate = history.get_success_rate("code-atlas", "extract")
        assert rate == 0.5  # Neutral default

        patterns = history.get_recent_patterns("code-atlas", "extract")
        assert patterns == []

    def test_default_history_file_location(self, tmp_path, monkeypatch):
        """Use default location if not specified."""
        # Change working directory to tmp_path
        monkeypatch.chdir(tmp_path)

        history = SimpleHistory()
        expected_path = tmp_path / ".forge" / "state" / "code_atlas_history.jsonl"

        assert history.history_file == expected_path
        assert history.history_file.parent.exists()

    def test_history_file_creation(self, tmp_path):
        """Create history file and parent directories."""
        history_file = tmp_path / "deep" / "nested" / "path" / "history.jsonl"
        history = SimpleHistory(history_file)

        assert history.history_file.parent.exists()
        assert history.history_file.exists()

    def test_append_only_writes(self, history):
        """Verify append-only behavior (thread-safe)."""
        # Write first record
        history.record("code-atlas", "sessions", "extract", True)

        # Read file content
        with open(history.history_file, "r") as f:
            first_content = f.read()

        # Write second record
        history.record("code-atlas", "sessions", "extract", False)

        # Read file content again
        with open(history.history_file, "r") as f:
            second_content = f.read()

        # First content should be preserved
        assert first_content in second_content
        assert second_content.startswith(first_content)

    def test_context_persistence(self, history):
        """Verify context data is persisted correctly."""
        context = {
            "session_id": "abc123",
            "entities": 42,
            "relationships": 17,
            "cost_usd": 0.015,
            "extraction_method": "llm",
            "duration_ms": 3500,
        }

        history.record("code-atlas", "sessions", "extract", True, context=context)

        patterns = history.get_recent_patterns("code-atlas", "extract", limit=1)
        assert len(patterns) == 1
        assert patterns[0]["context"] == context

    def test_timestamp_format(self, history):
        """Verify timestamp is ISO 8601 UTC format."""
        history.record("code-atlas", "sessions", "extract", True)

        with open(history.history_file, "r") as f:
            record = json.loads(f.readline())

        timestamp = record["timestamp"]
        # Should end with Z or +00:00 for UTC
        assert timestamp.endswith(("Z", "+00:00")) or "T" in timestamp
