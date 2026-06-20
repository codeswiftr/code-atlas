"""SQLite-backed graph store — FalkorDB-free fallback for Code Atlas.

This module provides a ``GraphStore``-compatible implementation backed by
aiosqlite so the application can be deployed without Redis/FalkorDB.  It
supports the complete interface defined in ``interface.py`` and translates a
small subset of Cypher-style patterns into SQL JOINs for compatibility with
the existing API layer.

Supported Cypher-style patterns (``execute_query``):
  - ``MATCH (n) RETURN n``
  - ``MATCH (n:Label) RETURN n``
  - ``MATCH (n:Label) WHERE n.name CONTAINS 'x' RETURN n``
  - ``MATCH (n {id: 'x'}) RETURN n, labels(n) as labels``
  - ``MATCH (n)-[r:TYPE]->(m) RETURN n, r, m, type(r) as rel_type, ...``
  - ``MATCH (n)-[r]->(m) RETURN ...``
  - ``RETURN count(n) as total``
  - SKIP / LIMIT clauses
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import aiosqlite

from ..logging_config import get_logger

logger = get_logger(__name__)

_CREATE_NODES = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    id          TEXT PRIMARY KEY,
    node_type   TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    properties  TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL
);
"""

_CREATE_EDGES = """
CREATE TABLE IF NOT EXISTS graph_edges (
    id          TEXT PRIMARY KEY,
    from_node_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    to_node_id   TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    edge_type    TEXT NOT NULL,
    properties   TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(node_type);",
    "CREATE INDEX IF NOT EXISTS idx_nodes_name ON graph_nodes(name);",
    "CREATE INDEX IF NOT EXISTS idx_edges_from ON graph_edges(from_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_to   ON graph_edges(to_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_type ON graph_edges(edge_type);",
]


def _serialize(props: dict[str, Any]) -> str:
    return json.dumps(props, default=str)


def _deserialize(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _row_to_node(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert a DB row to a node dictionary matching GraphPopulator output."""
    props = _deserialize(row["properties"])
    result: dict[str, Any] = {
        "id": row["id"],
        "node_type": row["node_type"],
        "name": row["name"],
        "created_at": row["created_at"],
        **props,
    }
    return result


