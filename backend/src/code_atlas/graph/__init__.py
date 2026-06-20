"""Graph store package for Code Atlas.

This package provides a backend-agnostic graph store abstraction.  The
``get_graph_store`` factory selects the implementation at runtime based on
the application settings:

- If ``settings.falkordb_url`` (``CODE_ATLAS_FALKORDB_URL``) is set, the
  FalkorDB/Redis-backed ``GraphPopulator`` is returned.
- Otherwise the ``SQLiteGraphStore`` is returned, using the path given by
  ``settings.sqlite_graph_path`` (``CODE_ATLAS_SQLITE_GRAPH_PATH``), which
  defaults to ``"graph.db"`` in the current working directory.

Selecting the backend via ``GRAPH_BACKEND`` env var
----------------------------------------------------
You can force a backend explicitly::

    GRAPH_BACKEND=sqlite   # always use SQLite
    GRAPH_BACKEND=falkordb # always use FalkorDB (requires FALKORDB_URL / REDIS_URL)

If ``GRAPH_BACKEND`` is unset, automatic detection is used (FalkorDB if
``CODE_ATLAS_FALKORDB_URL`` is present, else SQLite).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..graph_populator import GraphPopulator

from .interface import GraphStore
from .sqlite_graph import SQLiteGraphStore

__all__ = [
    "GraphStore",
    "SQLiteGraphStore",
    "get_graph_store",
]


def get_graph_store(settings=None):  # type: ignore[no-untyped-def]
    """Return the appropriate graph store for the current environment.

    Args:
        settings: An ``AtlasSettings`` instance.  When ``None``, a fresh
            ``AtlasSettings()`` instance is created.

    Returns:
        ``SQLiteGraphStore`` if ``GRAPH_BACKEND=sqlite`` or no FalkorDB URL is
        configured; otherwise a ``GraphPopulator`` (FalkorDB-backed).

    Note:
        The ``SQLiteGraphStore`` is **not** yet initialised — callers must
        ``await store.initialize()`` before first use.  ``GraphPopulator``
        initialises itself synchronously in ``__post_init__``.
    """
    if settings is None:
        from ..config import AtlasSettings

        settings = AtlasSettings()

    # Honour explicit GRAPH_BACKEND override
    backend: str = getattr(settings, "graph_backend", "auto").lower()

    if backend == "sqlite":
        db_path = getattr(settings, "sqlite_graph_path", None) or "graph.db"
        return SQLiteGraphStore(db_path=str(db_path))

    if backend == "falkordb":
        return _make_falkordb_store(settings)

    # "auto": prefer FalkorDB when a URL is explicitly configured
    falkordb_url = getattr(settings, "falkordb_url", None)
    if falkordb_url:
        return _make_falkordb_store(settings)

    # Default: SQLite fallback
    db_path = getattr(settings, "sqlite_graph_path", None) or "graph.db"
    return SQLiteGraphStore(db_path=str(db_path))


def _make_falkordb_store(settings) -> GraphPopulator:  # type: ignore[return]
    """Instantiate a FalkorDB-backed GraphPopulator.

    Falls back to the configured ``redis_url`` so existing deployments keep
    working without specifying a separate ``falkordb_url``.
    """
    from ..graph_populator import GraphPopulator

    url = getattr(settings, "falkordb_url", None) or getattr(settings, "redis_url", None)
    return GraphPopulator(
        graph_name=getattr(settings, "graph_name", "code_atlas"),
        redis_url=url,
        dry_run=False,
        create_indexes=getattr(settings, "create_db_indexes", True),
    )
