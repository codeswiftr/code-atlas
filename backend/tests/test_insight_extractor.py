from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from anthropic import APIError
from pydantic import ValidationError

from code_atlas.insight_extractor import (
    CLAUDE_HAIKU_INPUT_COST,
    CLAUDE_HAIKU_OUTPUT_COST,
    CLAUDE_SONNET_INPUT_COST,
    CLAUDE_SONNET_OUTPUT_COST,
    Entity,
    ExtractionResult,
    InsightExtractor,
    Relationship,
)
from code_atlas.models import ParsedSession, SessionMetadata, SessionMessage


def make_session() -> ParsedSession:
    metadata = SessionMetadata(
        path=__file__,
        session_id="sess-123",
        project="alpha",
        size_bytes=1024,
        modified_at=datetime.now(tz=timezone.utc),
    )
    messages = [
        SessionMessage(
            message_id="m1",
            role="user",
            text="Please update backend/app.py for better logging",
        )
    ]
    return ParsedSession(
        metadata=metadata,
        messages=messages,
        total_tokens=50,
        referenced_files=["backend/app.py"],
    )


def test_insight_extractor_heuristic() -> None:
    session = make_session()
    extractor = InsightExtractor(use_llm=False)

    result = extractor.extract(session)

    assert len(result.entities) == 1
    assert result.entities[0].type == "file"
    assert result.entities[0].confidence == 1.0
    assert result.relationships == []
    assert any("50 tokens" in insight for insight in result.insights)
    assert result.extraction_method == "heuristic"
    assert result.extractor_model == "heuristic"


def test_cost_calculation_sonnet() -> None:
    """Test accurate cost calculation for Sonnet model."""
    extractor = InsightExtractor(model="claude-3-5-sonnet-latest", use_llm=False)

    # Test with known token counts
    input_tokens = 1000
    output_tokens = 500

    cost = extractor._calculate_cost(input_tokens, output_tokens)

    # Expected: (1000/1M * $3) + (500/1M * $15) = $0.003 + $0.0075 = $0.0105
    expected_cost = (input_tokens / 1_000_000 * CLAUDE_SONNET_INPUT_COST) + (
        output_tokens / 1_000_000 * CLAUDE_SONNET_OUTPUT_COST
    )

    assert cost == pytest.approx(expected_cost, abs=1e-6)
    assert cost == pytest.approx(0.0105, abs=1e-6)


def test_cost_calculation_haiku() -> None:
    """Test accurate cost calculation for Haiku model."""
    extractor = InsightExtractor(model="claude-3-haiku-latest", use_llm=False)

    # Test with known token counts
    input_tokens = 10000
    output_tokens = 2000

    cost = extractor._calculate_cost(input_tokens, output_tokens)

    # Expected: (10000/1M * $0.25) + (2000/1M * $1.25) = $0.0025 + $0.0025 = $0.005
    expected_cost = (input_tokens / 1_000_000 * CLAUDE_HAIKU_INPUT_COST) + (
        output_tokens / 1_000_000 * CLAUDE_HAIKU_OUTPUT_COST
    )

    assert cost == pytest.approx(expected_cost, abs=1e-6)
    assert cost == pytest.approx(0.005, abs=1e-6)


def test_schema_validation_success() -> None:
    """Test successful schema validation with valid data."""
    extractor = InsightExtractor(use_llm=False)

    valid_data = {
        "entities": [
            {"type": "file", "name": "test.py", "confidence": 0.95},
            {"type": "concept", "name": "authentication", "confidence": 0.8},
        ],
        "relationships": [
            {"type": "USES", "source": "test.py", "target": "authentication", "confidence": 0.9}
        ],
        "insights": ["Test session analyzed successfully", "2 entities extracted"],
    }

    result = extractor._validate_schema(valid_data)

    assert len(result.entities) == 2
    assert result.entities[0].type == "file"
    assert result.entities[0].confidence == 0.95
    assert len(result.relationships) == 1
    assert result.relationships[0].type == "USES"
    assert len(result.insights) == 2


def test_schema_validation_invalid_entity() -> None:
    """Test schema validation fails with invalid entity type."""
    extractor = InsightExtractor(use_llm=False)

    invalid_data = {
        "entities": [
            {"type": "invalid_type", "name": "test.py"}  # Invalid entity type
        ],
        "relationships": [],
        "insights": [],
    }

    with pytest.raises(ValidationError):
        extractor._validate_schema(invalid_data)


