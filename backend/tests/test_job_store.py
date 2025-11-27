"""Tests for job store persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from code_atlas.job_store import JobStore, get_job_store, reset_job_store
from code_atlas.schemas.sessions import JobStatus, ProcessingJob


@pytest.fixture
def job_store() -> JobStore:
    """Create a fresh in-memory job store for each test."""
    return JobStore()


@pytest.fixture
def sample_job() -> ProcessingJob:
    """Create a sample processing job."""
    return ProcessingJob(
        job_id="job-test123",
        status=JobStatus.PENDING,
        created_at=datetime.now(tz=timezone.utc),
        total_sessions=5,
        processed_sessions=0,
        failed_sessions=0,
    )


def test_job_store_save_and_retrieve(job_store: JobStore, sample_job: ProcessingJob) -> None:
    """Jobs persist across store instances."""
    # Save job
    job_store.save(sample_job)

    # Retrieve and verify
    retrieved = job_store.get(sample_job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == sample_job.job_id
    assert retrieved.status == sample_job.status
    assert retrieved.total_sessions == sample_job.total_sessions


def test_job_store_list_with_status_filter(job_store: JobStore) -> None:
    """Filter by pending/running/completed."""
    # Create jobs with different statuses
    for i, status in enumerate([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED]):
        job = ProcessingJob(
            job_id=f"job-{i}",
            status=status,
            created_at=datetime.now(tz=timezone.utc),
            total_sessions=1,
            processed_sessions=0,
            failed_sessions=0,
        )
        job_store.save(job)

    # Filter by status
    pending = job_store.list_jobs(status=JobStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].status == JobStatus.PENDING

    running = job_store.list_jobs(status=JobStatus.RUNNING)
    assert len(running) == 1
    assert running[0].status == JobStatus.RUNNING

    # List all
    all_jobs = job_store.list_jobs()
    assert len(all_jobs) == 3


def test_job_store_update_status_atomic(job_store: JobStore, sample_job: ProcessingJob) -> None:
    """Concurrent updates don't corrupt."""
    job_store.save(sample_job)

    # Update status
    result = job_store.update_status(
        sample_job.job_id,
        JobStatus.RUNNING,
        started_at=datetime.now(tz=timezone.utc),
    )
    assert result is True

    # Verify update
    job = job_store.get(sample_job.job_id)
    assert job is not None
    assert job.status == JobStatus.RUNNING
    assert job.started_at is not None


def test_job_store_cleanup_old_jobs(job_store: JobStore) -> None:
    """Expired jobs removed, recent kept."""
    now = datetime.now(tz=timezone.utc)

    # Create old completed job
    old_job = ProcessingJob(
        job_id="job-old",
        status=JobStatus.COMPLETED,
        created_at=now - timedelta(days=10),
        total_sessions=1,
        processed_sessions=1,
        failed_sessions=0,
    )
    job_store.save(old_job)

    # Create recent completed job
    recent_job = ProcessingJob(
        job_id="job-recent",
        status=JobStatus.COMPLETED,
        created_at=now - timedelta(days=1),
        total_sessions=1,
        processed_sessions=1,
        failed_sessions=0,
    )
    job_store.save(recent_job)

    # Create old running job (should not be deleted)
    running_job = ProcessingJob(
        job_id="job-running",
        status=JobStatus.RUNNING,
        created_at=now - timedelta(days=10),
        total_sessions=1,
        processed_sessions=0,
        failed_sessions=0,
    )
    job_store.save(running_job)

    # Cleanup
    deleted = job_store.cleanup_old_jobs(days=7)
    assert deleted == 1

    # Verify correct jobs remain
    assert job_store.get("job-old") is None
    assert job_store.get("job-recent") is not None
    assert job_store.get("job-running") is not None


def test_job_store_handles_missing_job(job_store: JobStore) -> None:
    """Returns None for unknown job_id."""
    result = job_store.get("nonexistent-job")
    assert result is None


