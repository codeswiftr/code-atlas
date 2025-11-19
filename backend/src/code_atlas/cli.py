"""Typer CLI entrypoints for Code Atlas."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import AtlasSettings, SessionFilter
from .graph_populator import GraphPopulator
from .insight_extractor import InsightExtractor
from .logging_config import configure_logging
from .pipeline import PipelineRunner
from .session_discovery import SessionDiscovery

# Configure structured logging on module import
log_level = os.getenv("CODE_ATLAS_LOG_LEVEL", "INFO")
configure_logging(level=log_level)

app = typer.Typer(help="Utilities for turning Claude sessions into structured knowledge.")
console = Console()


def load_settings(config_path: Path | None = None) -> AtlasSettings:
    """Load settings with priority: --config flag > .code-atlas.toml > env vars > defaults.

    Args:
        config_path: Explicit config file path from --config flag

    Returns:
        AtlasSettings instance
    """
    # Priority 1: Explicit --config flag
    if config_path:
        if not config_path.exists():
            console.print(f"[red]Config file not found: {config_path}[/]")
            raise typer.Exit(code=1)
        return AtlasSettings.from_toml_with_env_override(config_path)

    # Priority 2: .code-atlas.toml in current directory
    default_config = Path.cwd() / ".code-atlas.toml"
    if default_config.exists():
        console.print(f"[dim]Loading config from {default_config}[/]")
        return AtlasSettings.from_toml_with_env_override(default_config)

    # Priority 3: Environment variables + defaults
    return AtlasSettings()


@app.command("discover")
def discover_sessions(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    root: Path | None = typer.Option(None, help="Override Claude projects root."),
    include_project: list[str] = typer.Option(
        None, "--include-project", "-i", help="Project names to include."
    ),
    limit: int | None = typer.Option(None, help="Maximum number of sessions to list."),
) -> None:
    """List discovered sessions."""

    settings = load_settings(config)
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
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    root: Path | None = typer.Option(None, help="Override Claude projects root."),
    limit: int | None = typer.Option(5, help="Limit number of sessions processed."),
    use_llm: bool = typer.Option(
        False, "--use-llm/--no-use-llm", help="Call Anthropic for extraction."
    ),
    graph_url: str | None = typer.Option(
        None,
        help="Redis/FalkorDB URL. Defaults to redis://localhost:6379 when not dry-run.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="When true, do not execute GRAPH.QUERY commands (just log).",
    ),
) -> None:
    """Placeholder pipeline that parses sessions and prints summaries."""

    settings = load_settings(config)
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


@app.command("report")
def generate_report(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_name: str = typer.Option("code_atlas", help="Graph name in FalkorDB."),
    redis_url: str = typer.Option("redis://localhost:6379", help="FalkorDB connection URL."),
    top_n: int = typer.Option(10, help="Number of top entities to show."),
) -> None:
    """Generate summary report from knowledge graph."""
    import redis
    from rich.panel import Panel

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        console.print(f"[red]Failed to connect to FalkorDB at {redis_url}[/]")
        console.print(f"[red]Error: {e}[/]")
        console.print("[yellow]Make sure FalkorDB is running: docker compose up -d[/]")
        raise typer.Exit(code=1) from e

    def query_graph(cypher: str) -> list[list]:
        """Execute Cypher query and return results."""
        try:
            result = client.execute_command("GRAPH.QUERY", graph_name, cypher, "--compact")
            # FalkorDB returns: [header, rows, stats]
            if isinstance(result, list) and len(result) >= 2:
                return result[1] if result[1] else []
            return []
        except redis.RedisError as e:
            console.print(f"[red]Query failed: {e}[/]")
            return []  # Graceful failure, return empty results

    # Top files by mentions
    files_query = f"""
    MATCH (f:File)<-[r:MENTIONS]-()
    RETURN f.name, COUNT(r) AS mentions
    ORDER BY mentions DESC
    LIMIT {top_n}
    """
    files_result = query_graph(files_query)

    if files_result:
        files_table = Table("File", "Mentions", title=f"Top {top_n} Files")
        for row in files_result:
            files_table.add_row(str(row[0]), str(row[1]))
        console.print(files_table)
    else:
        console.print("[yellow]No files found in graph[/]")

    # Top concepts
    concepts_query = f"""
    MATCH (c:Concept)<-[r:MENTIONS]-()
    RETURN c.name, COUNT(r) AS mentions
    ORDER BY mentions DESC
    LIMIT {top_n}
    """
    concepts_result = query_graph(concepts_query)

    if concepts_result:
        concepts_table = Table("Concept", "Mentions", title=f"Top {top_n} Concepts")
        for row in concepts_result:
            concepts_table.add_row(str(row[0]), str(row[1]))
        console.print(concepts_table)
    else:
        console.print("[yellow]No concepts found in graph[/]")

    # Session statistics
    stats_query = """
    MATCH (s:Session)
    RETURN COUNT(s) AS total_sessions,
           AVG(s.size_bytes) AS avg_size,
           SUM(s.size_bytes) AS total_size
    """
    stats_result = query_graph(stats_query)

    if stats_result and stats_result[0]:
        total_sessions = stats_result[0][0]
        avg_size = stats_result[0][1]
        total_size = stats_result[0][2]

        stats_text = f"""
[bold]Total Sessions:[/bold] {total_sessions}
[bold]Average Size:[/bold] {avg_size / 1024:.1f} KB
[bold]Total Size:[/bold] {total_size / (1024 * 1024):.2f} MB
        """
        console.print(Panel(stats_text.strip(), title="Session Statistics", expand=False))
    else:
        console.print("[yellow]No session statistics available[/]")

    # Recent sessions
    recent_query = f"""
    MATCH (s:Session)
    RETURN s.id, s.project, s.modified_at
    ORDER BY s.modified_at DESC
    LIMIT {top_n}
    """
    recent_result = query_graph(recent_query)

    if recent_result:
        from datetime import datetime

        recent_table = Table("Session ID", "Project", "Modified", title=f"Recent {top_n} Sessions")
        for row in recent_result:
            session_id = str(row[0])[:12] + "..."  # Truncate for display
            project = str(row[1])
            modified = datetime.fromtimestamp(float(row[2])).strftime("%Y-%m-%d %H:%M")
            recent_table.add_row(session_id, project, modified)
        console.print(recent_table)
    else:
        console.print("[yellow]No recent sessions found[/]")

    # Summary message
    if not any([files_result, concepts_result, stats_result, recent_result]):
        msg = "Graph appears to be empty. Run 'code-atlas run' to populate it."
        console.print(f"\n[yellow]{msg}[/]")
