"""Session management API endpoints."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from ...config import AtlasSettings
from ...job_store import JobStore, get_job_store
from ...logging_config import get_logger
from ...session_discovery import SessionDiscovery
from ...session_parser import SessionParser
from ...pipeline import PipelineRunner
from ..dependencies import Settings, Discovery, ApiKey
from ...schemas.sessions import (
    SessionDiscoveryRequest,
    SessionDiscoveryResponse,
    SessionInfo,
    SessionProcessRequest,
    SessionProcessResponse,
    ProcessingJob,
    JobStatus,
    ProcessingStatsResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])


def get_job_store_dependency() -> JobStore:
    """Dependency to get JobStore instance."""
    return get_job_store()


JobStoreDep = Annotated[JobStore, Depends(get_job_store_dependency)]


def _session_to_info(path: Path, project_name: str | None = None) -> SessionInfo:
    """Convert a session path to SessionInfo."""
    stat = path.stat()
    return SessionInfo(
        path=str(path),
        filename=path.name,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        project_name=project_name or path.parent.name,
    )


@router.post(
    "/discover",
    response_model=SessionDiscoveryResponse,
    summary="Discover available sessions",
    description="Scan for Claude Code session files in the specified directory.",
)
async def discover_sessions(
    request: SessionDiscoveryRequest,
    settings: Settings,
    api_key: ApiKey,
) -> SessionDiscoveryResponse:
    """Discover available session files."""
    logger.info(
        "Session discovery requested",
        root_path=request.root_path,
        project_filter=request.project_filter,
        api_key=api_key[:8] + "..." if api_key != "anonymous" else "anonymous",
    )

    # Use configured root path if not provided
    root_path = Path(request.root_path) if request.root_path else settings.session_root

    if not root_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Root path does not exist: {root_path}",
        )

    discovery = SessionDiscovery(root=root_path, settings=settings)
    sessions: list[SessionInfo] = []

    try:
        for session_path in discovery.discover_generator(
            project_filter=request.project_filter,
        ):
            # Apply size filters
            stat = session_path.stat()
            if request.min_size_bytes and stat.st_size < request.min_size_bytes:
                continue
            if request.max_size_bytes and stat.st_size > request.max_size_bytes:
                continue

            # Apply date filters
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if request.modified_after and modified_at < request.modified_after:
                continue
            if request.modified_before and modified_at > request.modified_before:
                continue

            sessions.append(_session_to_info(session_path))

            if len(sessions) >= request.limit:
                break

    except Exception as exc:
        logger.error("Session discovery failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {str(exc)}",
        )

    return SessionDiscoveryResponse(
        sessions=sessions,
        total_found=len(sessions),
        search_path=str(root_path),
        message=f"Found {len(sessions)} sessions",
    )


def _process_sessions_background(
    job_id: str,
    session_paths: list[str],
    settings: AtlasSettings,
    use_llm: bool,
    dry_run: bool,
    max_cost: float,
    job_store: JobStore,
) -> None:
    """Background task to process sessions."""
    job = job_store.get(job_id)
    if job is None:
        logger.error("Job not found for background processing", job_id=job_id)
        return

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(tz=timezone.utc)
    job_store.save(job)

    try:
        runner = PipelineRunner(settings)

        for i, path_str in enumerate(session_paths):
            job.current_session = Path(path_str).name
            job.processed_sessions = i
            job_store.save(job)

            try:
                # Process single session
                path = Path(path_str)
                if not path.exists():
                    job.failed_sessions += 1
                    job_store.save(job)
                    continue

                result = runner.process_session(
                    session_path=path,
                    use_llm=use_llm,
                    dry_run=dry_run,
                )

                if result.get("success"):
                    job.processed_sessions = i + 1
                    if job.stats is None:
                        job.stats = {
                            "entities_created": 0,
                            "relationships_created": 0,
                            "total_cost_usd": 0.0,
                        }
                    job.stats["entities_created"] += result.get("entities_created", 0)
                    job.stats["relationships_created"] += result.get(
                        "relationships_created", 0
                    )
                    job.stats["total_cost_usd"] += result.get("cost_usd", 0.0)
                else:
                    job.failed_sessions += 1

                job_store.save(job)

            except Exception as exc:
                logger.error(
                    "Session processing failed",
                    session=path_str,
                    error=str(exc),
                )
                job.failed_sessions += 1
                job_store.save(job)

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(tz=timezone.utc)
        job.current_session = None
        job_store.save(job)

    except Exception as exc:
        logger.error("Job failed", job_id=job_id, error=str(exc))
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.completed_at = datetime.now(tz=timezone.utc)
        job_store.save(job)


@router.post(
    "/process",
    response_model=SessionProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process sessions",
    description="Submit sessions for processing. Returns a job ID for tracking.",
)
async def process_sessions(
    request: SessionProcessRequest,
    background_tasks: BackgroundTasks,
    settings: Settings,
    api_key: ApiKey,
    job_store: JobStoreDep,
) -> SessionProcessResponse:
    """Submit sessions for processing."""
    logger.info(
        "Session processing requested",
        session_count=len(request.session_paths),
        use_llm=request.use_llm,
        dry_run=request.dry_run,
        api_key=api_key[:8] + "..." if api_key != "anonymous" else "anonymous",
    )

    # Validate session paths exist
    valid_paths = []
    for path_str in request.session_paths:
        path = Path(path_str)
        if path.exists() and path.suffix == ".jsonl":
            valid_paths.append(path_str)
        else:
            logger.warning("Invalid session path", path=path_str)

    if not valid_paths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid session files provided",
        )

    # Create job
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    job = ProcessingJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=datetime.now(tz=timezone.utc),
        total_sessions=len(valid_paths),
        processed_sessions=0,
        failed_sessions=0,
    )
    job_store.save(job)

    # Start background processing
    background_tasks.add_task(
        _process_sessions_background,
        job_id=job_id,
        session_paths=valid_paths,
        settings=settings,
        use_llm=request.use_llm,
        dry_run=request.dry_run,
        max_cost=request.max_cost_per_session,
        job_store=job_store,
    )

    return SessionProcessResponse(
        job=job,
        message=f"Processing job {job_id} created with {len(valid_paths)} sessions",
    )


@router.get(
    "/{job_id}/status",
    response_model=SessionProcessResponse,
    summary="Get job status",
    description="Get the current status of a processing job.",
)
async def get_job_status(
    job_id: str,
    api_key: ApiKey,
    job_store: JobStoreDep,
) -> SessionProcessResponse:
    """Get processing job status."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return SessionProcessResponse(job=job)


