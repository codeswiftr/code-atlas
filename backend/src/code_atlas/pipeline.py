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
from .session_discovery import SessionDiscovery
from .session_parser import SessionParser

console = Console()


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

    def __post_init__(self) -> None:
        """Initialize cost guard if settings provided and extractor uses LLM."""
        if self.settings and self.extractor.client:
            cost_guard = CostGuard(
                max_session=self.settings.max_cost_per_session_usd,
                max_cumulative=self.settings.max_cumulative_cost_usd,
            )
            self.extractor.cost_guard = cost_guard

    def run(self, limit: int | None = None) -> PipelineStats:
        stats = PipelineStats()
        sessions = self.discovery.discover(filters=SessionFilter(limit=limit))

        for meta in sessions:
            self._process_session_with_retry(meta, stats)

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
