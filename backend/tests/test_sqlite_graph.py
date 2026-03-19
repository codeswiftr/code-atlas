"""Tests for SQLiteGraphStore and get_graph_store factory.

Coverage targets:
- Node CRUD (add, get, delete)
- Edge CRUD (add, delete)
- Neighbor traversal (outgoing, incoming, both, edge-type filter)
- Search filtering (by type, by name, by both)
- execute_query: count, node match, edge match, WHERE/LIMIT/SKIP
- Factory function: SQLite default, GRAPH_BACKEND overrides
- Protocol conformance
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from code_atlas.graph import SQLiteGraphStore, get_graph_store
from code_atlas.graph.interface import GraphStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def store(tmp_path):
    """Isolated in-memory (tmp) SQLite graph store."""
    db = SQLiteGraphStore(db_path=str(tmp_path / "test_graph.db"))
    await db.initialize()
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


def test_sqlite_graph_store_implements_protocol(tmp_path):
    db = SQLiteGraphStore(db_path=str(tmp_path / "proto.db"))
    assert isinstance(db, GraphStore), "SQLiteGraphStore must satisfy the GraphStore protocol"


# ---------------------------------------------------------------------------
# 2. Node CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_node_returns_id(store):
    node_id = await store.add_node("Session", {"id": "s1", "name": "My Session"})
    assert node_id == "s1"


@pytest.mark.asyncio
async def test_add_node_auto_generates_id_when_missing(store):
    node_id = await store.add_node("Concept", {"name": "Redis"})
    assert node_id  # non-empty string


@pytest.mark.asyncio
async def test_get_node_returns_correct_data(store):
    await store.add_node("File", {"id": "f1", "name": "app.py", "language": "python"})
    node = await store.get_node("f1")
    assert node is not None
    assert node["id"] == "f1"
    assert node["name"] == "app.py"
    assert node["node_type"] == "File"
    assert node["language"] == "python"


@pytest.mark.asyncio
async def test_get_node_returns_none_for_missing(store):
    result = await store.get_node("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_add_node_upserts_on_duplicate_id(store):
    await store.add_node("Session", {"id": "s2", "name": "First"})
    await store.add_node("Session", {"id": "s2", "name": "Updated"})
    node = await store.get_node("s2")
    assert node["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_node_removes_it(store):
    await store.add_node("Tool", {"id": "t1", "name": "pytest"})
    deleted = await store.delete_node("t1")
    assert deleted is True
    assert await store.get_node("t1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_node_returns_false(store):
    result = await store.delete_node("ghost")
    assert result is False


# ---------------------------------------------------------------------------
# 3. Edge CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_edge_returns_id(store):
    await store.add_node("Session", {"id": "sess", "name": "s"})
    await store.add_node("File", {"id": "file", "name": "f"})
    edge_id = await store.add_edge("sess", "file", "MENTIONS")
    assert edge_id  # non-empty


@pytest.mark.asyncio
async def test_add_edge_upserts_deterministically(store):
    await store.add_node("Session", {"id": "sA", "name": "sA"})
    await store.add_node("File", {"id": "fA", "name": "fA"})
    id1 = await store.add_edge("sA", "fA", "USES")
    id2 = await store.add_edge("sA", "fA", "USES")
    assert id1 == id2  # same edge, same ID


@pytest.mark.asyncio
async def test_delete_edge(store):
    await store.add_node("Session", {"id": "sB", "name": "sB"})
    await store.add_node("File", {"id": "fB", "name": "fB"})
    edge_id = await store.add_edge("sB", "fB", "REFERENCES", {"confidence": 0.9})
    deleted = await store.delete_edge(edge_id)
    assert deleted is True


# ---------------------------------------------------------------------------
# 4. Neighbor queries
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def graph_with_edges(store):
    """Build a small graph: session -> file1 (MENTIONS), file1 -> concept (USES)."""
    await store.add_node("Session", {"id": "sess1", "name": "Session 1"})
    await store.add_node("File", {"id": "file1", "name": "main.py"})
    await store.add_node("Concept", {"id": "con1", "name": "Dependency Injection"})
    await store.add_edge("sess1", "file1", "MENTIONS")
    await store.add_edge("file1", "con1", "USES")
    return store


@pytest.mark.asyncio
async def test_get_neighbors_outgoing(graph_with_edges):
    neighbors = await graph_with_edges.get_neighbors("sess1", direction="outgoing")
    ids = [n["id"] for n in neighbors]
    assert "file1" in ids


@pytest.mark.asyncio
async def test_get_neighbors_incoming(graph_with_edges):
    neighbors = await graph_with_edges.get_neighbors("file1", direction="incoming")
    ids = [n["id"] for n in neighbors]
    assert "sess1" in ids


@pytest.mark.asyncio
async def test_get_neighbors_both_directions(graph_with_edges):
    neighbors = await graph_with_edges.get_neighbors("file1", direction="both")
    ids = {n["id"] for n in neighbors}
    assert "sess1" in ids  # incoming
    assert "con1" in ids  # outgoing


@pytest.mark.asyncio
async def test_get_neighbors_filtered_by_edge_type(graph_with_edges):
    neighbors = await graph_with_edges.get_neighbors("sess1", edge_type="USES")
    assert neighbors == []  # only MENTIONS from sess1


@pytest.mark.asyncio
async def test_get_neighbors_no_connections(store):
    await store.add_node("Concept", {"id": "iso", "name": "Isolated"})
    result = await store.get_neighbors("iso")
    assert result == []


# ---------------------------------------------------------------------------
# 5. Search filtering
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def populated_store(store):
    nodes = [
        ("Session", {"id": "s1", "name": "Alpha session"}),
        ("Session", {"id": "s2", "name": "Beta session"}),
        ("File", {"id": "f1", "name": "alpha.py"}),
        ("File", {"id": "f2", "name": "beta.py"}),
        ("Concept", {"id": "c1", "name": "Alpha concept"}),
    ]
    for node_type, props in nodes:
        await store.add_node(node_type, props)
    return store


@pytest.mark.asyncio
async def test_search_all_nodes(populated_store):
    results = await populated_store.search_nodes()
    assert len(results) == 5


@pytest.mark.asyncio
async def test_search_by_type(populated_store):
    sessions = await populated_store.search_nodes(node_type="Session")
    assert len(sessions) == 2
    assert all(n["node_type"] == "Session" for n in sessions)


@pytest.mark.asyncio
async def test_search_by_name_contains(populated_store):
    results = await populated_store.search_nodes(name_contains="alpha")
    names = {r["name"] for r in results}
    assert "Alpha session" in names
    assert "alpha.py" in names
    assert "Alpha concept" in names
    assert "beta.py" not in names


@pytest.mark.asyncio
async def test_search_by_type_and_name(populated_store):
    results = await populated_store.search_nodes(node_type="File", name_contains="alpha")
    assert len(results) == 1
    assert results[0]["name"] == "alpha.py"


@pytest.mark.asyncio
async def test_search_limit(populated_store):
    results = await populated_store.search_nodes(limit=2)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 6. execute_query (Cypher-to-SQL translation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_query_count_all(populated_store):
    result = await populated_store.execute_query("MATCH (n) RETURN count(n) as total")
    assert result[0]["total"] == 5


@pytest.mark.asyncio
async def test_execute_query_count_by_label(populated_store):
    result = await populated_store.execute_query(
        "MATCH (n:Session) RETURN count(n) as total"
    )
    assert result[0]["total"] == 2


@pytest.mark.asyncio
async def test_execute_query_match_label(populated_store):
    result = await populated_store.execute_query(
        "MATCH (e:File) RETURN e, labels(e) as labels LIMIT 10"
    )
    assert len(result) == 2
    for row in result:
        assert "e" in row
        assert row["labels"] == ["File"]


@pytest.mark.asyncio
async def test_execute_query_match_with_where_contains(populated_store):
    result = await populated_store.execute_query(
        "MATCH (e) WHERE e.name CONTAINS 'alpha' RETURN e LIMIT 100"
    )
    assert len(result) == 3


@pytest.mark.asyncio
async def test_execute_query_match_by_id(populated_store):
    result = await populated_store.execute_query(
        "MATCH (e {id: 's1'}) RETURN e, labels(e) as labels"
    )
    assert len(result) == 1
    assert result[0]["e"]["id"] == "s1"


@pytest.mark.asyncio
async def test_execute_query_with_limit(populated_store):
    result = await populated_store.execute_query("MATCH (n) RETURN n LIMIT 2")
    assert len(result) <= 2


@pytest.mark.asyncio
async def test_execute_query_skip_and_limit(populated_store):
    all_results = await populated_store.execute_query("MATCH (n) RETURN n LIMIT 100")
    page2 = await populated_store.execute_query("MATCH (n) RETURN n SKIP 2 LIMIT 2")
    assert len(page2) <= 2
    # Values at position 2-3 of all_results should match page2
    all_ids = [r["n"]["id"] for r in all_results]
    page2_ids = [r["n"]["id"] for r in page2]
    assert page2_ids == all_ids[2:4]


@pytest.mark.asyncio
async def test_execute_query_edge_pattern(store):
    await store.add_node("Session", {"id": "sX", "name": "Sx"})
    await store.add_node("File", {"id": "fX", "name": "fx.py"})
    await store.add_edge("sX", "fX", "MENTIONS", {"confidence": 0.9})

    result = await store.execute_query(
        "MATCH (n)-[r:MENTIONS]->(m) RETURN n, r, m, type(r) as rel_type, "
        "labels(n) as n_labels, labels(m) as m_labels"
    )
    assert len(result) == 1
    row = result[0]
    assert row["n"]["id"] == "sX"
    assert row["m"]["id"] == "fX"
    assert row["rel_type"] == "MENTIONS"


@pytest.mark.asyncio
async def test_execute_query_params_substitution(populated_store):
    result = await populated_store.execute_query(
        "MATCH (e) WHERE e.name CONTAINS $term RETURN e LIMIT 10",
        params={"term": "beta"},
    )
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# 7. Factory function
# ---------------------------------------------------------------------------


def test_get_graph_store_returns_sqlite_when_no_falkordb_url(tmp_path):
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.graph_backend = "auto"
    settings.falkordb_url = None
    settings.sqlite_graph_path = str(tmp_path / "factory.db")

    store = get_graph_store(settings)
    assert isinstance(store, SQLiteGraphStore)


def test_get_graph_store_explicit_sqlite_backend(tmp_path):
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.graph_backend = "sqlite"
    settings.sqlite_graph_path = str(tmp_path / "explicit.db")

    store = get_graph_store(settings)
    assert isinstance(store, SQLiteGraphStore)


def test_get_graph_store_explicit_falkordb_backend(tmp_path):
    """When GRAPH_BACKEND=falkordb a GraphPopulator should be returned.

    We mock GraphPopulator so the test does not require a live Redis/FalkorDB.
    """
    from unittest.mock import MagicMock, patch

    settings = MagicMock()
    settings.graph_backend = "falkordb"
    settings.falkordb_url = "redis://localhost:6379"
    settings.redis_url = "redis://localhost:6379"
    settings.graph_name = "test_graph"
    settings.create_db_indexes = False

    mock_populator = MagicMock()
    with patch(
        "code_atlas.graph_populator.GraphPopulator",
        return_value=mock_populator,
    ):
        result = get_graph_store(settings)
        # Should not be a SQLiteGraphStore
        assert not isinstance(result, SQLiteGraphStore)


def test_get_graph_store_auto_prefers_falkordb_when_url_set(tmp_path):
    """auto mode should pick FalkorDB when falkordb_url is configured."""
    from unittest.mock import MagicMock, patch

    settings = MagicMock()
    settings.graph_backend = "auto"
    settings.falkordb_url = "redis://myhost:6379"
    settings.redis_url = "redis://myhost:6379"
    settings.graph_name = "my_graph"
    settings.create_db_indexes = False

    mock_populator = MagicMock()
    with patch(
        "code_atlas.graph_populator.GraphPopulator",
        return_value=mock_populator,
    ):
        result = get_graph_store(settings)
        assert not isinstance(result, SQLiteGraphStore)


def test_get_graph_store_no_settings_uses_defaults(tmp_path, monkeypatch):
    """Calling get_graph_store() with no args should succeed and return SQLite."""
    monkeypatch.chdir(tmp_path)
    store = get_graph_store()
    assert isinstance(store, SQLiteGraphStore)
