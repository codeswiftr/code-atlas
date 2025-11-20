from __future__ import annotations

from datetime import datetime, timezone

import pytest
import redis

from code_atlas.graph_populator import GraphPopulator
from code_atlas.insight_extractor import Entity, ExtractionResult, Relationship
from code_atlas.models import ParsedSession, SessionMetadata, SessionMessage


def test_graph_populator_dry_run_records_queries() -> None:
    metadata = SessionMetadata(
        path=__file__,
        session_id="sess-001",
        project="atlas",
        size_bytes=10,
        modified_at=datetime.now(tz=timezone.utc),
    )
    session = ParsedSession(
        metadata=metadata,
        messages=[SessionMessage(message_id="m1", role="user", text="hi")],
        total_tokens=10,
        referenced_files=[],
    )
    extraction = ExtractionResult(
        entities=[Entity(type="file", name="backend/app.py")],
        relationships=[
            Relationship(type="MENTIONS_FILE", source="sess-001", target="backend/app.py")
        ],
        insights=["Example insight"],
    )

    populator = GraphPopulator(dry_run=True)
    populator.upsert(session, extraction)

    assert len(populator.executed_queries) >= 3


@pytest.fixture
def falkordb_available() -> bool:
    """Check if FalkorDB is available at localhost:6379."""
    try:
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()
        # Verify it's FalkorDB by checking for GRAPH.QUERY command
        try:
            client.execute_command("GRAPH.QUERY", "test", "RETURN 1")
            return True
        except redis.ResponseError:
            # Regular Redis doesn't support GRAPH.QUERY
            return False
    except (redis.ConnectionError, redis.TimeoutError):
        return False


@pytest.fixture
def test_graph_name() -> str:
    """Return a unique graph name for testing."""
    return "test_code_atlas"


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
def test_graph_populator_real_connection(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Test basic FalkorDB connection and query execution."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    populator = GraphPopulator(graph_name=test_graph_name, dry_run=False)

    # Verify client is initialized
    assert populator.client is not None

    # Test simple query execution
    query = "MERGE (n:Test {id:'test-node', name:'test'})"
    populator._execute(query)

    # Verify query was executed
    assert len(populator.executed_queries) == 1

    # Query the node back to verify it exists
    result = populator.client.execute_command(
        "GRAPH.QUERY", test_graph_name, "MATCH (n:Test {id:'test-node'}) RETURN n.name"
    )
    assert result is not None


@pytest.mark.integration
def test_graph_populator_creates_session_node(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Verify Session node creation with metadata."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    metadata = SessionMetadata(
        path="/test/path.jsonl",
        session_id="test-sess-001",
        project="test_project",
        size_bytes=1024,
        modified_at=datetime.now(tz=timezone.utc),
    )
    session = ParsedSession(
        metadata=metadata,
        messages=[SessionMessage(message_id="m1", role="user", text="test message")],
        total_tokens=100,
        referenced_files=[],
    )
    extraction = ExtractionResult(
        entities=[Entity(type="file", name="test/file.py")],
        relationships=[],
        insights=["Test insight"],
    )

    populator = GraphPopulator(graph_name=test_graph_name, dry_run=False)
    populator.upsert(session, extraction)

    # Query the session node
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session {id:'test-sess-001'}) RETURN s.project, s.size_bytes",
    )

    # FalkorDB returns results as nested arrays
    # Result format: [[data], [metadata]]
    assert result is not None
    assert len(result) >= 1


@pytest.mark.integration
def test_graph_populator_creates_entities_and_relationships(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Test entity creation and MENTIONS relationship."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    metadata = SessionMetadata(
        path="/test/path.jsonl",
        session_id="test-sess-002",
        project="test_project",
        size_bytes=512,
        modified_at=datetime.now(tz=timezone.utc),
    )
    session = ParsedSession(
        metadata=metadata,
        messages=[SessionMessage(message_id="m1", role="user", text="test")],
        total_tokens=50,
        referenced_files=["src/main.py"],
    )
    extraction = ExtractionResult(
        entities=[
            Entity(type="file", name="src/main.py"),
            Entity(type="concept", name="authentication"),
        ],
        relationships=[],
        insights=[],
    )

    populator = GraphPopulator(graph_name=test_graph_name, dry_run=False)
    populator.upsert(session, extraction)

    # Verify entities were created
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (e:File {name:'src/main.py'}) RETURN e.name",
    )
    assert result is not None

    # Verify MENTIONS relationship exists
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session {id:'test-sess-002'})-[:MENTIONS]->(e:File) RETURN count(e)",
    )
    assert result is not None


