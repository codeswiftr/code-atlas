"""API key management with SQLite storage.

Provides secure API key generation, validation, and lifecycle management.
Keys are hashed before storage and validated using constant-time comparison.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..logging_config import get_logger
from ..schemas.auth import APIKeyRecord, APIKeyScope

logger = get_logger(__name__)

# Key prefix for identification
KEY_PREFIX = "cat_"


class APIKeyManager:
    """Manages API key lifecycle with SQLite storage."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize with SQLite connection.

        Creates api_keys table if not exists.

        Args:
            db_path: Path to SQLite database file. None for in-memory.
        """
        if db_path is None:
            self._db_path = ":memory:"
        else:
            self._db_path = str(db_path)
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection: sqlite3.Connection | None = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                scopes TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                last_used_at TEXT,
                request_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)
        """)
        conn.commit()
        logger.debug("API key manager initialized", db_path=self._db_path)

    def _hash_key(self, raw_key: str) -> str:
        """Hash API key for secure storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _verify_key(self, raw_key: str, key_hash: str) -> bool:
        """Verify key using constant-time comparison."""
        computed_hash = self._hash_key(raw_key)
        return hmac.compare_digest(computed_hash, key_hash)

    def _serialize_scopes(self, scopes: list[APIKeyScope]) -> str:
        """Serialize scopes to comma-separated string."""
        return ",".join(s.value for s in scopes)

    def _deserialize_scopes(self, scopes_str: str) -> list[APIKeyScope]:
        """Deserialize scopes from comma-separated string."""
        if not scopes_str:
            return []
        return [APIKeyScope(s) for s in scopes_str.split(",")]

    def _row_to_record(self, row: sqlite3.Row) -> APIKeyRecord:
        """Convert database row to APIKeyRecord."""
        return APIKeyRecord(
            key_id=row["key_id"],
            name=row["name"],
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            scopes=self._deserialize_scopes(row["scopes"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=(
                datetime.fromisoformat(row["expires_at"])
                if row["expires_at"]
                else None
            ),
            last_used_at=(
                datetime.fromisoformat(row["last_used_at"])
                if row["last_used_at"]
                else None
            ),
            request_count=row["request_count"],
        )

    def generate_key(
        self,
        name: str,
        scopes: list[APIKeyScope],
        expires_in_days: int | None = None,
    ) -> tuple[str, APIKeyRecord]:
        """Generate new API key with prefix 'cat_'.

        Returns (raw_key, record). Raw key shown once, hashed for storage.

        Args:
            name: Human-readable name for the key.
            scopes: List of scopes to grant.
            expires_in_days: Days until expiration (None = never).

        Returns:
            Tuple of (raw_key, APIKeyRecord).
        """
        # Generate secure random key
        random_part = secrets.token_urlsafe(32)
        raw_key = f"{KEY_PREFIX}{random_part}"
        key_hash = self._hash_key(raw_key)
        key_id = f"key_{secrets.token_hex(8)}"

        now = datetime.now(tz=timezone.utc)
        expires_at = (
            now + timedelta(days=expires_in_days)
            if expires_in_days
            else None
        )

        record = APIKeyRecord(
            key_id=key_id,
            name=name,
            key_hash=key_hash,
            key_prefix=raw_key[:12],  # "cat_" + first 8 chars
            scopes=scopes,
            is_active=True,
            created_at=now,
            expires_at=expires_at,
            last_used_at=None,
            request_count=0,
        )

        # Store in database
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO api_keys (
                key_id, name, key_hash, key_prefix, scopes,
                is_active, created_at, expires_at, last_used_at, request_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.key_id,
                record.name,
                record.key_hash,
                record.key_prefix,
                self._serialize_scopes(record.scopes),
                1,
                record.created_at.isoformat(),
                record.expires_at.isoformat() if record.expires_at else None,
                None,
                0,
            ),
        )
        conn.commit()

        logger.info(
            "API key generated",
            key_id=key_id,
            name=name,
            scopes=[s.value for s in scopes],
        )

        return raw_key, record

    def validate_key(self, raw_key: str) -> APIKeyRecord | None:
        """Validate API key and return record if valid.

        Checks hash, expiration, and active status.

        Args:
            raw_key: The raw API key to validate.

        Returns:
            APIKeyRecord if valid, None otherwise.
        """
        if not raw_key or not raw_key.startswith(KEY_PREFIX):
            return None

        key_hash = self._hash_key(raw_key)

        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ?",
            (key_hash,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        record = self._row_to_record(row)

        # Check if active
        if not record.is_active:
            logger.warning("Attempted use of inactive key", key_id=record.key_id)
            return None

        # Check expiration
        if record.expires_at and record.expires_at < datetime.now(tz=timezone.utc):
            logger.warning("Attempted use of expired key", key_id=record.key_id)
            return None

        return record

    def has_scope(self, record: APIKeyRecord, required_scope: APIKeyScope) -> bool:
        """Check if key has required scope.

        Admin scope grants access to everything.

        Args:
            record: The API key record.
            required_scope: The scope to check for.

        Returns:
            True if key has the required scope.
        """
        # Admin has all scopes
        if APIKeyScope.ADMIN in record.scopes:
            return True
        return required_scope in record.scopes

    def revoke_key(self, key_id: str) -> bool:
        """Revoke API key by ID.

        Sets is_active=False, keeps record for audit.

        Args:
            key_id: The key ID to revoke.

        Returns:
            True if key was found and revoked.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE key_id = ?",
            (key_id,),
        )
        conn.commit()

        if cursor.rowcount > 0:
            logger.info("API key revoked", key_id=key_id)
            return True
        return False

    def list_keys(self, include_revoked: bool = False) -> list[APIKeyRecord]:
        """List all API keys.

        Excludes revoked by default.

        Args:
            include_revoked: Whether to include revoked keys.

        Returns:
            List of API key records.
        """
        conn = self._get_connection()
        if include_revoked:
            cursor = conn.execute(
                "SELECT * FROM api_keys ORDER BY created_at DESC"
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE is_active = 1 ORDER BY created_at DESC"
            )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_key(self, key_id: str) -> APIKeyRecord | None:
        """Get API key record by ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM api_keys WHERE key_id = ?",
            (key_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def record_usage(self, key_id: str) -> None:
        """Record API key usage for tracking.

        Increments request_count, updates last_used_at.

        Args:
            key_id: The key ID to record usage for.
        """
        now = datetime.now(tz=timezone.utc)
        conn = self._get_connection()
        conn.execute(
            """
            UPDATE api_keys
            SET request_count = request_count + 1, last_used_at = ?
            WHERE key_id = ?
            """,
            (now.isoformat(), key_id),
        )
        conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# Global API key manager instance
_key_manager: APIKeyManager | None = None


def get_key_manager(db_path: Path | str | None = None) -> APIKeyManager:
    """Get or create global API key manager instance.

    Args:
        db_path: Path to database. Only used on first call.

    Returns:
        APIKeyManager singleton instance.
    """
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager(db_path)
    return _key_manager


def reset_key_manager() -> None:
    """Reset global key manager. Used for testing."""
    global _key_manager
    if _key_manager is not None:
        _key_manager.close()
        _key_manager = None
