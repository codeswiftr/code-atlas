"""Usage tracking for billing and rate limit enforcement."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import uuid

from .logging_config import get_logger
from .schemas.usage import UsageEvent, UsageEventType, UsageSummary

logger = get_logger(__name__)


class UsageTracker:
    """Tracks API usage for billing and rate limit enforcement.

    Stores events in SQLite for persistence and provides aggregation methods
    for usage reports.
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize with SQLite connection.

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
            CREATE TABLE IF NOT EXISTS usage_events (
                event_id TEXT PRIMARY KEY,
                key_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                endpoint TEXT,
                tokens_used INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_events_key_id
            ON usage_events(key_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_events_timestamp
            ON usage_events(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_events_type
            ON usage_events(event_type)
        """)
        conn.commit()
        logger.debug("Usage tracker initialized", db_path=self._db_path)

    def record_event(
        self,
        key_id: str,
        event_type: UsageEventType,
        endpoint: str | None = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        """Record a usage event.

        Args:
            key_id: API key identifier
            event_type: Type of event
            endpoint: API endpoint called
            tokens_used: LLM tokens consumed
            cost_usd: Cost in USD
            metadata: Additional event metadata

        Returns:
            UsageEvent with generated ID
        """
        event_id = f"evt_{uuid.uuid4().hex}"
        event = UsageEvent(
            event_id=event_id,
            key_id=key_id,
            event_type=event_type,
            timestamp=datetime.now(tz=UTC),
            endpoint=endpoint,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            metadata=metadata or {},
        )

        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO usage_events (
                event_id, key_id, event_type, timestamp, endpoint,
                tokens_used, cost_usd, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.key_id,
                event.event_type.value,
                event.timestamp.isoformat(),
                event.endpoint,
                event.tokens_used,
                event.cost_usd,
                str(event.metadata) if event.metadata else "{}",
            ),
        )
        conn.commit()

        logger.debug(
            "Usage event recorded",
            event_id=event.event_id,
            key_id=key_id,
            event_type=event_type.value,
        )

        return event

    def get_events(
        self,
        key_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[UsageEvent]:
        """Get usage events for a key.

        Args:
            key_id: API key identifier
            since: Only events after this timestamp
            limit: Maximum events to return

        Returns:
            List of UsageEvent objects
        """
        conn = self._get_connection()

        if since:
            cursor = conn.execute(
                """
                SELECT * FROM usage_events
                WHERE key_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (key_id, since.isoformat(), limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM usage_events
                WHERE key_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (key_id, limit),
            )

        events = []
        for row in cursor.fetchall():
            events.append(self._row_to_event(row))

        return events

    def get_hourly_usage(self, key_id: str) -> int:
        """Get number of requests in the current hour window.

        Used for rate limiting.

        Args:
            key_id: API key identifier

        Returns:
            Number of events in the current hour
        """
        one_hour_ago = datetime.now(tz=UTC) - timedelta(hours=1)

        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT COUNT(*) as count FROM usage_events
            WHERE key_id = ? AND timestamp >= ?
            """,
            (key_id, one_hour_ago.isoformat()),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_summary(
        self,
        key_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageSummary:
        """Get usage summary for a period.

        Args:
            key_id: API key identifier
            period_start: Start of period
            period_end: End of period

        Returns:
            UsageSummary with aggregated stats
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN event_type = 'report_generated' THEN 1 ELSE 0 END) as report_count,
                SUM(tokens_used) as total_tokens,
                SUM(cost_usd) as total_cost
            FROM usage_events
            WHERE key_id = ? AND timestamp >= ? AND timestamp < ?
            """,
            (key_id, period_start.isoformat(), period_end.isoformat()),
        )
        row = cursor.fetchone()

        return UsageSummary(
            key_id=key_id,
            period_start=period_start,
            period_end=period_end,
            total_requests=row["total_requests"] if row else 0,
            report_count=row["report_count"] if row else 0,
            total_tokens=row["total_tokens"] if row else 0,
            total_cost_usd=row["total_cost"] if row else 0.0,
        )

    def _row_to_event(self, row: sqlite3.Row) -> UsageEvent:
        """Convert database row to UsageEvent."""
        import json

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, KeyError):
                pass

        return UsageEvent(
            event_id=row["event_id"],
            key_id=row["key_id"],
            event_type=UsageEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            endpoint=row["endpoint"],
            tokens_used=row["tokens_used"] or 0,
            cost_usd=row["cost_usd"] or 0.0,
            metadata=metadata,
        )

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# Global tracker instance
_tracker: UsageTracker | None = None


def get_tracker(db_path: Path | str | None = None) -> UsageTracker:
    """Get or create global tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker(db_path)
    return _tracker


def reset_tracker() -> None:
    """Reset global tracker. Used for testing."""
    global _tracker
    if _tracker is not None:
        _tracker.close()
        _tracker = None