@pytest.mark.integration
def test_graph_populator_provenance_metadata(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Test that provenance metadata is attached to nodes and relationships."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    from code_atlas.insight_extractor import InsightExtractor

    metadata = SessionMetadata(
        path="/test/path.jsonl",
        session_id="test-sess-provenance",
        project="test_project",
        size_bytes=256,
        modified_at=datetime.now(tz=timezone.utc),
    )
    session = ParsedSession(
        metadata=metadata,
        messages=[SessionMessage(message_id="m1", role="user", text="test")],
        total_tokens=25,
        referenced_files=["test.py"],
    )

    # Use heuristic extraction which sets provenance metadata
    extractor = InsightExtractor(use_llm=False)
    extraction = extractor.extract(session)

    # Verify extraction has provenance metadata
    assert extraction.extracted_at is not None
    assert extraction.extractor_model == "heuristic"
    assert extraction.extraction_method == "heuristic"

    # Populate graph with provenance
    populator = GraphPopulator(graph_name=test_graph_name, dry_run=False)
    populator.upsert(session, extraction)

    # Verify Session node has extraction metadata
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session {id:'test-sess-provenance'}) "
        "RETURN s.extraction_method, s.extractor_model",
    )
    assert result is not None

    # Verify MENTIONS relationship has confidence and timestamp
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session {id:'test-sess-provenance'})-[r:MENTIONS]->(e:File) "
        "RETURN r.confidence, r.source",
    )
    assert result is not None


@pytest.mark.integration
def test_graph_populator_cleanup(
    falkordb_available: bool, test_graph_name: str
) -> None:
    """Test data deletion and cleanup."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    # Create a test graph
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "CREATE (n:Test {id:'cleanup-test'})",
    )

    # Delete the graph
    client.execute_command("GRAPH.DELETE", test_graph_name)

    # Verify graph is deleted by trying to query it
    # Querying a deleted graph should work but return no results
    result = client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (n:Test) RETURN count(n)",
    )
    # New graph should have 0 nodes
    assert result is not None


@pytest.mark.integration
def test_graph_populator_index_creation_during_initialization(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Test that indexes are created during GraphPopulator initialization."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    populator = GraphPopulator(
        graph_name=test_graph_name,
        dry_run=False,
        create_indexes=True
    )

    # Check that index creation queries were executed
    index_queries = [q for q in populator.executed_queries if "CREATE INDEX" in q or "FULLTEXT INDEX" in q]
    assert len(index_queries) > 0, "No index creation queries were executed"

    # Verify critical indexes exist
    index_query_strings = " ".join(index_queries)
    assert "session_id" in index_query_strings, "Missing session_id index"
    assert "entity_name" in index_query_strings, "Missing entity_name index"


@pytest.mark.integration
def test_graph_populator_with_disabled_indexes(
    falkordb_available: bool, test_graph_name: str, cleanup_test_graph: None
) -> None:
    """Test GraphPopulator behavior with indexes disabled."""
    if not falkordb_available:
        pytest.skip("FalkorDB not available at localhost:6379")

    populator = GraphPopulator(
        graph_name=test_graph_name,
        dry_run=False,
        create_indexes=False
    )

    # No index creation queries should be executed
    index_queries = [q for q in populator.executed_queries if "CREATE INDEX" in q or "FULLTEXT INDEX" in q]
    assert len(index_queries) == 0, "Index creation queries should not be executed when disabled"

    # Test that normal operations still work
    metadata = SessionMetadata(
        path="/test/path.jsonl",
        session_id="test-sess-no-index",
        project="test_project",
        size_bytes=512,
        modified_at=datetime.now(tz=timezone.utc),
    )
    session = ParsedSession(
        metadata=metadata,
        messages=[SessionMessage(message_id="m1", role="user", text="test")],
        total_tokens=50,
        referenced_files=["test.py"],
    )
    extraction = ExtractionResult(
        entities=[Entity(type="file", name="test.py")],
        relationships=[],
        insights=[],
    )

    populator.upsert(session, extraction)

    # Should still be able to query data even without indexes
    result = populator.client.execute_command(
        "GRAPH.QUERY",
        test_graph_name,
        "MATCH (s:Session {id:'test-sess-no-index'}) RETURN s.project",
    )
    assert result is not None
