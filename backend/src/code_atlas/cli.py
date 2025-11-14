"""Typer CLI entrypoints for Code Atlas."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import AtlasSettings, SessionFilter
from .graph_populator import GraphPopulator
from .insight_extractor import InsightExtractor
from .pipeline import PipelineRunner
from .session_discovery import SessionDiscovery

app = typer.Typer(help="Utilities for turning Claude sessions into structured knowledge.")
console = Console()


@app.command("discover")
def discover_sessions(
    root: Optional[Path] = typer.Option(None, help="Override Claude projects root."),
    include_project: list[str] = typer.Option(
        None, "--include-project", "-i", help="Project names to include."
    ),
    limit: Optional[int] = typer.Option(None, help="Maximum number of sessions to list."),
) -> None:
    """List discovered sessions."""

    settings = AtlasSettings()
    discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    filters = SessionFilter(include_projects=set(include_project or []), limit=limit)

    rows = discovery.discover(filters=filters)
    table = Table("Session ID", "Project", "Modified", "Size (KB)", title="Discovered Sessions")
    for meta in rows:
        table.add_row(
            meta.session_id,
            meta.project,
            meta.modified_at.isoformat(timespec="seconds"),
            f"{meta.size_bytes / 1024:.1f}",
        )
    console.print(table)


@app.command("run")
def run_pipeline(
    root: Optional[Path] = typer.Option(None, help="Override Claude projects root."),
    limit: Optional[int] = typer.Option(5, help="Limit number of sessions processed."),
    use_llm: bool = typer.Option(
        False, "--use-llm/--no-use-llm", help="Call Anthropic for extraction instead of heuristics."
    ),
    graph_url: Optional[str] = typer.Option(
        None,
        help="Redis/FalkorDB connection URL. Defaults to redis://localhost:6379 when not dry-run.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="When true, do not execute GRAPH.QUERY commands (just log).",
    ),
) -> None:
    """Placeholder pipeline that parses sessions and prints summaries."""

    settings = AtlasSettings()
    discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    extractor = InsightExtractor(use_llm=use_llm)
    populator = GraphPopulator(redis_url=graph_url, dry_run=dry_run)
    runner = PipelineRunner(discovery, extractor, populator)

    stats = runner.run(limit=limit)

    if stats.sessions_processed == 0:
        console.print("[yellow]No sessions processed. Check filters/root path.[/]")
        raise typer.Exit(code=0)

    table = Table(title="Pipeline Summary")
    table.add_column("Sessions")
    table.add_column("Messages")
    table.add_column("Tokens")
    table.add_column("Entities")
    table.add_column("Relationships")
    table.add_column("Insights")
    table.add_column("Est. Cost (USD)")
    table.add_row(
        str(stats.sessions_processed),
        str(stats.messages_parsed),
        str(stats.total_tokens),
        str(stats.entities_created),
        str(stats.relationships_created),
        str(stats.insights_logged),
        f"{stats.estimated_cost_usd:.2f}",
    )
    console.print(table)

    if stats.errors:
        console.print(f"[red]Encountered {len(stats.errors)} errors:[/]")
        for err in stats.errors:
            console.print(f" - {err}")
