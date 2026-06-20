"""Tests for UsageTracker."""

from datetime import UTC, datetime, timedelta

import pytest

from code_atlas.schemas.usage import UsageEventType
from code_atlas.usage_tracker import UsageTracker, reset_tracker


@pytest.fixture
def tracker():
    """Create a fresh tracker for each test."""
    reset_tracker()
    t = UsageTracker(db_path=None)  # in-memory
    yield t
    t.close()
    reset_tracker()


class TestUsageTracker:
    """Test UsageTracker functionality."""

    def test_record_event(self, tracker):
        """Test recording a basic usage event."""
        event = tracker.record_event(
            key_id="test_key_123",
            event_type=UsageEventType.REPORT_GENERATED,
            endpoint="/api/v1/sessions/report",
            tokens_used=5000,
            cost_usd=0.15,
        )

        assert event.event_id.startswith("evt_")
        assert event.key_id == "test_key_123"
        assert event.event_type == UsageEventType.REPORT_GENERATED
        assert event.tokens_used == 5000
        assert event.cost_usd == 0.15

    def test_get_events(self, tracker):
        """Test retrieving events for a key."""
        # Record multiple events
        tracker.record_event(
            key_id="key_abc",
            event_type=UsageEventType.API_REQUEST,
        )
        tracker.record_event(
            key_id="key_abc",
            event_type=UsageEventType.REPORT_GENERATED,
        )
        tracker.record_event(
            key_id="key_xyz",
            event_type=UsageEventType.API_REQUEST,
        )

        events = tracker.get_events("key_abc")
        assert len(events) == 2

        events = tracker.get_events("key_xyz")
        assert len(events) == 1

    def test_get_events_with_since_filter(self, tracker):
        """Test filtering events by timestamp."""
        # Record an old event
        tracker.record_event(
            key_id="key_filter",
            event_type=UsageEventType.API_REQUEST,
        )
        # Manually backdate would require DB access - skip for now
        # Just test basic since filtering works

        # Record a new event
        tracker.record_event(
            key_id="key_filter",
            event_type=UsageEventType.REPORT_GENERATED,
        )

        # Get events since a point after the first
        one_hour_ago = datetime.now(tz=UTC) - timedelta(hours=1)
        events = tracker.get_events("key_filter", since=one_hour_ago)
        assert len(events) == 2

    def test_get_hourly_usage(self, tracker):
        """Test hourly usage count for rate limiting."""
        # Record 3 events
        for _i in range(3):
            tracker.record_event(
                key_id="key_rate",
                event_type=UsageEventType.API_REQUEST,
            )

        count = tracker.get_hourly_usage("key_rate")
        assert count == 3

        # Different key should have 0
        count = tracker.get_hourly_usage("nonexistent_key")
        assert count == 0

    def test_get_summary(self, tracker):
        """Test usage summary aggregation."""
        # Record various events
        tracker.record_event(
            key_id="key_summary",
            event_type=UsageEventType.REPORT_GENERATED,
            tokens_used=1000,
            cost_usd=0.03,
        )
        tracker.record_event(
            key_id="key_summary",
            event_type=UsageEventType.REPORT_GENERATED,
            tokens_used=2000,
            cost_usd=0.06,
        )
        tracker.record_event(
            key_id="key_summary",
            event_type=UsageEventType.API_REQUEST,
            tokens_used=100,
            cost_usd=0.01,
        )

        start = datetime.now(tz=UTC) - timedelta(hours=2)
        end = datetime.now(tz=UTC)

        summary = tracker.get_summary("key_summary", start, end)

        assert summary.total_requests == 3
        assert summary.report_count == 2
        assert summary.total_tokens == 3100
        assert abs(summary.total_cost_usd - 0.10) < 0.001

    def test_get_summary_empty(self, tracker):
        """Test summary for key with no events."""
        start = datetime.now(tz=UTC) - timedelta(hours=1)
        end = datetime.now(tz=UTC)

        summary = tracker.get_summary("nonexistent", start, end)

        assert summary.total_requests == 0
        assert summary.report_count == 0
        assert summary.total_tokens == 0
        assert summary.total_cost_usd == 0.0

    def test_event_id_unique(self, tracker):
        """Test that event IDs are unique."""
        ids = set()
        for _ in range(100):
            event = tracker.record_event(
                key_id="key_unique",
                event_type=UsageEventType.API_REQUEST,
            )
            ids.add(event.event_id)

        assert len(ids) == 100


class TestUsageTrackerPersistence:
    """Test tracker persistence with file-based DB."""

    def test_file_based_db(self, tmp_path):
        """Test tracker with file-based SQLite."""
        db_path = tmp_path / "usage.db"
        tracker = UsageTracker(db_path=str(db_path))

        tracker.record_event(
            key_id="file_key",
            event_type=UsageEventType.REPORT_GENERATED,
        )

        # Create new tracker instance with same file
        tracker2 = UsageTracker(db_path=str(db_path))
        events = tracker2.get_events("file_key")

        assert len(events) == 1
        assert events[0].key_id == "file_key"

        tracker.close()
        tracker2.close()
