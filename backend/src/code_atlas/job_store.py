"""SQLite-backed job persistence for processing jobs.

This module provides durable storage for processing jobs that survives
server restarts. Uses aiosqlite for async operations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .logging_config import get_logger
from .schemas.sessions import JobStatus, ProcessingJob

logger = get_logger(__name__)


class JobStore:
    """SQLite-backed job persistence with sync operations.

    Provides durable storage for processing jobs that survives
    server restarts. Thread-safe for concurrent access.
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize job store with SQLite connection.

        Creates tables if they don't exist. Uses in-memory DB if no path provided.

        Args:
            db_path: Path to SQLite database file. None for in-memory.
        """
        if db_path is None:
            self._db_path = ":memory:"
        else:
            self._db_path = str(db_path)
            # Ensure parent directory exists
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
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                total_sessions INTEGER NOT NULL DEFAULT 0,
                processed_sessions INTEGER NOT NULL DEFAULT 0,
                failed_sessions INTEGER NOT NULL DEFAULT 0,
                current_session TEXT,
                error_message TEXT,
                stats TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)
        """)
        conn.commit()
        logger.debug("Job store initialized", db_path=self._db_path)

    def _serialize_job(self, job: ProcessingJob) -> dict[str, Any]:
        """Serialize job to database row values."""
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "total_sessions": job.total_sessions,
            "processed_sessions": job.processed_sessions,
            "failed_sessions": job.failed_sessions,
            "current_session": job.current_session,
            "error_message": job.error_message,
            "stats": json.dumps(job.stats) if job.stats else None,
        }

    def _deserialize_job(self, row: sqlite3.Row) -> ProcessingJob:
        """Deserialize database row to ProcessingJob."""
        return ProcessingJob(
            job_id=row["job_id"],
            status=JobStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(
                datetime.fromisoformat(row["started_at"])
                if row["started_at"]
                else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            total_sessions=row["total_sessions"],
            processed_sessions=row["processed_sessions"],
            failed_sessions=row["failed_sessions"],
            current_session=row["current_session"],
            error_message=row["error_message"],
            stats=json.loads(row["stats"]) if row["stats"] else None,
        )

    def save(self, job: ProcessingJob) -> None:
        """Persist job state to SQLite.

        Upserts job by job_id, serializes stats dict as JSON.

        Args:
            job: Processing job to save.
        """
        data = self._serialize_job(job)
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs (
                job_id, status, created_at, started_at, completed_at,
                total_sessions, processed_sessions, failed_sessions,
                current_session, error_message, stats
            ) VALUES (
                :job_id, :status, :created_at, :started_at, :completed_at,
                :total_sessions, :processed_sessions, :failed_sessions,
                :current_session, :error_message, :stats
            )
            """,
            data,
        )
        conn.commit()
        logger.debug("Job saved", job_id=job.job_id, status=job.status.value)

    def get(self, job_id: str) -> ProcessingJob | None:
        """Retrieve job by ID.

        Returns None if job not found, deserializes JSON stats.

        Args:
            job_id: Unique job identifier.

        Returns:
            ProcessingJob if found, None otherwise.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._deserialize_job(row)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[ProcessingJob]:
        """List jobs with optional status filter.

        Ordered by created_at descending.

        Args:
            status: Optional status filter.
            limit: Maximum number of jobs to return.

        Returns:
            List of processing jobs.
        """
        conn = self._get_connection()
        if status is not None:
            cursor = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status.value, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [self._deserialize_job(row) for row in cursor.fetchall()]

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        **kwargs: Any,
    ) -> bool:
        """Update job status and optional fields.

        Atomic update for concurrent access safety.

        Args:
            job_id: Job to update.
            status: New status.
            **kwargs: Additional fields to update (started_at, completed_at, etc.)

        Returns:
            True if job was found and updated, False otherwise.
        """
        # Build dynamic SET clause
        set_parts = ["status = ?"]
        params: list[Any] = [status.value]

        allowed_fields = {
            "started_at",
            "completed_at",
            "processed_sessions",
            "failed_sessions",
            "current_session",
            "error_message",
            "stats",
        }

        for key, value in kwargs.items():
            if key not in allowed_fields:
                continue
            set_parts.append(f"{key} = ?")
            if key in ("started_at", "completed_at") and value is not None:
                params.append(value.isoformat())
            elif key == "stats" and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)

        params.append(job_id)

        conn = self._get_connection()
        cursor = conn.execute(
            f"""
            UPDATE jobs
            SET {', '.join(set_parts)}
            WHERE job_id = ?
            """,
            params,
        )
        conn.commit()

        updated = cursor.rowcount > 0
        if updated:
            logger.debug(
                "Job status updated", job_id=job_id, status=status.value
            )
        return updated

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """Remove completed/failed jobs older than N days.

        Returns count of deleted jobs.

        Args:
            days: Number of days to keep jobs.

        Returns:
            Count of deleted jobs.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        conn = self._get_connection()
        cursor = conn.execute(
            """
            DELETE FROM jobs
            WHERE status IN (?, ?, ?)
            AND created_at < ?
            """,
            (
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
                cutoff.isoformat(),
            ),
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Cleaned up old jobs", count=deleted, days=days)
        return deleted

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# Global job store instance
_job_store: JobStore | None = None


def get_job_store(db_path: Path | str | None = None) -> JobStore:
    """Get or create global job store instance.

    Args:
        db_path: Path to database. Only used on first call.

    Returns:
        JobStore singleton instance.
    """
    global _job_store
    if _job_store is None:
        _job_store = JobStore(db_path)
    return _job_store


def reset_job_store() -> None:
    """Reset global job store. Used for testing."""
    global _job_store
    if _job_store is not None:
        _job_store.close()
        _job_store = None