class SQLiteGraphStore:
    """Async SQLite-backed graph store.

    Usage::

        store = SQLiteGraphStore("graph.db")
        await store.initialize()
        node_id = await store.add_node("Session", {"id": "s1", "project": "atlas"})
        await store.close()
    """

    def __init__(self, db_path: str = "graph.db") -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the database and create schema if needed."""
        if self._conn is not None:
            return  # already open

        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.execute(_CREATE_NODES)
        await self._conn.execute(_CREATE_EDGES)
        for idx_sql in _CREATE_INDEXES:
            await self._conn.execute(idx_sql)
        await self._conn.commit()
        logger.info("SQLiteGraphStore initialised", db_path=self._db_path)

    async def close(self) -> None:
        """Flush and close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def _ensure_open(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError(
                "SQLiteGraphStore is not initialised. Call await store.initialize() first."
            )
        return self._conn

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    async def add_node(
        self,
        node_type: str,
        properties: dict[str, Any],
    ) -> str:
        """Insert or replace a node.  Returns the node ID."""
        conn = self._ensure_open()
        node_id: str = str(properties.get("id") or uuid.uuid4())
        name: str = str(properties.get("name") or properties.get("title") or node_id)

        # Strip id/name from the blob to avoid duplication
        extra = {k: v for k, v in properties.items() if k not in ("id", "name")}

        await conn.execute(
            """
            INSERT INTO graph_nodes (id, node_type, name, properties, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                node_type  = excluded.node_type,
                name       = excluded.name,
                properties = excluded.properties
            """,
            (node_id, node_type, name, _serialize(extra), time.time()),
        )
        await conn.commit()
        return node_id

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Return a node by ID or ``None``."""
        conn = self._ensure_open()
        async with conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,)) as cur:
            row = await cur.fetchone()
        return _row_to_node(row) if row else None

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its incident edges.  Returns True if deleted."""
        conn = self._ensure_open()
        async with conn.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,)) as cur:
            deleted = cur.rowcount > 0
        await conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Insert or replace a directed edge.  Returns the edge ID."""
        conn = self._ensure_open()
        # Deterministic ID so that upsert replaces on duplicate
        explicit_id = (properties or {}).get("id")
        edge_id = (
            str(explicit_id)
            if explicit_id is not None
            else str(uuid.uuid5(uuid.NAMESPACE_OID, f"{from_id}:{edge_type}:{to_id}"))
        )
        safe_props = properties or {}

        await conn.execute(
            """
            INSERT INTO graph_edges
                (id, from_node_id, to_node_id, edge_type, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                edge_type  = excluded.edge_type,
                properties = excluded.properties
            """,
            (edge_id, from_id, to_id, edge_type, _serialize(safe_props), time.time()),
        )
        await conn.commit()
        return edge_id

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by ID.  Returns True if deleted."""
        conn = self._ensure_open()
        async with conn.execute("DELETE FROM graph_edges WHERE id = ?", (edge_id,)) as cur:
            deleted = cur.rowcount > 0
        await conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Return neighbour nodes connected to ``node_id``.

        Args:
            node_id:   The centre node.
            edge_type: Restrict to this relationship type (or ``None`` for all).
            direction: ``"outgoing"``, ``"incoming"``, or ``"both"``.
        """
        conn = self._ensure_open()

        type_clause = "AND e.edge_type = ?" if edge_type else ""
        type_param: tuple[str, ...] = (edge_type,) if edge_type else ()

        rows: list[aiosqlite.Row] = []

        if direction in ("outgoing", "both"):
            sql = f"""
                SELECT n.* FROM graph_nodes n
                JOIN graph_edges e ON e.to_node_id = n.id
                WHERE e.from_node_id = ? {type_clause}
            """
            async with conn.execute(sql, (node_id, *type_param)) as cur:
                rows.extend(await cur.fetchall())

        if direction in ("incoming", "both"):
            sql = f"""
                SELECT n.* FROM graph_nodes n
                JOIN graph_edges e ON e.from_node_id = n.id
                WHERE e.to_node_id = ? {type_clause}
            """
            async with conn.execute(sql, (node_id, *type_param)) as cur:
                rows.extend(await cur.fetchall())

        # Deduplicate by ID while preserving order
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for row in rows:
            nid = row["id"]
            if nid not in seen:
                seen.add(nid)
                result.append(_row_to_node(row))
        return result

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_nodes(
        self,
        node_type: str | None = None,
        name_contains: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return nodes matching optional filters."""
        conn = self._ensure_open()

        clauses: list[str] = []
        params: list[Any] = []

        if node_type:
            clauses.append("node_type = ?")
            params.append(node_type)

        if name_contains:
            clauses.append("name LIKE ?")
            params.append(f"%{name_contains}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        async with conn.execute(
            f"SELECT * FROM graph_nodes {where} ORDER BY name LIMIT ?", params
        ) as cur:
            rows = await cur.fetchall()

        return [_row_to_node(r) for r in rows]

    # ------------------------------------------------------------------
    # Query translation
    # ------------------------------------------------------------------

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Translate a limited Cypher-style query to SQL and execute it.

        Supported patterns are documented in the module docstring.
        Falls back to an empty list and a warning for unrecognised patterns.
        """
        conn = self._ensure_open()

        # Substitute named $params into the query string (mirrors GraphPopulator)
        if params:
            for key, value in params.items():
                placeholder = f"${key}"
                if isinstance(value, str):
                    query = query.replace(placeholder, f"'{value}'")
                else:
                    query = query.replace(placeholder, str(value))

        # Normalise whitespace
        normalised = " ".join(query.split())

        try:
            return await self._translate_and_execute(conn, normalised)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "SQLiteGraphStore: unhandled query pattern, returning empty",
                query=normalised[:200],
                error=str(exc),
            )
            return []

    # ------------------------------------------------------------------
    # Internal query translation helpers
    # ------------------------------------------------------------------

    async def _translate_and_execute(
        self,
        conn: aiosqlite.Connection,
        query: str,
    ) -> list[dict[str, Any]]:
        """Route a normalised query string to the right SQL builder."""
        upper = query.upper()

        # count(n) short-circuit
        if "COUNT(" in upper:
            return await self._execute_count(conn, query)

        # Relationship pattern: MATCH (n)-[r...]->(m) RETURN ...
        if re.search(r"-\[r", query, re.IGNORECASE):
            return await self._execute_edge_query(conn, query)

        # Node pattern: MATCH (n...) RETURN ...
        if re.search(r"MATCH\s*\(", query, re.IGNORECASE):
            return await self._execute_node_query(conn, query)

        logger.debug("SQLiteGraphStore: pass-through query (no pattern matched)", query=query[:200])
        return []

    # -- count queries --

    async def _execute_count(
        self,
        conn: aiosqlite.Connection,
        query: str,
    ) -> list[dict[str, Any]]:
        """Handle ``RETURN count(n) as total`` patterns."""
        alias_match = re.search(r"count\(\w+\)\s+as\s+(\w+)", query, re.IGNORECASE)
        alias = alias_match.group(1) if alias_match else "total"

        # Extract optional label / WHERE
        label = _extract_node_label(query)
        where_parts, _ = _extract_where_clauses(query)

        clauses: list[str] = []
        sql_params: list[Any] = []

        if label:
            clauses.append("node_type = ?")
            sql_params.append(label)

        for col, op, val in where_parts:
            clause, p = _build_sql_clause(col, op, val)
            if clause:
                clauses.append(clause)
                sql_params.extend(p)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT COUNT(*) AS cnt FROM graph_nodes {where_sql}"

        async with conn.execute(sql, sql_params) as cur:
            row = await cur.fetchone()
        return [{alias: row["cnt"] if row else 0}]

    # -- node-only queries --

    async def _execute_node_query(
        self,
        conn: aiosqlite.Connection,
        query: str,
    ) -> list[dict[str, Any]]:
        """Handle ``MATCH (n[:Label]) [WHERE ...] RETURN n [SKIP x] [LIMIT y]``."""
        label = _extract_node_label(query)
        id_val = _extract_id_predicate(query)
        where_parts, raw_where = _extract_where_clauses(query)
        skip_val, limit_val = _extract_skip_limit(query)

        clauses: list[str] = []
        sql_params: list[Any] = []

        if label:
            clauses.append("node_type = ?")
            sql_params.append(label)

        if id_val:
            clauses.append("id = ?")
            sql_params.append(id_val)

        for col, op, val in where_parts:
            clause, p = _build_sql_clause(col, op, val)
            if clause:
                clauses.append(clause)
                sql_params.extend(p)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order_sql = "ORDER BY name"
        limit_sql = f"LIMIT {limit_val}" if limit_val is not None else "LIMIT 1000"
        skip_sql = f"OFFSET {skip_val}" if skip_val else ""

        sql = f"SELECT * FROM graph_nodes {where_sql} {order_sql} {limit_sql} {skip_sql}"

        async with conn.execute(sql, sql_params) as cur:
            rows = await cur.fetchall()

        return_cols = _extract_return_columns(query)
        results: list[dict[str, Any]] = []
        for row in rows:
            node = _row_to_node(row)
            row_dict: dict[str, Any] = {}
            if "e" in return_cols or "n" in return_cols:
                alias = "e" if "e" in return_cols else "n"
                row_dict[alias] = node
            if "labels(e)" in return_cols or "labels(n)" in return_cols:
                alias = "labels"
                row_dict["labels"] = [node["node_type"]]
            if not row_dict:
                row_dict = node
            results.append(row_dict)

        return results

    # -- edge queries --

    async def _execute_edge_query(
        self,
        conn: aiosqlite.Connection,
        query: str,
    ) -> list[dict[str, Any]]:
        """Handle ``MATCH (n)-[r[:TYPE]]->(m) RETURN n, r, m, type(r) as rel_type``."""
        upper = query.upper()
        skip_val, limit_val = _extract_skip_limit(query)

        # Determine edge type filter
        edge_type_match = re.search(r"\[r:(\w+)\]", query, re.IGNORECASE)
        edge_type = edge_type_match.group(1) if edge_type_match else None

        # Source / target id filters from WHERE
        src_id: str | None = None
        tgt_id: str | None = None
        where_match = re.search(r"WHERE(.+?)(?:RETURN|ORDER|SKIP|LIMIT|$)", query, re.IGNORECASE)
        if where_match:
            raw = where_match.group(1)
            src_m = re.search(r"s\.id\s*=\s*'([^']+)'", raw, re.IGNORECASE)
            tgt_m = re.search(r"t\.id\s*=\s*'([^']+)'", raw, re.IGNORECASE)
            if src_m:
                src_id = src_m.group(1)
            if tgt_m:
                tgt_id = tgt_m.group(1)

        clauses: list[str] = []
        sql_params: list[Any] = []

        if edge_type:
            clauses.append("e.edge_type = ?")
            sql_params.append(edge_type)
        if src_id:
            clauses.append("e.from_node_id = ?")
            sql_params.append(src_id)
        if tgt_id:
            clauses.append("e.to_node_id = ?")
            sql_params.append(tgt_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {limit_val}" if limit_val is not None else "LIMIT 1000"
        skip_sql = f"OFFSET {skip_val}" if skip_val else ""

        sql = f"""
            SELECT
                e.id         AS edge_id,
                e.edge_type  AS edge_type,
                e.properties AS edge_props,
                src.id          AS src_id,
                src.node_type   AS src_type,
                src.name        AS src_name,
                src.properties  AS src_props,
                tgt.id          AS tgt_id,
                tgt.node_type   AS tgt_type,
                tgt.name        AS tgt_name,
                tgt.properties  AS tgt_props
            FROM graph_edges e
            JOIN graph_nodes src ON src.id = e.from_node_id
            JOIN graph_nodes tgt ON tgt.id = e.to_node_id
            {where_sql}
            {limit_sql} {skip_sql}
        """

        async with conn.execute(sql, sql_params) as cur:
            rows = await cur.fetchall()

        return_cols = _extract_return_columns(query)
        results: list[dict[str, Any]] = []

        for row in rows:
            src_props = _deserialize(row["src_props"])
            tgt_props = _deserialize(row["tgt_props"])
            edge_props = _deserialize(row["edge_props"])

            src_node: dict[str, Any] = {
                "id": row["src_id"],
                "node_type": row["src_type"],
                "name": row["src_name"],
                **src_props,
            }
            tgt_node: dict[str, Any] = {
                "id": row["tgt_id"],
                "node_type": row["tgt_type"],
                "name": row["tgt_name"],
                **tgt_props,
            }
            edge_dict: dict[str, Any] = {
                "id": row["edge_id"],
                "type": row["edge_type"],
                **edge_props,
            }

            row_dict: dict[str, Any] = {}

            if "n" in return_cols:
                row_dict["n"] = src_node
            if "m" in return_cols:
                row_dict["m"] = tgt_node
            if "r" in return_cols:
                row_dict["r"] = edge_dict
            if "s" in return_cols:
                row_dict["s"] = src_node
            if "t" in return_cols:
                row_dict["t"] = tgt_node

            # type(r) as rel_type — key is "type(r)", alias is "rel_type"
            if "type(r)" in return_cols or "rel_type" in return_cols.values():
                alias = return_cols.get("type(r)", "rel_type")
                row_dict[alias] = row["edge_type"]

            # labels(n) / labels(s) / labels(m) / labels(t)
            for node_alias, node_obj in [
                ("n", src_node),
                ("s", src_node),
                ("m", tgt_node),
                ("t", tgt_node),
            ]:
                lk = f"labels({node_alias})"
                if lk in return_cols:
                    alias = return_cols[lk]
                    row_dict[alias] = [node_obj["node_type"]]

            # count query on edge result
            if "count" in upper:
                return [{"total": len(rows)}]

            if not row_dict:
                row_dict = {**src_node, "rel_type": row["edge_type"], **tgt_node}

            results.append(row_dict)

        return results


# ---------------------------------------------------------------------------
# Query parsing helpers (module-private)
# ---------------------------------------------------------------------------


def _extract_node_label(query: str) -> str | None:
    """Extract label from ``MATCH (n:Label ...)`` or ``MATCH (e:Label ...)``."""
    m = re.search(r"MATCH\s*\(\w+:(\w+)", query, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_id_predicate(query: str) -> str | None:
    """Extract ``id: 'value'`` from inline node pattern."""
    m = re.search(r"\{id:\s*'([^']+)'\}", query, re.IGNORECASE)
    if m:
        return m.group(1)
    # dollar-param already substituted
    m = re.search(r"\{id:\s*\"([^\"]+)\"\}", query, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_where_clauses(
    query: str,
) -> tuple[list[tuple[str, str, str]], str]:
    """Extract WHERE conditions into ``(column, operator, value)`` triples."""
    where_match = re.search(
        r"WHERE\s+(.+?)(?:RETURN|ORDER\s+BY|SKIP|LIMIT|$)",
        query,
        re.IGNORECASE,
    )
    if not where_match:
        return [], ""

    raw = where_match.group(1).strip()
    parts: list[tuple[str, str, str]] = []

    # Split on AND (simple, no nested parens)
    for clause in re.split(r"\bAND\b", raw, flags=re.IGNORECASE):
        clause = clause.strip()
        # e.name CONTAINS 'value'
        m = re.match(r"\w+\.(\w+)\s+CONTAINS\s+'([^']*)'", clause, re.IGNORECASE)
        if m:
            parts.append((m.group(1), "CONTAINS", m.group(2)))
            continue
        # e.confidence >= value
        m = re.match(r"\w+\.(\w+)\s*(>=|<=|>|<|=)\s*(['\w.]+)", clause, re.IGNORECASE)
        if m:
            val = m.group(3).strip("'")
            parts.append((m.group(1), m.group(2), val))

    return parts, raw


def _build_sql_clause(
    col: str,
    op: str,
    val: str,
) -> tuple[str, list[Any]]:
    """Convert a parsed WHERE triple to an SQL fragment and params."""
    col_lower = col.lower()

    # ``name`` is a proper column; anything else is in the JSON blob
    if col_lower == "name":
        if op.upper() == "CONTAINS":
            return "name LIKE ?", [f"%{val}%"]
        return f"name {op} ?", [val]

    if col_lower == "confidence":
        return f"CAST(json_extract(properties, '$.confidence') AS REAL) {op} ?", [float(val)]

    # Generic JSON property
    if op.upper() == "CONTAINS":
        return f"json_extract(properties, '$.{col}') LIKE ?", [f"%{val}%"]
    return f"json_extract(properties, '$.{col}') {op} ?", [val]


def _extract_skip_limit(query: str) -> tuple[int | None, int | None]:
    """Extract SKIP and LIMIT values."""
    skip: int | None = None
    limit: int | None = None

    skip_m = re.search(r"\bSKIP\s+(\d+)", query, re.IGNORECASE)
    if skip_m:
        skip = int(skip_m.group(1))

    limit_m = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
    if limit_m:
        limit = int(limit_m.group(1))

    return skip, limit


def _extract_return_columns(query: str) -> dict[str, str]:
    """Return ``{expression: alias}`` mapping from the RETURN clause.

    E.g. ``RETURN n, labels(n) as labels, type(r) as rel_type``
    ->  ``{"n": "n", "labels(n)": "labels", "type(r)": "rel_type"}``
    """
    m = re.search(r"RETURN\s+(.+?)(?:ORDER\s+BY|SKIP|LIMIT|$)", query, re.IGNORECASE)
    if not m:
        return {}

    result: dict[str, str] = {}
    for token in m.group(1).split(","):
        token = token.strip()
        as_m = re.match(r"(.+?)\s+as\s+(\w+)", token, re.IGNORECASE)
        if as_m:
            result[as_m.group(1).strip()] = as_m.group(2).strip()
        elif token:
            result[token] = token

    return result