@router.get(
    "",
    response_model=list[ProcessingJob],
    summary="List jobs",
    description="List all processing jobs.",
)
async def list_jobs(
    api_key: ApiKey,
    job_store: JobStoreDep,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ProcessingJob]:
    """List processing jobs."""
    return job_store.list_jobs(status=status_filter, limit=limit)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel job",
    description="Cancel a pending or running job.",
)
async def cancel_job(
    job_id: str,
    api_key: ApiKey,
    job_store: JobStoreDep,
) -> None:
    """Cancel a processing job."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )

    job_store.update_status(
        job_id,
        JobStatus.CANCELLED,
        completed_at=datetime.now(tz=timezone.utc),
    )


@router.get(
    "/stats",
    response_model=ProcessingStatsResponse,
    summary="Get processing statistics",
    description="Get aggregate statistics for all processing jobs.",
)
async def get_stats(
    api_key: ApiKey,
    job_store: JobStoreDep,
) -> ProcessingStatsResponse:
    """Get processing statistics."""
    all_jobs = job_store.list_jobs(limit=1000)
    completed_jobs = [j for j in all_jobs if j.status == JobStatus.COMPLETED]

    total_sessions = sum(j.processed_sessions for j in completed_jobs)
    total_entities = sum(
        (j.stats or {}).get("entities_created", 0) for j in completed_jobs
    )
    total_relationships = sum(
        (j.stats or {}).get("relationships_created", 0) for j in completed_jobs
    )
    total_cost = sum((j.stats or {}).get("total_cost_usd", 0.0) for j in completed_jobs)

    # Calculate average processing time
    processing_times = []
    for j in completed_jobs:
        if j.started_at and j.completed_at:
            delta = (j.completed_at - j.started_at).total_seconds()
            processing_times.append(delta)

    avg_time = sum(processing_times) / len(processing_times) if processing_times else 0

    # Calculate success rate
    all_sessions = sum(j.total_sessions for j in all_jobs)
    success_rate = total_sessions / all_sessions if all_sessions > 0 else 0

    return ProcessingStatsResponse(
        total_jobs=len(all_jobs),
        total_sessions_processed=total_sessions,
        total_entities_created=total_entities,
        total_relationships_created=total_relationships,
        total_cost_usd=total_cost,
        avg_processing_time_seconds=avg_time,
        success_rate=success_rate,
    )
