"""Typer CLI entrypoints for Code Atlas."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import AtlasSettings, SessionFilter
from .graph_populator import GraphPopulator
from .insight_extractor import InsightExtractor
from .logging_config import configure_logging
from .metrics import init_metrics
from .pipeline import PipelineRunner
from .server import MetricsServer
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
        False, "--use-llm/--no-use-llm", help="Use LLM for extraction (Anthropic or OpenRouter)."
    ),
    provider: str = typer.Option(
        None, "--provider", help="LLM provider: 'anthropic' or 'openrouter'. Defaults to config/env."
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
    """Run the Code Atlas pipeline to process sessions."""

    settings = load_settings(config)
    discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    
    # Determine provider: CLI flag > config > env > default
    llm_provider = provider or settings.llm_provider
    if llm_provider and llm_provider not in ("anthropic", "openrouter"):
        console.print(f"[red]Invalid provider '{llm_provider}'. Must be 'anthropic' or 'openrouter'.[/]")
        raise typer.Exit(code=1)
    
    extractor = InsightExtractor(
        use_llm=use_llm,
        provider=llm_provider if llm_provider else None,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_model=settings.openrouter_model,
        openrouter_base_url=settings.openrouter_base_url,
    )

    # Initialize metrics if enabled
    metrics = init_metrics(settings) if settings.enable_metrics else None

    populator = GraphPopulator(
        redis_url=graph_url,
        dry_run=dry_run,
        create_indexes=settings.create_db_indexes,
        index_timeout=settings.db_index_creation_timeout,
        verify_indexes_after_creation=settings.verify_indexes,
        metrics=metrics
    )

    # Pass metrics to extractor and populator
    extractor.metrics = metrics

    runner = PipelineRunner(
        discovery, extractor, populator, settings=settings
    )

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

    # Show metrics status if enabled
    if settings.enable_metrics:
        console.print(f"\n[green]✅ Metrics enabled and available at http://{settings.metrics_host}:{settings.metrics_port}{settings.metrics_path}[/]")


@app.command("metrics")
def start_metrics_server(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    host: str | None = typer.Option(
        None, "--host", help="Override metrics server host."
    ),
    port: int | None = typer.Option(
        None, "--port", help="Override metrics server port."
    ),
    daemon: bool = typer.Option(
        False, "--daemon", help="Run metrics server in daemon mode (background)."
    ),
) -> None:
    """Start the Prometheus metrics server for monitoring."""
    import threading
    from rich.panel import Panel

    settings = load_settings(config)

    # Override settings with CLI arguments if provided
    if host:
        settings.metrics_host = host
    if port:
        settings.metrics_port = port

    if not settings.enable_metrics:
        console.print("[yellow]Metrics collection is disabled in configuration.[/]")
        console.print("Set enable_metrics = true in your .code-atlas.toml or use CODE_ATLAS_ENABLE_METRICS=true")
        raise typer.Exit(code=1)

    # Start metrics server
    console.print(f"[blue]Starting metrics server...[/]")
    console.print(Panel(
        f"[bold]Metrics Server[/bold]\n"
        f"Host: {settings.metrics_host}\n"
        f"Port: {settings.metrics_port}\n"
        f"Metrics: http://{settings.metrics_host}:{settings.metrics_port}{settings.metrics_path}\n"
        f"Health: http://{settings.metrics_host}:{settings.metrics_port}{settings.health_path}\n"
        f"Status: http://{settings.metrics_host}:{settings.metrics_port}{settings.status_path}",
        title="Monitoring Configuration",
        expand=False
    ))

    try:
        if daemon:
            # Run in daemon thread (non-blocking)
            def run_server():
                server = MetricsServer(settings)
                server.run()

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            console.print("[green]✅ Metrics server started in daemon mode[/]")
            console.print("[dim]Press Ctrl+C to stop[/]")

            # Keep main thread alive
            try:
                while server_thread.is_alive():
                    server_thread.join(timeout=1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping metrics server...[/]")
        else:
            # Run in foreground (blocking)
            server = MetricsServer(settings)
            server.run()

    except Exception as e:
        console.print(f"[red]Failed to start metrics server: {e}[/]")
        raise typer.Exit(code=1) from e


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


@app.command("indexes")
def manage_indexes(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_name: str = typer.Option("code_atlas", help="Graph name in FalkorDB."),
    redis_url: str = typer.Option("redis://localhost:6379", help="FalkorDB connection URL."),
    action: str = typer.Option(
        "list", "--action", "-a",
        help="Action: list, create, verify, drop"
    ),
) -> None:
    """Manage database indexes for optimal query performance."""
    from rich.panel import Panel
    from rich.table import Table
    import redis

    # Load settings
    settings = load_settings(config)

    # Test connection
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        console.print(f"[red]Failed to connect to FalkorDB at {redis_url}[/]")
        console.print(f"[red]Error: {e}[/]")
        console.print("[yellow]Make sure FalkorDB is running: docker compose up -d[/]")
        raise typer.Exit(code=1) from e

    # Create populator for index management
    populator = GraphPopulator(
        graph_name=graph_name,
        redis_url=redis_url,
        dry_run=False,
        create_indexes=settings.create_db_indexes,
        index_timeout=settings.db_index_creation_timeout,
        verify_indexes_after_creation=settings.verify_indexes
    )

    if action == "list":
        console.print(Panel("Database Index Configuration", expand=False))

        indexes = populator.list_indexes()
        table = Table("Category", "Index Count", "Description")

        category_descriptions = {
            "Session": "Indexes for Session nodes (id, project, modified_at, size)",
            "Entity": "Indexes for File and Concept entities (id, name, type)",
            "Insight": "Indexes for Insight nodes (id)",
            "Relationships": "Indexes for MENTIONS relationships (confidence, timestamp)",
            "FullText": "Full-text search indexes for entity names"
        }

        for category, index_list in indexes.items():
            table.add_row(
                category,
                str(len(index_list)),
                category_descriptions.get(category, "Unknown category")
            )

        console.print(table)

        total_indexes = sum(len(indexes) for indexes in indexes.values())
        console.print(f"\n[dim]Total indexes defined: {total_indexes}[/]")

    elif action == "create":
        console.print(f"[blue]Creating indexes in graph '{graph_name}'...[/]")

        # Force index creation by creating a new populator
        creation_populator = GraphPopulator(
            graph_name=graph_name,
            redis_url=redis_url,
            dry_run=False,
            create_indexes=True,
            index_timeout=settings.db_index_creation_timeout,
            verify_indexes_after_creation=settings.verify_indexes
        )

        # Count index creation queries
        index_queries = [q for q in creation_populator.executed_queries
                        if "CREATE INDEX" in q or "FULLTEXT INDEX" in q]

        console.print(f"[green]✅ {len(index_queries)} index creation queries executed[/]")

        if settings.verify_indexes:
            console.print("[blue]Verifying index creation...[/]")
            verification_result = creation_populator.verify_indexes()

            success_count = sum(
                1 for cat_status in verification_result.values()
                if isinstance(cat_status, dict) and any(status is True for status in cat_status.values())
            )
            console.print(f"[green]✅ Index verification completed for {success_count} categories[/]")

    elif action == "verify":
        console.print(f"[blue]Verifying indexes in graph '{graph_name}'...[/]")

        verification_result = populator.verify_indexes()

        if "error" in verification_result:
            console.print(f"[red]❌ {verification_result['error']}[/]")
        else:
            table = Table("Category", "Index Name", "Status")

            for category, index_status in verification_result.items():
                if isinstance(index_status, dict):
                    for index_name, status in index_status.items():
                        status_icon = "✅" if status else "❌"
                        status_text = "Exists" if status else "Missing"
                        table.add_row(category, index_name, f"{status_icon} {status_text}")

            if table.row_count > 0:
                console.print(table)
            else:
                console.print("[yellow]No index status information available[/]")

    elif action == "drop":
        console.print(f"[yellow]⚠️  Dropping all indexes from graph '{graph_name}'...[/]")

        if not typer.confirm("This will remove all indexes. Continue?", default=False):
            console.print("[dim]Operation cancelled.[/]")
            return

        populator.drop_indexes()

        console.print("[green]✅ Index drop operation completed[/]")
        console.print("[yellow]Note: Some indexes may be automatically recreated on next startup[/]")

    else:
        console.print(f"[red]Invalid action: {action}[/]")
        console.print("Valid actions: list, create, verify, drop")
        raise typer.Exit(code=1)


@app.command("serve")
def serve_api(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind the server to."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes."),
) -> None:
    """Start the Code Atlas API server.

    This command starts a FastAPI server that provides:
    - Session discovery and processing endpoints
    - Knowledge graph query and visualization APIs
    - Health checks and Prometheus metrics

    Example usage:
        # Start server with defaults
        code-atlas serve

        # Start on custom port with auto-reload
        code-atlas serve --port 9000 --reload

        # Production mode with multiple workers
        code-atlas serve --workers 4
    """
    import uvicorn

    settings = load_settings(config)

    # Update settings with CLI overrides
    settings.metrics_host = host
    settings.metrics_port = port
    settings.enable_metrics = True

    console.print(Panel.fit(
        f"[bold blue]Code Atlas API Server[/]\n\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Workers: {workers}\n"
        f"Reload: {reload}\n"
        f"\n[dim]API docs: http://{host}:{port}/docs[/]",
        title="Starting Server",
    ))

    # Import here to avoid circular imports
    from .api.main import create_app

    if reload:
        # Development mode with auto-reload
        uvicorn.run(
            "code_atlas.api.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
        )
    else:
        # Production mode
        app_instance = create_app(settings)
        uvicorn.run(
            app_instance,
            host=host,
            port=port,
            workers=workers,
            log_level="info",
        )