def test_schema_validation_missing_fields() -> None:
    """Test schema validation fails with missing required fields."""
    extractor = InsightExtractor(use_llm=False)

    invalid_data = {
        "entities": [
            {"type": "file"}  # Missing 'name' field
        ],
        "relationships": [],
        "insights": [],
    }

    with pytest.raises(ValidationError):
        extractor._validate_schema(invalid_data)


def test_schema_validation_invalid_insights() -> None:
    """Test schema validation fails with non-string insights."""
    extractor = InsightExtractor(use_llm=False)

    invalid_data = {
        "entities": [],
        "relationships": [],
        "insights": ["valid insight", 123, None],  # Contains non-strings
    }

    # ValueError for custom validation, ValidationError for Pydantic validation
    with pytest.raises(ValueError, match="Invalid extraction schema"):
        extractor._validate_schema(invalid_data)


@patch("code_atlas.insight_extractor.time.sleep")  # Mock sleep to speed up test
def test_retry_logic_success_after_failure(mock_sleep: Mock) -> None:
    """Test retry logic succeeds after initial API failures."""
    extractor = InsightExtractor(use_llm=False)
    extractor.client = Mock()  # Mock Anthropic client

    session = make_session()

    # Mock API to fail twice, then succeed
    mock_response = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.content = [
        Mock(
            type="text",
            text='{"entities": [], "relationships": [], "insights": ["test"]}',
        )
    ]

    # Use generic APIError for testing (constructor is complex)
    extractor.client.messages.create.side_effect = [
        APIError("Rate limit", body=None, request=Mock()),  # First attempt fails
        APIError("Temporary error", body=None, request=Mock()),  # Second attempt fails
        mock_response,  # Third attempt succeeds
    ]

    result = extractor._call_llm_with_retry(session)

    # Verify retries occurred
    assert extractor.client.messages.create.call_count == 3
    assert mock_sleep.call_count == 2  # Slept before 2nd and 3rd attempts

    # Verify exponential backoff (1s, 2s)
    mock_sleep.assert_any_call(1)
    mock_sleep.assert_any_call(2)

    # Verify result
    assert result is not None
    assert result.extraction_method == "llm"


@patch("code_atlas.insight_extractor.time.sleep")
def test_retry_logic_max_retries_exceeded(mock_sleep: Mock) -> None:
    """Test retry logic raises after max retries."""
    extractor = InsightExtractor(use_llm=False)
    extractor.client = Mock()

    session = make_session()

    # Mock API to always fail
    api_error = APIError("Persistent error", body=None, request=Mock())
    extractor.client.messages.create.side_effect = api_error

    with pytest.raises(APIError):
        extractor._call_llm_with_retry(session, max_retries=3)

    # Verify all retries attempted
    assert extractor.client.messages.create.call_count == 3
    assert mock_sleep.call_count == 2  # Slept before 2nd and 3rd attempts


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping real API test",
)
def test_insight_extractor_llm_real_api() -> None:
    """Test real Anthropic API integration with minimal cost."""
    session = make_session()

    # Use Haiku for cost efficiency
    extractor = InsightExtractor(model="claude-3-haiku-20240307", use_llm=True)

    result = extractor.extract(session)

    # Verify extraction succeeded
    assert result is not None
    assert result.extraction_method == "llm"
    assert result.extractor_model == "claude-3-haiku-20240307"
    assert result.extracted_at is not None

    # Verify cost tracking
    assert result.estimated_cost_usd > 0
    assert result.estimated_cost_usd < 0.01  # Should be well under 1 cent

    # Verify schema compliance (entities and relationships validated)
    for entity in result.entities:
        assert isinstance(entity, Entity)
        assert 0.0 <= entity.confidence <= 1.0

    for rel in result.relationships:
        assert isinstance(rel, Relationship)
        assert 0.0 <= rel.confidence <= 1.0

    # Print cost for visibility
    print(f"\n✅ Real API test completed. Cost: ${result.estimated_cost_usd:.6f}")


def test_extraction_provenance_metadata() -> None:
    """Test that provenance metadata is set correctly."""
    session = make_session()
    extractor = InsightExtractor(use_llm=False)

    result = extractor.extract(session)

    # Verify provenance metadata
    assert result.extracted_at is not None
    assert result.extractor_model == "heuristic"
    assert result.extraction_method == "heuristic"

    # Verify timestamp is recent (within last minute)
    from datetime import datetime, timezone

    extracted_time = datetime.fromisoformat(result.extracted_at)
    now = datetime.now(tz=timezone.utc)
    time_diff = (now - extracted_time).total_seconds()

    assert time_diff < 60  # Extracted within last minute
