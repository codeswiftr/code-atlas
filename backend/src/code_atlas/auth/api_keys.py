"""API key management with SQLite storage.

Provides secure API key generation, validation, and lifecycle management.
Keys are hashed before storage and validated using constant-time comparison.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..logging_config import get_logger
from ..schemas.auth import APIKeyRecord, APIKeyScope, APITier

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
                tier TEXT NOT NULL DEFAULT 'free',
                subscription_status TEXT NOT NULL DEFAULT 'active',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                last_used_at TEXT,
                request_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Add columns to existing tables (idempotent — ignored if column exists)
        for col_def in (
            "ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'active'",
            "ADD COLUMN stripe_customer_id TEXT",
            "ADD COLUMN stripe_subscription_id TEXT",
        ):
            try:
                conn.execute(f"ALTER TABLE api_keys {col_def}")
            except Exception:
                pass  # Column already exists
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
        keys = row.keys()
        tier_str = row["tier"] if "tier" in keys else "free"
        try:
            tier = APITier(tier_str)
        except ValueError:
            tier = APITier.FREE

        return APIKeyRecord(
            key_id=row["key_id"],
            name=row["name"],
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            scopes=self._deserialize_scopes(row["scopes"]),
            tier=tier,
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
        tier: APITier = APITier.FREE,
        expires_in_days: int | None = None,
    ) -> tuple[str, APIKeyRecord]:
        """Generate new API key with prefix 'cat_'.

        Returns (raw_key, record). Raw key shown once, hashed for storage.

        Args:
            name: Human-readable name for the key.
            scopes: List of scopes to grant.
            tier: Subscription tier for rate limiting.
            expires_in_days: Days until expiration (None = never).

        Returns:
            Tuple of (raw_key, APIKeyRecord).
        """
        # Generate secure random key
        random_part = secrets.token_urlsafe(32)
        raw_key = f"{KEY_PREFIX}{random_part}"
        key_hash = self._hash_key(raw_key)
        key_id = f"key_{secrets.token_hex(8)}"

        now = datetime.now(tz=UTC)
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
            tier=tier,
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
                key_id, name, key_hash, key_prefix, scopes, tier,
                is_active, created_at, expires_at, last_used_at, request_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.key_id,
                record.name,
                record.key_hash,
                record.key_prefix,
                self._serialize_scopes(record.scopes),
                record.tier.value,
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
            tier=tier.value,
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
        if record.expires_at and record.expires_at < datetime.now(tz=UTC):
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

    def update_tier(self, key_id: str, tier: APITier) -> bool:
        """Update the subscription tier for an API key.

        Args:
            key_id: The key ID to update.
            tier: New subscription tier.

        Returns:
            True if key was found and updated.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "UPDATE api_keys SET tier = ? WHERE key_id = ?",
            (tier.value, key_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info("API key tier updated", key_id=key_id, tier=tier.value)
        return updated

    def update_subscription_status(self, key_id: str, subscription_status: str) -> bool:
        """Update the subscription status for an API key.

        Valid statuses mirror Stripe: active, trialing, past_due, canceled, unpaid.

        Args:
            key_id: The key ID to update.
            subscription_status: New status string.

        Returns:
            True if key was found and updated.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "UPDATE api_keys SET subscription_status = ? WHERE key_id = ?",
            (subscription_status, key_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(
                "API key subscription status updated",
                key_id=key_id,
                subscription_status=subscription_status,
            )
        return updated

    def set_stripe_customer(
        self,
        key_id: str,
        stripe_customer_id: str,
        stripe_subscription_id: str | None = None,
    ) -> bool:
        """Associate a Stripe customer ID with an API key.

        Called on successful checkout to link the key to the Stripe customer
        record so future webhook events (payment failure, cancellation) can
        look up the correct key.

        Args:
            key_id: The key ID to update.
            stripe_customer_id: Stripe customer ID (cus_xxx).
            stripe_subscription_id: Stripe subscription ID (sub_xxx), optional.

        Returns:
            True if key was found and updated.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            UPDATE api_keys
            SET stripe_customer_id = ?, stripe_subscription_id = ?
            WHERE key_id = ?
            """,
            (stripe_customer_id, stripe_subscription_id, key_id),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(
                "API key Stripe customer linked",
                key_id=key_id,
                stripe_customer_id=stripe_customer_id,
            )
        return updated

    def get_key_by_stripe_customer(self, stripe_customer_id: str) -> APIKeyRecord | None:
        """Look up an API key record by its associated Stripe customer ID.

        Used by webhook handlers to resolve customer events back to internal
        key records.

        Args:
            stripe_customer_id: Stripe customer ID (cus_xxx).

        Returns:
            APIKeyRecord if found, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM api_keys WHERE stripe_customer_id = ? AND is_active = 1",
            (stripe_customer_id,),
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
        now = datetime.now(tz=UTC)
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
