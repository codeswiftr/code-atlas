"""SQLite-backed store for encrypted OAuth tokens.

Tokens are encrypted with :mod:`code_atlas.integrations.crypto` before being
written to disk.  The store is a thin wrapper around :mod:`sqlite3` following
the same pattern as :class:`code_atlas.auth.api_keys.APIKeyManager`.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..logging_config import get_logger
from .crypto import decrypt_token, encrypt_token
from .models import GitHubConnection, GitHubStatus

logger = get_logger(__name__)


class TokenStore:
    """Persist encrypted GitHub tokens keyed by ``user_id``."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            self._db_path = ":memory:"
        else:
            self._db_path = str(db_path)
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection: sqlite3.Connection | None = None
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS github_tokens (
                user_id      TEXT PRIMARY KEY,
                enc_token    TEXT NOT NULL,
                github_login TEXT,
                connected_at TEXT NOT NULL
            )
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def save(
        self,
        user_id: str,
        raw_token: str,
        github_login: str | None = None,
    ) -> GitHubConnection:
        """Encrypt *raw_token* and persist it for *user_id*.

        If a token already exists for *user_id* it is overwritten.

        Returns:
            The stored :class:`~code_atlas.integrations.models.GitHubConnection`.
        """
        enc = encrypt_token(raw_token)
        now = datetime.now(tz=UTC)
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO github_tokens (user_id, enc_token, github_login, connected_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                enc_token    = excluded.enc_token,
                github_login = excluded.github_login,
                connected_at = excluded.connected_at
            """,
            (user_id, enc, github_login, now.isoformat()),
        )
        conn.commit()
        logger.info("GitHub token stored", user_id=user_id, has_login=github_login is not None)
        return GitHubConnection(
            user_id=user_id,
            access_token=enc,
            connected_at=now,
            github_login=github_login,
        )

    def get_raw_token(self, user_id: str) -> str | None:
        """Return the decrypted token for *user_id*, or ``None`` if not found."""
        row = self._fetch_row(user_id)
        if row is None:
            return None
        return decrypt_token(row["enc_token"])

    def get_connection(self, user_id: str) -> GitHubConnection | None:
        """Return the :class:`GitHubConnection` for *user_id* (token still encrypted)."""
        row = self._fetch_row(user_id)
        if row is None:
            return None
        return GitHubConnection(
            user_id=user_id,
            access_token=row["enc_token"],
            connected_at=datetime.fromisoformat(row["connected_at"]),
            github_login=row["github_login"],
        )

    def get_status(self, user_id: str) -> GitHubStatus:
        """Return the connection status for *user_id*."""
        row = self._fetch_row(user_id)
        if row is None:
            return GitHubStatus(connected=False)
        return GitHubStatus(
            connected=True,
            github_login=row["github_login"],
            connected_at=datetime.fromisoformat(row["connected_at"]),
        )

    def delete(self, user_id: str) -> bool:
        """Remove the token for *user_id*.  Returns ``True`` if a row was deleted."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM github_tokens WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("GitHub token deleted", user_id=user_id)
        return deleted

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_row(self, user_id: str) -> sqlite3.Row | None:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM github_tokens WHERE user_id = ?",
            (user_id,),
        )
        return cursor.fetchone()


# ---------------------------------------------------------------------------
# Process-level singleton (mirrors api_keys.py pattern)
# ---------------------------------------------------------------------------

_store: TokenStore | None = None


def get_token_store(db_path: Path | str | None = None) -> TokenStore:
    """Return the process-level :class:`TokenStore` singleton."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = TokenStore(db_path)
    return _store


def reset_token_store() -> None:
    """Reset the singleton — used in tests."""
    global _store  # noqa: PLW0603
    if _store is not None:
        _store.close()
        _store = None
