"""Tests for session chunking functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from code_atlas.insight_extractor import (
    Entity,
    ExtractionResult,
    InsightExtractor,
    Relationship,
)
from code_atlas.models import ParsedSession, SessionMessage, SessionMetadata


def make_message(message_id: str, text_size: int = 100) -> SessionMessage:
    """Create a test message with specified text size."""
    return SessionMessage(
        message_id=message_id,
        role="user",
        text="X" * text_size,  # Simple repeated character
    )


def make_session(
    session_id: str = "sess-123", message_count: int = 1, message_size: int = 100
) -> ParsedSession:
    """Create a test session with configurable message count and size."""
    metadata = SessionMetadata(
        path=Path(__file__),
        session_id=session_id,
        project="test-project",
        size_bytes=1024,
        modified_at=datetime.now(tz=UTC),
    )
    messages = [make_message(f"m{i}", text_size=message_size) for i in range(message_count)]
    return ParsedSession(
        metadata=metadata,
        messages=messages,
        total_tokens=message_size * message_count // 4,
        referenced_files=["test.py"],
    )


def test_estimate_tokens() -> None:
    """Test token estimation accuracy."""
    extractor = InsightExtractor(use_llm=False)

    # Test various text lengths
    assert extractor._estimate_tokens("X" * 100) == 25  # 100 / 4
    assert extractor._estimate_tokens("X" * 400) == 100  # 400 / 4
    assert extractor._estimate_tokens("X" * 1000) == 250  # 1000 / 4


def test_chunk_session_small() -> None:
    """Test that small sessions return a single chunk."""
    extractor = InsightExtractor(use_llm=False)

    # Create small session (10 messages * 100 chars = 1000 chars ~250 tokens)
    session = make_session(message_count=10, message_size=100)

    chunks = extractor._chunk_session(session, max_tokens=12000)

    # Should return single chunk with all messages
    assert len(chunks) == 1
    assert len(chunks[0]) == 10
    assert chunks[0] == session.messages


def test_chunk_session_large() -> None:
    """Test that large sessions are split into multiple chunks."""
    extractor = InsightExtractor(use_llm=False)

    # Create large session (100 messages * 2000 chars = 200,000 chars ~50,000 tokens)
    session = make_session(message_count=100, message_size=2000)

    chunks = extractor._chunk_session(session, max_tokens=12000)

    # Should create multiple chunks
    assert len(chunks) > 1

    # Each chunk should be within token limit (approximately)
    for chunk in chunks:
        chunk_tokens = sum(extractor._estimate_tokens(msg.text) for msg in chunk)
        # Allow some overflow due to overlap
        assert chunk_tokens <= 15000  # 12000 + 3000 buffer for overlap


def test_chunk_overlap_preserved() -> None:
    """Test that chunks have 2-message overlap for context."""
    extractor = InsightExtractor(use_llm=False)

    # Create session with distinct messages to track overlap
    messages = [
        SessionMessage(message_id=f"m{i}", role="user", text=f"Message {i}" * 500)
        for i in range(20)
    ]
    session = ParsedSession(
        metadata=SessionMetadata(
            path=Path(__file__),
            session_id="sess-overlap",
            project="test",
            size_bytes=1024,
            modified_at=datetime.now(tz=UTC),
        ),
        messages=messages,
        total_tokens=10000,
        referenced_files=[],
    )

    chunks = extractor._chunk_session(session, max_tokens=5000)

    # Verify we have multiple chunks
    assert len(chunks) > 1

    # Verify overlap between consecutive chunks
    for i in range(len(chunks) - 1):
        current_chunk = chunks[i]
        next_chunk = chunks[i + 1]

        # Next chunk should start with last messages from current chunk (up to 2)
        overlap_size = min(2, len(current_chunk))
        if overlap_size > 0:
            # Check that the last message IDs from current chunk
            # appear at the start of next chunk
            current_end_ids = [msg.message_id for msg in current_chunk[-overlap_size:]]
            next_start_ids = [msg.message_id for msg in next_chunk[:overlap_size]]

            assert current_end_ids == next_start_ids


def test_format_chunk() -> None:
    """Test chunk formatting for LLM prompt."""
    extractor = InsightExtractor(use_llm=False)

    messages = [
        SessionMessage(message_id="m1", role="user", text="First message" * 50),
        SessionMessage(message_id="m2", role="assistant", text="Second message" * 50),
    ]

    formatted = extractor._format_chunk(messages)

    # Verify prompt structure
    assert "Extract structured knowledge" in formatted
    assert "USER:" in formatted
    assert "ASSISTANT:" in formatted
    assert "First message" in formatted
    assert "Second message" in formatted


def test_merge_extractions_deduplicates_entities() -> None:
    """Test that merging deduplicates entities by (type, name)."""
    extractor = InsightExtractor(use_llm=False)

    result1 = ExtractionResult(
        entities=[
            Entity(type="file", name="test.py", confidence=0.8),
            Entity(type="concept", name="authentication", confidence=0.9),
        ],
        relationships=[],
        insights=["Insight 1"],
        estimated_cost_usd=0.01,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    result2 = ExtractionResult(
        entities=[
            Entity(type="file", name="test.py", confidence=0.95),  # Higher confidence
            Entity(type="concept", name="authorization", confidence=0.85),
        ],
        relationships=[],
        insights=["Insight 2"],
        estimated_cost_usd=0.02,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    merged = extractor._merge_extractions([result1, result2])

    # Should have 3 unique entities (test.py, authentication, authorization)
    assert len(merged.entities) == 3

    # test.py should have higher confidence from result2
    test_py = [e for e in merged.entities if e.name == "test.py"][0]
    assert test_py.confidence == 0.95

    # Total cost should be sum
    assert merged.estimated_cost_usd == pytest.approx(0.03, abs=1e-6)


def test_merge_extractions_deduplicates_relationships() -> None:
    """Test that merging deduplicates relationships by (source, target, type)."""
    extractor = InsightExtractor(use_llm=False)

    result1 = ExtractionResult(
        entities=[],
        relationships=[
            Relationship(type="USES", source="A", target="B", confidence=0.7),
            Relationship(type="CONTAINS", source="C", target="D", confidence=0.8),
        ],
        insights=[],
        estimated_cost_usd=0.01,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    result2 = ExtractionResult(
        entities=[],
        relationships=[
            Relationship(type="USES", source="A", target="B", confidence=0.9),  # Higher
            Relationship(type="IMPLEMENTS", source="E", target="F", confidence=0.85),
        ],
        insights=[],
        estimated_cost_usd=0.02,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    merged = extractor._merge_extractions([result2, result1])

    # Should have 3 unique relationships
    assert len(merged.relationships) == 3

    # A->B relationship should have higher confidence
    uses_rel = [r for r in merged.relationships if r.type == "USES"][0]
    assert uses_rel.confidence == 0.9


def test_merge_extractions_deduplicates_insights() -> None:
    """Test that merging deduplicates insights."""
    extractor = InsightExtractor(use_llm=False)

    result1 = ExtractionResult(
        entities=[],
        relationships=[],
        insights=["Insight A", "Insight B", "Insight A"],  # Duplicate
        estimated_cost_usd=0.01,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    result2 = ExtractionResult(
        entities=[],
        relationships=[],
        insights=["Insight B", "Insight C"],  # Duplicate B
        estimated_cost_usd=0.02,
        extracted_at=datetime.now(tz=UTC).isoformat(),
        extractor_model="test",
        extraction_method="llm",
    )

    merged = extractor._merge_extractions([result1, result2])

    # Should have 3 unique insights (A, B, C)
    assert len(merged.insights) == 3
    assert set(merged.insights) == {"Insight A", "Insight B", "Insight C"}


def test_merge_extractions_empty() -> None:
    """Test merging empty results list."""
    extractor = InsightExtractor(use_llm=False)

    merged = extractor._merge_extractions([])

    assert len(merged.entities) == 0
    assert len(merged.relationships) == 0
    assert len(merged.insights) == 0
    assert merged.estimated_cost_usd == 0.0


def test_large_session_triggers_chunking() -> None:
    """Test that large sessions automatically trigger chunking."""
    extractor = InsightExtractor(use_llm=True, provider="anthropic")
    extractor.client = Mock()
    extractor.provider = "anthropic"  # Reset after __post_init__ clears it (no API key in test)

    # Create large session (>12K tokens)
    # 60 messages * 1000 chars = 60,000 chars ~15,000 tokens
    session = make_session(message_count=60, message_size=1000)

    # Mock API responses for each chunk
    mock_response = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.content = [
        Mock(
            type="text",
            text='{"entities": [{"type": "file", "name": "test.py"}], '
            '"relationships": [], "insights": ["test"]}',
        )
    ]
    extractor.client.messages.create.return_value = mock_response

    result = extractor._call_llm_with_retry(session)

    # Verify result was returned
    assert result is not None
    assert result.extraction_method == "llm"

    # Verify API was called multiple times (once per chunk)
    assert extractor.client.messages.create.call_count > 1


def test_small_session_no_chunking() -> None:
    """Test that small sessions do not trigger chunking."""
    extractor = InsightExtractor(use_llm=True, provider="anthropic")
    extractor.client = Mock()
    extractor.provider = "anthropic"  # Reset after __post_init__ clears it (no API key in test)

    # Create small session (<12K tokens)
    # 5 messages * 200 chars = 1,000 chars ~250 tokens
    session = make_session(message_count=5, message_size=200)

    # Mock API response
    mock_response = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.content = [
        Mock(type="text", text='{"entities": [], "relationships": [], "insights": []}')
    ]
    extractor.client.messages.create.return_value = mock_response

    result = extractor._call_llm_with_retry(session)

    # Verify result was returned
    assert result is not None

    # Verify API was called exactly once (no chunking)
    assert extractor.client.messages.create.call_count == 1
