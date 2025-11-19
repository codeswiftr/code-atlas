"""Pipeline orchestration for Code Atlas."""

from __future__ import annotations

import json
import multiprocessing
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict

from rich.console import Console

from .config import AtlasSettings, SessionFilter
from .exceptions import CodeAtlasError
from .graph_populator import GraphPopulator
from .insight_extractor import CostGuard, ExtractionResult, InsightExtractor
from .session_discovery import SessionDiscovery
from .session_parser import SessionParser

console = Console()


@dataclass
class PipelineConfig:
    """Configuration for pipeline retry behavior and error handling."""

    max_retries: int = 3
    retry_delay_base: float = 1.0
    quarantine_dir: Path | None = None
    parallel_workers: int | None = None  # None = auto-detect CPU count
    enable_parallel: bool = False  # Disabled by default for safety
    min_sessions_for_parallel: int = 5  # Minimum sessions to enable parallel processing


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

    def __post_init__(self) -> None:
        """Initialize cost guard if settings provided and extractor uses LLM."""
        if self.settings and self.extractor.client:
            cost_guard = CostGuard(
                max_session=self.settings.max_cost_per_session_usd,
                max_cumulative=self.settings.max_cumulative_cost_usd,
            )
            self.extractor.cost_guard = cost_guard

    def run(self, limit: int | None = None) -> PipelineStats:
        """Run the pipeline with optional parallel processing."""
        # Use generator for memory efficiency with large session sets
        session_generator = self.discovery.discover_generator(filters=SessionFilter(limit=limit))

        # Convert to list to check count (needed for parallel decision)
        sessions = list(session_generator)
        session_count = len(sessions)

        # Decide whether to use parallel processing
        should_use_parallel = (
            self.config.enable_parallel and
            session_count >= self.config.min_sessions_for_parallel and
            not self.extractor.client  # Don't use parallel with LLM calls to avoid API rate limits
        )

        console.print(f"[dim]Processing {session_count} sessions "
                     f"{'in parallel' if should_use_parallel else 'sequentially'}[/]")

        if should_use_parallel:
            return self._run_parallel(sessions)
        else:
            return self._run_sequential(sessions)

    def _run_sequential(self, sessions: list) -> PipelineStats:
        """Process sessions sequentially (original behavior)."""
        stats = PipelineStats()

        for meta in sessions:
            self._process_session_with_retry(meta, stats)

        return stats

    def _run_parallel(self, sessions: list) -> PipelineStats:
        """Process sessions in parallel using ProcessPoolExecutor."""
        stats = PipelineStats()

        # Determine worker count
        worker_count = self.config.parallel_workers or min(
            multiprocessing.cpu_count(),
            len(sessions)
        )

        console.print(f"[dim]Using {worker_count} parallel workers[/]")

        # Process sessions in parallel
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            # Submit all tasks
            future_to_session = {
                executor.submit(_process_session_worker, session_meta): session_meta
                for session_meta in sessions
            }

            # Collect results as they complete
            for future in as_completed(future_to_session):
                session_meta = future_to_session[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per session
                    if result["success"]:
                        # Update stats from successful processing
                        self._update_stats_from_result(stats, result)
                    else:
                        # Handle failed processing
                        error_msg = f"{session_meta.session_id}: {result['error']}"
                        stats.errors.append(error_msg)
                        stats.sessions_quarantined += 1
                        console.print(f"[red]Failed processing {session_meta.session_id}: {result['error']}[/]")

                except Exception as exc:
                    # Handle unexpected errors
                    error_msg = f"{session_meta.session_id}: {exc}"
                    stats.errors.append(error_msg)
                    console.print(f"[red]Unexpected error processing {session_meta.session_id}: {exc}[/]")

        return stats

    def _process_session_with_retry(self, meta, stats: PipelineStats) -> None:
        """Process a session with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                parsed = SessionParser(metadata=meta).parse()
                extraction = self.extractor.extract(parsed)
                self.populator.upsert(parsed, extraction)
                self._update_stats(stats, parsed.messages, extraction)
                return  # Success - exit retry loop
            except Exception as exc:  # noqa: BLE001
                last_exception = exc
                stats.retries_attempted += 1

                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    wait_time = self.config.retry_delay_base * (2**attempt)
                    console.print(
                        f"[yellow]Retry {attempt + 1}/{self.config.max_retries} "
                        f"for {meta.session_id}: {exc}. Waiting {wait_time}s...[/]"
                    )
                    time.sleep(wait_time)
                else:
                    # Max retries exhausted - quarantine and record error
                    stats.errors.append(f"{meta.session_id}: {exc}")
                    console.print(f"[red]Failed processing {meta.session_id} after "
                                  f"{self.config.max_retries} attempts: {exc}[/]")
                    self._quarantine_session(meta, last_exception)
                    stats.sessions_quarantined += 1

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

    def _update_stats_from_result(self, stats: PipelineStats, result: Dict[str, Any]) -> None:
        """Update stats from a successful parallel processing result."""
        stats.sessions_processed += 1
        stats.messages_parsed += result.get("messages_count", 0)
        stats.total_tokens += result.get("total_tokens", 0)
        stats.entities_created += result.get("entities_count", 0)
        stats.relationships_created += result.get("relationships_count", 0)
        stats.insights_logged += result.get("insights_count", 0)
        stats.estimated_cost_usd += result.get("estimated_cost_usd", 0.0)


# Worker function for parallel processing (must be top-level for multiprocessing)
def _process_session_worker(session_meta) -> Dict[str, Any]:
    """
    Worker function to process a single session in a separate process.

    This function runs in a separate process and must be self-contained.
    It returns a dictionary with the processing result.
    """
    try:
        # Import inside function to avoid multiprocessing issues with circular imports
        from .session_parser import SessionParser
        from .insight_extractor import InsightExtractor

        # Parse the session
        parser = SessionParser(metadata=session_meta)
        parsed = parser.parse()

        # Use heuristic extraction for parallel processing (no LLM API calls)
        extractor = InsightExtractor(use_llm=False)
        extraction = extractor.extract(parsed)

        return {
            "success": True,
            "session_id": session_meta.session_id,
            "messages_count": len(parsed.messages),
            "total_tokens": sum(message.token_count or 0 for message in parsed.messages),
            "entities_count": len(extraction.entities),
            "relationships_count": len(extraction.relationships),
            "insights_count": len(extraction.insights),
            "estimated_cost_usd": extraction.estimated_cost_usd,
            "parsed": parsed,
            "extraction": extraction,
        }

    except Exception as exc:
        return {
            "success": False,
            "session_id": getattr(session_meta, "session_id", "unknown"),
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
