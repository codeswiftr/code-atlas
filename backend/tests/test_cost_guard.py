"""Tests for cost guard functionality."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from code_atlas.config import AtlasSettings
from code_atlas.exceptions import CostLimitExceeded
from code_atlas.insight_extractor import CostGuard, InsightExtractor
from code_atlas.models import ParsedSession, SessionMetadata, SessionMessage
from code_atlas.pipeline import PipelineRunner
from code_atlas.session_discovery import SessionDiscovery


def make_session(session_id: str = "sess-123", message_count: int = 1) -> ParsedSession:
    """Create a test session with configurable message count."""
    metadata = SessionMetadata(
        path=Path(__file__),
        session_id=session_id,
        project="test-project",
        size_bytes=1024,
        modified_at=datetime.now(tz=timezone.utc),
    )
    messages = [
        SessionMessage(
            message_id=f"m{i}",
            role="user",
            text="Test message " * 50,  # Make messages reasonably sized
        )
        for i in range(message_count)
    ]
    return ParsedSession(
        metadata=metadata,
        messages=messages,
        total_tokens=50 * message_count,
        referenced_files=["test.py"],
    )


def test_cost_guard_session_limit() -> None:
    """Test that CostGuard prevents extraction when session limit exceeded."""
    cost_guard = CostGuard(max_session=0.001, max_cumulative=1.0)

    # Check a cost that's under the limit
    assert cost_guard.check_session(0.0005) is True

    # Check a cost that equals the limit
    assert cost_guard.check_session(0.001) is True

    # Check a cost that exceeds the limit
    assert cost_guard.check_session(0.002) is False


def test_cost_guard_cumulative_limit() -> None:
    """Test that CostGuard raises exception when cumulative limit exceeded."""
    cost_guard = CostGuard(max_session=0.01, max_cumulative=0.05)

    # Record costs that are under the limit
    cost_guard.record(0.01)
    assert cost_guard.cumulative == 0.01

    cost_guard.record(0.02)
    assert cost_guard.cumulative == 0.03

    # Record a cost that would exceed the cumulative limit
    with pytest.raises(CostLimitExceeded) as exc_info:
        cost_guard.record(0.03)  # Total would be 0.06 > 0.05

    assert exc_info.value.current_cost == 0.06
    assert exc_info.value.limit == 0.05
    assert exc_info.value.limit_type == "cumulative"


def test_cost_guard_tracks_accurately() -> None:
    """Test that CostGuard accurately tracks cumulative costs."""
    cost_guard = CostGuard(max_session=0.01, max_cumulative=1.0)

    costs = [0.001, 0.002, 0.003, 0.004]
    for cost in costs:
        cost_guard.record(cost)

    expected_total = sum(costs)
    assert cost_guard.cumulative == pytest.approx(expected_total, abs=1e-6)


def test_extractor_respects_session_cost_limit() -> None:
    """Test that InsightExtractor raises CostLimitExceeded for expensive sessions."""
    # Create a cost guard with very low session limit
    cost_guard = CostGuard(max_session=0.00001, max_cumulative=1.0)

    # Create extractor with mocked client (use_llm=True, provider=anthropic for LLM path)
    extractor = InsightExtractor(use_llm=True, provider="anthropic")
    extractor.client = Mock()  # Mock client to enable LLM path
    extractor.cost_guard = cost_guard

    session = make_session(message_count=10)  # Large session

    # Should raise CostLimitExceeded before making API call
    with pytest.raises(CostLimitExceeded) as exc_info:
        extractor._call_llm(session)

    # Verify the exception details
    assert exc_info.value.limit_type == "session"
    assert exc_info.value.limit == 0.00001
    assert exc_info.value.current_cost > 0.00001

    # Verify API was never called
    extractor.client.messages.create.assert_not_called()


def test_extractor_records_cost_after_extraction() -> None:
    """Test that InsightExtractor records actual cost with cost guard."""
    cost_guard = CostGuard(max_session=1.0, max_cumulative=10.0)

    extractor = InsightExtractor(use_llm=True, provider="anthropic")
    extractor.client = Mock()
    extractor.cost_guard = cost_guard

    session = make_session()

    # Mock successful API response
    mock_response = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.content = [
        Mock(type="text", text='{"entities": [], "relationships": [], "insights": []}')
    ]
    extractor.client.messages.create.return_value = mock_response

    # Extract
    result = extractor._call_llm(session)

    # Verify cost was recorded
    assert cost_guard.cumulative > 0
    assert cost_guard.cumulative == pytest.approx(result.estimated_cost_usd, abs=1e-6)


def test_extractor_falls_back_on_cost_limit() -> None:
    """Test that extract() falls back to heuristics when cost limit hit."""
    cost_guard = CostGuard(max_session=0.00001, max_cumulative=1.0)

    extractor = InsightExtractor(use_llm=False)
    extractor.client = Mock()  # Enable LLM path
    extractor.cost_guard = cost_guard

    session = make_session(message_count=10)

    # Should fall back to heuristic extraction
    result = extractor.extract(session)

    # Verify heuristic extraction was used
    assert result.extraction_method == "heuristic"
    assert result.extractor_model == "heuristic"

    # Verify API was never called
    extractor.client.messages.create.assert_not_called()


def test_pipeline_initializes_cost_guard() -> None:
    """Test that PipelineRunner initializes cost guard from settings."""
    settings = AtlasSettings(
        max_cost_per_session_usd=0.05,
        max_cumulative_cost_usd=5.0,
    )

    # Create extractor with LLM enabled (required for cost guard initialization)
    extractor = InsightExtractor(use_llm=True, provider="anthropic")
    extractor.client = Mock()  # Mock client

    # Create minimal pipeline
    discovery = Mock(spec=SessionDiscovery)
    populator = Mock()

    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
        settings=settings,
    )

    # Verify cost guard was initialized
    assert runner.extractor.cost_guard is not None
    assert runner.extractor.cost_guard.max_session == 0.05
    assert runner.extractor.cost_guard.max_cumulative == 5.0


def test_pipeline_without_settings() -> None:
    """Test that pipeline works without settings (no cost guard)."""
    extractor = InsightExtractor(use_llm=False)
    extractor.client = Mock()

    discovery = Mock(spec=SessionDiscovery)
    populator = Mock()

    runner = PipelineRunner(
        discovery=discovery,
        extractor=extractor,
        populator=populator,
        settings=None,  # No settings
    )

    # Verify no cost guard was initialized
    assert runner.extractor.cost_guard is None


def test_cost_guard_zero_limits() -> None:
    """Test cost guard behavior with zero limits."""
    cost_guard = CostGuard(max_session=0.0, max_cumulative=0.0)

    # Any non-zero cost should fail session check
    assert cost_guard.check_session(0.0) is True
    assert cost_guard.check_session(0.0001) is False

    # Any recording should raise exception
    with pytest.raises(CostLimitExceeded):
        cost_guard.record(0.0001)


def test_estimate_session_cost() -> None:
    """Test that cost estimation is reasonably accurate."""
    extractor = InsightExtractor(use_llm=False)

    # Create sessions of different sizes
    small_session = make_session(message_count=1)
    large_session = make_session(message_count=20)

    small_cost = extractor._estimate_session_cost(small_session)
    large_cost = extractor._estimate_session_cost(large_session)

    # Larger session should have higher estimated cost
    assert large_cost > small_cost

    # Costs should be reasonable (not negative, not absurdly high)
    assert small_cost > 0
    assert small_cost < 0.1  # Less than 10 cents
    assert large_cost < 1.0  # Less than $1