def test_job_store_serializes_stats_dict(job_store: JobStore) -> None:
    """Complex stats dict round-trips."""
    job = ProcessingJob(
        job_id="job-stats",
        status=JobStatus.COMPLETED,
        created_at=datetime.now(tz=timezone.utc),
        total_sessions=5,
        processed_sessions=4,
        failed_sessions=1,
        stats={
            "entities_created": 100,
            "relationships_created": 50,
            "total_cost_usd": 0.15,
            "nested": {"key": "value"},
        },
    )
    job_store.save(job)

    # Retrieve and verify stats
    retrieved = job_store.get("job-stats")
    assert retrieved is not None
    assert retrieved.stats is not None
    assert retrieved.stats["entities_created"] == 100
    assert retrieved.stats["relationships_created"] == 50
    assert retrieved.stats["total_cost_usd"] == 0.15
    assert retrieved.stats["nested"]["key"] == "value"


def test_job_store_update_nonexistent_returns_false(job_store: JobStore) -> None:
    """Update on missing job returns False."""
    result = job_store.update_status("missing-job", JobStatus.RUNNING)
    assert result is False


def test_job_store_list_ordered_by_created_at(job_store: JobStore) -> None:
    """Jobs are listed in descending order by creation time."""
    now = datetime.now(tz=timezone.utc)

    for i in range(3):
        job = ProcessingJob(
            job_id=f"job-{i}",
            status=JobStatus.PENDING,
            created_at=now - timedelta(hours=i),
            total_sessions=1,
            processed_sessions=0,
            failed_sessions=0,
        )
        job_store.save(job)

    jobs = job_store.list_jobs()
    assert len(jobs) == 3
    # Most recent first (job-0)
    assert jobs[0].job_id == "job-0"
    assert jobs[2].job_id == "job-2"


def test_job_store_persists_to_file(tmp_path: Path) -> None:
    """Jobs persist across store instances with file-backed DB."""
    db_path = tmp_path / "jobs.db"

    # Create store and save job
    store1 = JobStore(db_path)
    job = ProcessingJob(
        job_id="job-persist",
        status=JobStatus.PENDING,
        created_at=datetime.now(tz=timezone.utc),
        total_sessions=3,
        processed_sessions=0,
        failed_sessions=0,
    )
    store1.save(job)
    store1.close()

    # Create new store instance and verify
    store2 = JobStore(db_path)
    retrieved = store2.get("job-persist")
    assert retrieved is not None
    assert retrieved.job_id == "job-persist"
    assert retrieved.total_sessions == 3
    store2.close()


def test_job_store_global_singleton() -> None:
    """Global job store is singleton."""
    reset_job_store()  # Clear any existing

    store1 = get_job_store()
    store2 = get_job_store()

    assert store1 is store2

    reset_job_store()  # Cleanup


def test_job_store_full_lifecycle(job_store: JobStore) -> None:
    """Test complete job lifecycle: create -> start -> progress -> complete."""
    now = datetime.now(tz=timezone.utc)

    # Create job
    job = ProcessingJob(
        job_id="job-lifecycle",
        status=JobStatus.PENDING,
        created_at=now,
        total_sessions=3,
        processed_sessions=0,
        failed_sessions=0,
    )
    job_store.save(job)

    # Start job
    job_store.update_status(
        "job-lifecycle",
        JobStatus.RUNNING,
        started_at=now,
    )

    # Check running state
    running = job_store.get("job-lifecycle")
    assert running is not None
    assert running.status == JobStatus.RUNNING
    assert running.started_at is not None

    # Update progress
    job_store.update_status(
        "job-lifecycle",
        JobStatus.RUNNING,
        processed_sessions=2,
        current_session="session-3.jsonl",
    )

    # Complete job
    job_store.update_status(
        "job-lifecycle",
        JobStatus.COMPLETED,
        processed_sessions=3,
        completed_at=now + timedelta(minutes=5),
        current_session=None,
        stats={"entities_created": 50, "relationships_created": 25},
    )

    # Verify final state
    completed = job_store.get("job-lifecycle")
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.processed_sessions == 3
    assert completed.completed_at is not None
    assert completed.stats["entities_created"] == 50
