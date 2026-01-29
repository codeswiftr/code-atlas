"""Pipeline orchestration for Code Atlas."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from .config import AtlasSettings, SessionFilter
from .graph_populator import GraphPopulator
from .insight_extractor import CostGuard, ExtractionResult, InsightExtractor
from .logging_config import get_logger
from .metrics import AtlasMetrics, init_metrics
from .session_discovery import SessionDiscovery
from .session_parser import SessionParser
from .simple_history import SimpleHistory

console = Console()
logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for pipeline retry behavior and error handling."""

    max_retries: int = 3
    retry_delay_base: float = 1.0
    quarantine_dir: Path | None = None


@dataclass
class PipelineStats:
    sessions_processed: int = 0
    messages_parsed: int = 0
    total_tokens: int = 0
    entities_created: int = 0
    relationships_created: int = 0
    insights_logged: int = 0
    estimated_cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    retries_attempted: int = 0
    sessions_quarantined: int = 0


@dataclass
class PipelineRunner:
    discovery: SessionDiscovery
    extractor: InsightExtractor
    populator: GraphPopulator
    config: PipelineConfig = field(default_factory=PipelineConfig)
    settings: AtlasSettings | None = None
    metrics: AtlasMetrics | None = field(init=False, default=None)
    history: SimpleHistory | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        """Initialize cost guard, metrics, and history tracking if settings provided."""
        if self.settings:
            # Initialize cost guard if extractor uses LLM (any provider)
            if self.extractor.provider:
                cost_guard = CostGuard(
                    max_session=self.settings.max_cost_per_session_usd,
                    max_cumulative=self.settings.max_cumulative_cost_usd,
                )
                self.extractor.cost_guard = cost_guard

            # Initialize metrics if enabled
            if self.settings.enable_metrics:
                self.metrics = init_metrics(self.settings)

        # Always initialize history tracking
        self.history = SimpleHistory(
            history_file=Path.cwd() / ".forge" / "state" / "code_atlas_history.jsonl"
        )

    def run(self, limit: int | None = None) -> PipelineStats:
        stats = PipelineStats()
        sessions = self.discovery.discover(filters=SessionFilter(limit=limit))

        # Convert sessions to list to get count and for multiple iterations
        session_list = list(sessions) if sessions else []

        logger.info(
            "Pipeline run started",
            num_sessions_discovered=len(session_list),
            limit=limit,
        )

        # Update queue size metric
        if self.metrics:
            self.metrics.update_queue_size(len(session_list))

        for meta in session_list:
            self._process_session_with_retry(meta, stats)

        # Record final metrics
        if self.metrics:
            self.metrics.update_queue_size(0)  # Queue is empty after processing

        logger.info(
            "Pipeline run completed",
            sessions_processed=stats.sessions_processed,
            entities_created=stats.entities_created,
            relationships_created=stats.relationships_created,
            total_cost_usd=stats.estimated_cost_usd,
            errors_count=len(stats.errors),
        )

        return stats

    def _process_session_with_retry(self, meta, stats: PipelineStats) -> None:
        """Process a session with exponential backoff retry logic."""
        last_exception = None

        logger.debug(
            "Processing session",
            session_id=meta.session_id,
            project=meta.project,
            size_bytes=meta.size_bytes,
        )

        # Update active sessions metric
        if self.metrics:
            self.metrics.update_active_sessions(1)

        # Time the pipeline processing
        context_manager = (
            self.metrics.time_pipeline_processing(meta.project)
            if self.metrics
            else self._null_context_manager()
        )

        with context_manager:
            for attempt in range(self.config.max_retries):
                try:
                    parsed = SessionParser(metadata=meta).parse()
                    extraction = self.extractor.extract(parsed)
                    self.populator.upsert(parsed, extraction)
                    self._update_stats(stats, parsed.messages, extraction)

                    # Record success metrics
                    if self.metrics:
                        self.metrics.record_session_processed(meta.project, "success")

                    # Record success in history
                    if self.history:
                        self.history.record(
                            domain="code-atlas",
                            project=meta.project,
                            action="extract",
                            success=True,
                            context={
                                "session_id": meta.session_id,
                                "entities": len(extraction.entities),
                                "relationships": len(extraction.relationships),
                                "cost_usd": extraction.estimated_cost_usd,
                            }
                        )

                    logger.info(
                        "Session processed successfully",
                        session_id=meta.session_id,
                        entities_created=len(extraction.entities),
                        relationships_created=len(extraction.relationships),
                        cost_usd=extraction.estimated_cost_usd,
                    )
                    return  # Success - exit retry loop
                except Exception as exc:  # noqa: BLE001
                    last_exception = exc
                    stats.retries_attempted += 1

                    # Record error metrics
                    if self.metrics:
                        self.metrics.record_error("pipeline", type(exc).__name__)

                    if attempt < self.config.max_retries - 1:
                        # Exponential backoff
                        wait_time = self.config.retry_delay_base * (2**attempt)
                        logger.warning(
                            "Session processing failed, retrying",
                            session_id=meta.session_id,
                            attempt=attempt + 1,
                            max_retries=self.config.max_retries,
                            wait_time_seconds=wait_time,
                            error=str(exc),
                            error_type=type(exc).__name__,
                        )
                        console.print(
                            f"[yellow]Retry {attempt + 1}/{self.config.max_retries} "
                            f"for {meta.session_id}: {exc}. Waiting {wait_time}s...[/]"
                        )
                        time.sleep(wait_time)
                    else:
                        # Max retries exhausted - quarantine and record error
                        stats.errors.append(f"{meta.session_id}: {exc}")

                        # Record failure metrics
                        if self.metrics:
                            self.metrics.record_session_processed(meta.project, "failed")

                        # Record failure in history
                        if self.history:
                            self.history.record(
                                domain="code-atlas",
                                project=meta.project,
                                action="extract",
                                success=False,
                                context={
                                    "session_id": meta.session_id,
                                    "error": str(exc)[:200],  # Truncate long errors
                                    "error_type": type(exc).__name__,
                                }
                            )

                        logger.error(
                            "Session processing failed after max retries, quarantining",
                            session_id=meta.session_id,
                            max_retries=self.config.max_retries,
                            error=str(exc),
                            error_type=type(exc).__name__,
                        )
                        console.print(
                            f"[red]Failed processing {meta.session_id} after "
                            f"{self.config.max_retries} attempts: {exc}[/]"
                        )
                        self._quarantine_session(meta, last_exception)
                        stats.sessions_quarantined += 1
                finally:
                    # Update active sessions metric when done
                    if self.metrics:
                        self.metrics.update_active_sessions(0)

    def _null_context_manager(self):
        """Null context manager for when metrics are disabled."""
        from contextlib import nullcontext

        return nullcontext()

    def _quarantine_session(self, meta, exception: Exception) -> None:
        """Save failed session details to quarantine directory."""
        if not self.config.quarantine_dir:
            return

        self.config.quarantine_dir.mkdir(parents=True, exist_ok=True)

        quarantine_file = self.config.quarantine_dir / f"{meta.session_id}.json"
        quarantine_data = {
            "session_id": meta.session_id,
            "session_path": str(meta.path),
            "project": meta.project,
            "error": str(exception),
            "error_type": type(exception).__name__,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "size_bytes": meta.size_bytes,
        }

        with quarantine_file.open("w", encoding="utf-8") as f:
            json.dump(quarantine_data, f, indent=2)

        logger.warning(
            "Session quarantined",
            session_id=meta.session_id,
            quarantine_file=str(quarantine_file),
            error=str(exception),
            error_type=type(exception).__name__,
        )
        console.print(f"[yellow]Quarantined session details saved to {quarantine_file}[/]")

    def _update_stats(
        self,
        stats: PipelineStats,
        messages,
        extraction: ExtractionResult,
    ) -> None:
        stats.sessions_processed += 1
        stats.messages_parsed += len(messages)
        stats.total_tokens += sum(message.token_count or 0 for message in messages)
        stats.entities_created += len(extraction.entities)
        stats.relationships_created += len(extraction.relationships)
        stats.insights_logged += len(extraction.insights)
        stats.estimated_cost_usd += extraction.estimated_cost_usd

        # Record metrics
        if self.metrics:
            # Messages and tokens
            self.metrics.record_message_processed()
            self.metrics.record_tokens_processed(
                sum(message.token_count or 0 for message in messages)
            )

            # Cost
            self.metrics.record_session_cost(extraction.estimated_cost_usd)
            if extraction.estimated_cost_usd > 0:
                self.metrics.record_cost(
                    extraction.estimated_cost_usd,
                    extraction.extractor_model or "unknown",
                    "extraction",
                )

    def process_session(
        self, session_path: Path, use_llm: bool = True, dry_run: bool = False
    ) -> dict:
        """Process a single session and return results.

        Args:
            session_path: Path to session file
            use_llm: Whether to use LLM extraction
            dry_run: Whether to perform dry run (no database writes)

        Returns:
            Dictionary with processing results
        """
        from .session_discovery import SessionDiscovery

        logger.info(
            "Processing single session",
            session_path=str(session_path),
            use_llm=use_llm,
            dry_run=dry_run,
        )

        try:
            # Create session discovery and metadata
            discovery = SessionDiscovery(root=session_path.parent, settings=self.settings)
            meta = discovery._build_metadata(session_path)

            # Parse session
            parsed = SessionParser(metadata=meta).parse()

            # Extract insights
            if use_llm and not dry_run:
                extraction = self.extractor.extract(parsed)
            else:
                # Use heuristic extraction for dry run or when LLM disabled
                extraction = self.extractor._heuristic_extract(parsed)

            # Populate graph (skip if dry run)
            if not dry_run:
                self.populator.upsert(parsed, extraction)

            # Record success in history
            if self.history and not dry_run:
                self.history.record(
                    domain="code-atlas",
                    project=meta.project,
                    action="extract",
                    success=True,
                    context={
                        "session_id": meta.session_id,
                        "entities": len(extraction.entities),
                        "relationships": len(extraction.relationships),
                        "extraction_method": "llm" if use_llm else "heuristics",
                    }
                )

            # Return results
            return {
                "success": True,
                "session_id": meta.session_id,
                "entities_created": len(extraction.entities),
                "relationships_created": len(extraction.relationships),
                "cost_usd": extraction.estimated_cost_usd,
                "messages_processed": len(parsed.messages),
                "extraction_method": "llm" if use_llm else "heuristics",
            }

        except Exception as exc:
            logger.error(
                "Single session processing failed",
                session_path=str(session_path),
                error=str(exc),
                error_type=type(exc).__name__,
            )

            # Record failure in history
            if self.history:
                # Try to get project from path if meta doesn't exist
                try:
                    project = meta.project if 'meta' in locals() else session_path.parent.name
                except Exception:
                    project = "unknown"

                self.history.record(
                    domain="code-atlas",
                    project=project,
                    action="extract",
                    success=False,
                    context={
                        "session_path": str(session_path),
                        "error": str(exc)[:200],
                        "error_type": type(exc).__name__,
                    }
                )

            return {
                "success": False,
                "session_path": str(session_path),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "entities_created": 0,
                "relationships_created": 0,
                "cost_usd": 0.0,
            }
