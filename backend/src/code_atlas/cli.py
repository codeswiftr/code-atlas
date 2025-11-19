"""Typer CLI entrypoints for Code Atlas."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
import typer
from rich.console import Console
from rich.table import Table

from .config import AtlasSettings, SessionFilter, setup_logging
from .graph_populator import GraphPopulator
from .insight_extractor import InsightExtractor
from .pipeline import PipelineRunner
from .session_discovery import SessionDiscovery

app = typer.Typer(help="Utilities for turning Claude sessions into structured knowledge.")
console = Console()


def load_settings(config_path: Optional[Path] = None) -> AtlasSettings:
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
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    json_logs: bool = typer.Option(False, help="Force JSON logging output"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to .code-atlas.toml config file."),
    root: Optional[Path] = typer.Option(None, help="Override Claude projects root."),
    include_project: list[str] = typer.Option(
        None, "--include-project", "-i", help="Project names to include."
    ),
    limit: Optional[int] = typer.Option(None, help="Maximum number of sessions to list."),
) -> None:
    """List discovered sessions."""

    # Initialize structured logging
    setup_logging(log_level=log_level, json_output=json_logs)
    logger = structlog.get_logger()

    logger.info("Starting session discovery", limit=limit, root=root)

    try:
        settings = load_settings(config)
        logger.info("Settings loaded", claude_root=settings.claude_root)
    except Exception as e:
        logger.error("Failed to load settings", error=str(e))
        raise
    discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    filters = SessionFilter(include_projects=set(include_project or []), limit=limit)

    try:
        rows = discovery.discover(filters=filters)
        session_count = len(rows)
        logger.info("Session discovery completed", count=session_count)

        if session_count == 0:
            logger.warning("No sessions discovered")
            console.print("[yellow]No sessions found matching the criteria.[/]")
            return

        table = Table("Session ID", "Project", "Modified", "Size (KB)", title="Discovered Sessions")
        for meta in rows:
            table.add_row(
                meta.session_id,
                meta.project,
                meta.modified_at.isoformat(timespec="seconds"),
                f"{meta.size_bytes / 1024:.1f}",
            )
        console.print(table)

    except Exception as e:
        logger.error("Session discovery failed", error=str(e))
        raise


@app.command("run")
def run_pipeline(
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    json_logs: bool = typer.Option(False, help="Force JSON logging output"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to .code-atlas.toml config file."),
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
    """Execute pipeline to process sessions and populate knowledge graph."""

    # Initialize structured logging
    setup_logging(log_level=log_level, json_output=json_logs)
    logger = structlog.get_logger()

    logger.info("Starting pipeline execution", limit=limit, use_llm=use_llm, dry_run=dry_run, graph_url=graph_url)

    try:
        settings = load_settings(config)
        logger.info("Settings loaded", claude_root=settings.claude_root)
    except Exception as e:
        logger.error("Failed to load settings", error=str(e))
        raise
    discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    extractor = InsightExtractor(use_llm=use_llm)
    populator = GraphPopulator(redis_url=graph_url, dry_run=dry_run)
    runner = PipelineRunner(discovery, extractor, populator)

    try:
        stats = runner.run(limit=limit)

        logger.info(
            "Pipeline execution completed",
            sessions_processed=stats.sessions_processed,
            messages_parsed=stats.messages_parsed,
            total_tokens=stats.total_tokens,
            entities_created=stats.entities_created,
            relationships_created=stats.relationships_created,
            insights_logged=stats.insights_logged,
            estimated_cost_usd=stats.estimated_cost_usd,
            errors_count=len(stats.errors)
        )

        if stats.sessions_processed == 0:
            logger.warning("No sessions processed")
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
            logger.error("Pipeline completed with errors", error_count=len(stats.errors))
            console.print(f"[red]Encountered {len(stats.errors)} errors:[/]")
            for err in stats.errors:
                logger.error("Pipeline error", error=err)
                console.print(f" - {err}")

    except Exception as e:
        logger.error("Pipeline execution failed", error=str(e))
        raise


@app.command("report")
def generate_report(
    log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    json_logs: bool = typer.Option(False, help="Force JSON logging output"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to .code-atlas.toml config file."),
    graph_name: str = typer.Option("code_atlas", help="Graph name in FalkorDB."),
    redis_url: str = typer.Option("redis://localhost:6379", help="FalkorDB connection URL."),
    top_n: int = typer.Option(10, help="Number of top entities to show."),
) -> None:
    """Generate summary report from knowledge graph."""
    import redis
    from rich.panel import Panel

    # Initialize structured logging
    setup_logging(log_level=log_level, json_output=json_logs)
    logger = structlog.get_logger()

    logger.info("Generating knowledge graph report", graph_name=graph_name, redis_url=redis_url, top_n=top_n)

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("Successfully connected to FalkorDB")
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error("Failed to connect to FalkorDB", redis_url=redis_url, error=str(e))
        console.print(f"[red]Failed to connect to FalkorDB at {redis_url}[/]")
        console.print(f"[red]Error: {e}[/]")
        console.print("[yellow]Make sure FalkorDB is running: docker compose up -d[/]")
        raise typer.Exit(code=1)

    def query_graph(cypher: str) -> list[list]:
        """Execute Cypher query and return results."""
        try:
            logger.debug("Executing Cypher query", query=cypher)
            result = client.execute_command("GRAPH.QUERY", graph_name, cypher, "--compact")
            # FalkorDB returns: [header, rows, stats]
            if isinstance(result, list) and len(result) >= 2:
                rows = result[1] if result[1] else []
                logger.debug("Query executed successfully", rows_returned=len(rows))
                return rows
            logger.warning("Unexpected query result format", result=result)
            return []
        except redis.RedisError as e:
            logger.error("Cypher query failed", query=cypher, error=str(e))
            console.print(f"[red]Query failed: {e}[/]")
            return []

    # Top files by mentions
    files_query = f"""
    MATCH (f:File)<-[r:MENTIONS]-()
    RETURN f.name, COUNT(r) AS mentions
    ORDER BY mentions DESC
    LIMIT {top_n}
    """
    files_result = query_graph(files_query)

    if files_result:
        logger.info("Found files in graph", count=len(files_result))
        files_table = Table("File", "Mentions", title=f"Top {top_n} Files")
        for row in files_result:
            files_table.add_row(str(row[0]), str(row[1]))
        console.print(files_table)
    else:
        logger.warning("No files found in graph")
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
        logger.info("Found concepts in graph", count=len(concepts_result))
        concepts_table = Table("Concept", "Mentions", title=f"Top {top_n} Concepts")
        for row in concepts_result:
            concepts_table.add_row(str(row[0]), str(row[1]))
        console.print(concepts_table)
    else:
        logger.warning("No concepts found in graph")
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

        logger.info(
            "Session statistics retrieved",
            total_sessions=total_sessions,
            avg_size_kb=avg_size / 1024 if avg_size else 0,
            total_size_mb=total_size / (1024 * 1024) if total_size else 0
        )

        stats_text = f"""
[bold]Total Sessions:[/bold] {total_sessions}
[bold]Average Size:[/bold] {avg_size / 1024:.1f} KB
[bold]Total Size:[/bold] {total_size / (1024 * 1024):.2f} MB
        """
        console.print(Panel(stats_text.strip(), title="Session Statistics", expand=False))
    else:
        logger.warning("No session statistics available")
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

        logger.info("Found recent sessions", count=len(recent_result))
        recent_table = Table("Session ID", "Project", "Modified", title=f"Recent {top_n} Sessions")
        for row in recent_result:
            session_id = str(row[0])[:12] + "..."  # Truncate for display
            project = str(row[1])
            modified = datetime.fromtimestamp(float(row[2])).strftime("%Y-%m-%d %H:%M")
            recent_table.add_row(session_id, project, modified)
        console.print(recent_table)
    else:
        logger.warning("No recent sessions found")
        console.print("[yellow]No recent sessions found[/]")

    # Summary message
    if not any([files_result, concepts_result, stats_result, recent_result]):
        logger.warning("Graph appears to be empty")
        console.print("\n[yellow]Graph appears to be empty. Run 'code-atlas run' to populate it.[/]")
    else:
        logger.info("Report generation completed successfully")
