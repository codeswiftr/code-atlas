"""Typer CLI entrypoints for Code Atlas."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import redis
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
from .rag_service import create_rag_service
from .server import MetricsServer
from .session_discovery import SessionDiscovery
from .vector_store import VectorStore

# Configure structured logging on module import
log_level = os.getenv("CODE_ATLAS_LOG_LEVEL", "INFO")
configure_logging(level=log_level)

app = typer.Typer(
    help="Utilities for turning Claude sessions into structured knowledge.",
    no_args_is_help=True,
)
console = Console()

# Version from pyproject.toml
VERSION = "0.1.0"


def load_settings(config_path: Path | None = None) -> AtlasSettings:
    """Load settings with priority: --config flag > .code-atlas.toml > env vars > defaults."""
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


def output_json(data: dict[str, Any]) -> None:
    """Output data as JSON for agent parsing using FORGE standard schema."""
    console.print_json(json.dumps(data, default=str))


def output_success(result: dict[str, Any], start_time: float, json_mode: bool = False) -> None:
    """Output success result in FORGE standard format.

    Args:
        result: Command-specific result data
        start_time: Start time from time.time()
        json_mode: Whether to output JSON or human-readable format
    """
    if json_mode:
        duration_ms = int((time.time() - start_time) * 1000)
        response = {
            "success": True,
            "result": result,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": duration_ms,
            "metadata": {"version": VERSION},
        }
        output_json(response)
    else:
        console.print("[green]✓[/green] Command completed successfully")


def output_error(
    error_code: str, message: str, start_time: float | None = None, json_mode: bool = False
) -> None:
    """Output error in FORGE standard format.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        start_time: Optional start time for duration tracking
        json_mode: Whether to output JSON or human-readable format
    """
    if json_mode:
        response = {
            "success": False,
            "error": {"code": error_code, "message": message},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if start_time:
            response["duration_ms"] = int((time.time() - start_time) * 1000)
        output_json(response)
    else:
        console.print(f"[red]✗[/red] {message}")
    raise typer.Exit(code=1)


# =============================================================================
# DISCOVER COMMAND
# =============================================================================


@app.command("discover")
def discover_sessions(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    root: Path | None = typer.Option(None, help="Override Claude projects root."),
    include_project: list[str] = typer.Option(
        None, "--include-project", "-i", help="Project names to include."
    ),
    exclude_project: list[str] = typer.Option(
        None, "--exclude-project", "-e", help="Project names to exclude."
    ),
    limit: int | None = typer.Option(None, help="Maximum number of sessions to list."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing."),
) -> None:
    """List discovered sessions."""
    settings = load_settings(config)

    try:
        discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    except FileNotFoundError as e:
        output_error(
            "discover",
            "ROOT_NOT_FOUND",
            str(e),
            {"root": str(root or settings.claude_root)},
            json_output,
        )
        return

    filters = SessionFilter(
        include_projects=set(include_project or []),
        exclude_projects=set(exclude_project or []),
        limit=limit,
    )

    rows = discovery.discover(filters=filters)

    if json_output:
        sessions_data = [
            {
                "session_id": meta.session_id,
                "project": meta.project,
                "path": str(meta.path),
                "size_bytes": meta.size_bytes,
                "modified_at": meta.modified_at.isoformat(),
            }
            for meta in rows
        ]
        output_json(
            {
                "success": True,
                "operation": "discover",
                "count": len(sessions_data),
                "sessions": sessions_data,
            }
        )
    else:
        table = Table("Session ID", "Project", "Modified", "Size (KB)", title="Discovered Sessions")
        for meta in rows:
            table.add_row(
                meta.session_id,
                meta.project,
                meta.modified_at.isoformat(timespec="seconds"),
                f"{meta.size_bytes / 1024:.1f}",
            )
        console.print(table)


# =============================================================================
# INDEX COMMAND (alias for run)
# =============================================================================


@app.command("index")
def index_sessions(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    root: Path | None = typer.Option(None, help="Override Claude projects root."),
    limit: int | None = typer.Option(5, help="Limit number of sessions processed."),
    use_llm: bool = typer.Option(
        False, "--use-llm/--no-use-llm", help="Use LLM for extraction (Anthropic or OpenRouter)."
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="LLM provider: 'anthropic' or 'openrouter'. Defaults to config/env.",
    ),
    graph_url: str | None = typer.Option(
        None,
        "--graph-url",
        "-g",
        help="Redis/FalkorDB URL. Defaults to redis://localhost:6379.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run/--no-dry-run",
        help="When true, do not execute GRAPH.QUERY commands (just log).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing."),
) -> None:
    """Index Claude Code sessions into the knowledge graph.

    Alias for 'run' command - processes sessions and populates the graph.
    """
    settings = load_settings(config)

    try:
        discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    except FileNotFoundError as e:
        output_error(
            "index",
            "ROOT_NOT_FOUND",
            str(e),
            {"root": str(root or settings.claude_root)},
            json_output,
        )
        return

    # Determine provider: CLI flag > config > env > default
    llm_provider = provider or settings.llm_provider
    if llm_provider and llm_provider not in ("anthropic", "openrouter"):
        output_error(
            "index",
            "INVALID_PROVIDER",
            f"Invalid provider '{llm_provider}'. Must be 'anthropic' or 'openrouter'.",
            {"valid": ["anthropic", "openrouter"]},
            json_output,
        )
        return

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
        metrics=metrics,
    )

    # Pass metrics to extractor and populator
    extractor.metrics = metrics

    runner = PipelineRunner(discovery, extractor, populator, settings=settings)

    stats = runner.run(limit=limit)

    if stats.sessions_processed == 0:
        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "index",
                    "warning": "No sessions processed",
                    "stats": {},
                }
            )
        else:
            console.print("[yellow]No sessions processed. Check filters/root path.[/]")
        raise typer.Exit(code=0)

    if json_output:
        output_json(
            {
                "success": True,
                "operation": "index",
                "stats": {
                    "sessions_processed": stats.sessions_processed,
                    "messages_parsed": stats.messages_parsed,
                    "total_tokens": stats.total_tokens,
                    "entities_created": stats.entities_created,
                    "relationships_created": stats.relationships_created,
                    "insights_logged": stats.insights_logged,
                    "estimated_cost_usd": round(stats.estimated_cost_usd, 4),
                    "errors_count": len(stats.errors),
                    "retries_attempted": stats.retries_attempted,
                    "sessions_quarantined": stats.sessions_quarantined,
                },
                "dry_run": dry_run,
            }
        )
    else:
        table = Table(title="Indexing Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Sessions Processed", str(stats.sessions_processed))
        table.add_row("Messages Parsed", str(stats.messages_parsed))
        table.add_row("Total Tokens", str(stats.total_tokens))
        table.add_row("Entities Created", str(stats.entities_created))
        table.add_row("Relationships Created", str(stats.relationships_created))
        table.add_row("Insights Logged", str(stats.insights_logged))
        table.add_row("Est. Cost (USD)", f"${stats.estimated_cost_usd:.4f}")

        if stats.errors:
            table.add_row("Errors", f"[red]{len(stats.errors)}[/red]")
        if stats.sessions_quarantined:
            table.add_row("Quarantined", f"[yellow]{stats.sessions_quarantined}[/yellow]")

        console.print(table)

        if dry_run:
            console.print("\n[dim]Dry run complete - no data written to database[/dim]")

    if stats.errors:
        console.print(f"[red]Encountered {len(stats.errors)} errors:[/]")
        for err in stats.errors:
            console.print(f" - {err}")

    # Show metrics status if enabled
    if settings.enable_metrics and not json_output:
        console.print(
            f"\n[green]✅ Metrics enabled and available at http://{settings.metrics_host}:{settings.metrics_port}{settings.metrics_path}[/]"
        )


# =============================================================================
# RUN COMMAND (legacy - now an alias for index)
# =============================================================================


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
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="LLM provider: 'anthropic' or 'openrouter'. Defaults to config/env.",
    ),
    graph_url: str | None = typer.Option(
        None,
        "--graph-url",
        "-g",
        help="Redis/FalkorDB URL. Defaults to redis://localhost:6379.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="When true, do not execute GRAPH.QUERY commands (just log).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing."),
) -> None:
    """Run the Code Atlas pipeline to process sessions (legacy, use 'index')."""
    # Delegate to index command
    index_sessions(
        config=config,
        root=root,
        limit=limit,
        use_llm=use_llm,
        provider=provider,
        graph_url=graph_url,
        dry_run=dry_run,
        json_output=json_output,
    )


# =============================================================================
# QUERY COMMAND
# =============================================================================


@app.command("query")
def query_graph(
    question: str = typer.Argument(..., help="Question to ask the knowledge graph"),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_url: str | None = typer.Option(None, "--graph-url", "-g", help="Redis/FalkorDB URL."),
    graph_name: str | None = typer.Option(
        None, "--graph-name", "-n", help="Graph name in FalkorDB."
    ),
    entity_type: str | None = typer.Option(
        None, "--entity-type", "-t", help="Filter by entity type (File, Concept, Session, etc.)"
    ),
    limit: int = typer.Option(
        5, "--limit", "-l", help="Maximum number of context entities to retrieve"
    ),
    no_sources: bool = typer.Option(
        False, "--no-sources", help="Omit source citations from output"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Query the knowledge graph with natural language.

    Examples:
        code-atlas query "How do I implement OAuth?"
        code-atlas query "What files were modified?" --entity-type File
        code-atlas query "List all API endpoints" --json
    """
    settings = load_settings(config)
    redis_url = graph_url or settings.redis_url
    graph = graph_name or settings.graph_name

    try:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        output_error(
            "query",
            "CONNECTION_ERROR",
            f"Failed to connect to FalkorDB at {redis_url}",
            {"error": str(e)},
            json_output,
        )
        return

    try:
        # Initialize components
        populator = GraphPopulator(
            redis_url=redis_url,
            graph_name=graph,
            dry_run=False,
        )
        vector_store = VectorStore(redis_client=redis_client)

        # Create RAG service
        rag = create_rag_service(
            graph_populator=populator,
            vector_store=vector_store,
        )

        # Execute query
        result = rag.answer_question(
            question=question,
            entity_type=entity_type,
            include_sources=not no_sources,
        )

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "query",
                    "question": question,
                    "answer": result["answer"],
                    "confidence": result["confidence"],
                    "sources": result.get("sources", []),
                    "context_entities": result.get("context_entities", []),
                    "search_results_count": result.get("search_results_count", 0),
                }
            )
        else:
            # Display answer in panel
            answer_panel = Panel(
                result["answer"],
                title=f"[bold]Answer[/bold] (confidence: {result['confidence']:.0%})",
                border_style="green",
            )
            console.print(answer_panel)

            # Display sources
            if result.get("context_entities") and not no_sources:
                console.print("\n[bold cyan]Sources:[/bold cyan]")
                for entity in result["context_entities"]:
                    entity_type_str = entity.get("entity_type", "Unknown")
                    entity_name = entity.get("entity_name", "Unknown")
                    console.print(f"  • [{entity_type_str}] {entity_name}")

    except Exception as e:
        output_error("query", "QUERY_FAILED", str(e), {}, json_output)


# =============================================================================
# EXPORT COMMAND
# =============================================================================


@app.command("export")
def export_data(
    output: Path = typer.Option(
        Path("code-atlas-export.json"), "--output", "-o", help="Output file path"
    ),
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format: json, cypher, or graphml"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_url: str | None = typer.Option(None, "--graph-url", "-g", help="Redis/FalkorDB URL"),
    graph_name: str | None = typer.Option(
        None, "--graph-name", "-n", help="Graph name in FalkorDB"
    ),
    entity_type: list[str] = typer.Option(
        None, "--entity-type", "-t", help="Entity types to export (can specify multiple)"
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-l", help="Maximum number of entities to export"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output JSON for agent parsing (meta-output)"
    ),
) -> None:
    """Export knowledge graph data to various formats.

    Formats:
        json    - JSON format with entities and relationships
        cypher  - Cypher CREATE statements for Neo4j/FalkorDB
        graphml - GraphML XML format for visualization tools

    Examples:
        code-atlas export --output backup.json
        code-atlas export --format cypher --output import.cypher
        code-atlas export --entity-type File --output files.json
    """
    settings = load_settings(config)
    redis_url = graph_url or settings.redis_url
    graph = graph_name or settings.graph_name

    # Validate format
    valid_formats = ["json", "cypher", "graphml"]
    if format not in valid_formats:
        output_error(
            "export",
            "INVALID_FORMAT",
            f"Invalid format: {format}",
            {"valid": valid_formats},
            json_output,
        )
        return

    try:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        output_error(
            "export",
            "CONNECTION_ERROR",
            f"Failed to connect to FalkorDB at {redis_url}",
            {"error": str(e)},
            json_output,
        )
        return

    try:
        # Query graph for entities
        populator = GraphPopulator(
            redis_url=redis_url,
            graph_name=graph,
            dry_run=False,
        )

        # Build entity type filter
        type_filter = ""
        if entity_type:
            type_list = ", ".join(f"'{t}'" for t in entity_type)
            type_filter = f"WHERE labels(e)[0] IN [{type_list}]"

        # Query for entities
        entity_query = f"""
            MATCH (e)
            {type_filter}
            RETURN labels(e) as types, e
            {f"LIMIT {limit}" if limit else ""}
        """

        try:
            entity_results = populator.execute_query(entity_query)
        except Exception as e:
            output_error(
                "export", "QUERY_FAILED", f"Failed to query entities: {e}", {}, json_output
            )
            return

        # Query for relationships
        rel_query = f"""
            MATCH (a)-[r]->(b)
            {type_filter.replace("e", "a").replace("WHERE", "WHERE labels(a)[0] IN")}
            RETURN a.id as from_id, labels(a) as from_labels,
                   type(r) as rel_type, r as rel_props,
                   b.id as to_id, labels(b) as to_labels
            {f"LIMIT {limit}" if limit else ""}
        """

        try:
            rel_results = populator.execute_query(rel_query)
        except Exception:
            rel_results = []  # Relationships optional

        # Format data based on export format
        if format == "json":
            export_data = {
                "export_metadata": {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "format": "json",
                    "graph_name": graph,
                    "entity_count": len(entity_results),
                    "relationship_count": len(rel_results),
                },
                "entities": [
                    {
                        "id": row.get("e", {}).get("id", "unknown"),
                        "type": row.get("types", ["Unknown"])[0] if row.get("types") else "Unknown",
                        "properties": dict(row.get("e", {})),
                    }
                    for row in entity_results
                ],
                "relationships": [
                    {
                        "from": row.get("from_id"),
                        "from_type": row.get("from_labels", ["Unknown"])[0]
                        if row.get("from_labels")
                        else "Unknown",
                        "to": row.get("to_id"),
                        "to_type": row.get("to_labels", ["Unknown"])[0]
                        if row.get("to_labels")
                        else "Unknown",
                        "type": row.get("rel_type"),
                        "properties": dict(row.get("rel_props", {})),
                    }
                    for row in rel_results
                ],
            }
            output_content = json.dumps(export_data, indent=2, default=str)

        elif format == "cypher":
            lines = ["// Code Atlas Export", f"// Generated: {datetime.now(UTC).isoformat()}", ""]

            # Generate CREATE statements for entities
            for row in entity_results:
                node = row.get("e", {})
                labels = row.get("types", ["Entity"])
                label_str = ":".join(labels)
                node_id = node.get("id", "unknown")

                props = {k: v for k, v in node.items() if k != "id"}
                prop_str = ", ".join(f"{k}: {json.dumps(v)}" for k, v in props.items())

                lines.append(
                    f"CREATE (:{label_str} {{id: {json.dumps(node_id)}{f', {prop_str}' if prop_str else ''}}})"
                )

            lines.append("")

            # Generate CREATE statements for relationships
            for row in rel_results:
                from_id = row.get("from_id")
                to_id = row.get("to_id")
                rel_type = row.get("rel_type", "RELATED_TO")

                lines.append(
                    f"MATCH (a {{id: {json.dumps(from_id)}}}), (b {{id: {json.dumps(to_id)}}})"
                )
                lines.append(f"CREATE (a)-[:{rel_type}]->(b)")
                lines.append("")

            output_content = "\n".join(lines)

        elif format == "graphml":
            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
                '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
                '  <graph id="code-atlas" edgedefault="directed">',
            ]

            for i, row in enumerate(entity_results):
                node = row.get("e", {})
                node_id = node.get("id", f"node_{i}")
                node_label = row.get("types", ["Unknown"])[0] if row.get("types") else "Unknown"
                lines.append(f'    <node id="{node_id}">')
                lines.append(f'      <data key="label">{node_label}</data>')
                lines.append("    </node>")

            for i, row in enumerate(rel_results):
                from_id = row.get("from_id", f"from_{i}")
                to_id = row.get("to_id", f"to_{i}")
                rel_type = row.get("rel_type", "RELATED_TO")
                lines.append(
                    f'    <edge id="e{i}" source="{from_id}" target="{to_id}" label="{rel_type}"/>'
                )

            lines.extend(["  </graph>", "</graphml>"])

            output_content = "\n".join(lines)

        # Write output file
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content)

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "export",
                    "output_file": str(output_path.absolute()),
                    "format": format,
                    "entity_count": len(entity_results),
                    "relationship_count": len(rel_results),
                }
            )
        else:
            console.print(f"[green]✓[/green] Exported to [cyan]{output_path.absolute()}[/cyan]")
            console.print(f"  Format: [yellow]{format}[/yellow]")
            console.print(f"  Entities: [blue]{len(entity_results)}[/blue]")
            if rel_results:
                console.print(f"  Relationships: [blue]{len(rel_results)}[/blue]")

    except Exception as e:
        output_error("export", "EXPORT_FAILED", str(e), {}, json_output)


# =============================================================================
# STATUS COMMAND
# =============================================================================


@app.command("status")
def show_status(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_url: str | None = typer.Option(None, "--graph-url", "-g", help="Redis/FalkorDB URL"),
    graph_name: str | None = typer.Option(
        None, "--graph-name", "-n", help="Graph name in FalkorDB"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Show status of the Code Atlas knowledge graph."""
    settings = load_settings(config)
    redis_url = graph_url or settings.redis_url
    graph = graph_name or settings.graph_name

    try:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        db_connected = True
    except (redis.ConnectionError, redis.TimeoutError):
        db_connected = False

    if not db_connected:
        if json_output:
            output_json(
                {
                    "success": False,
                    "operation": "status",
                    "error": "Database connection failed",
                    "redis_url": redis_url,
                }
            )
        else:
            console.print("[red]✗[/red] Database connection failed")
            console.print(f"  URL: [dim]{redis_url}[/dim]")
        return

    try:
        populator = GraphPopulator(
            redis_url=redis_url,
            graph_name=graph,
            dry_run=False,
        )

        # Get entity counts by type
        entity_query = """
            MATCH (e)
            RETURN labels(e)[0] as type, COUNT(e) as count
        """
        entity_counts = populator.execute_query(entity_query)

        # Get relationship counts by type
        rel_query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, COUNT(r) as count
        """
        rel_counts = populator.execute_query(rel_query)

        # Get total counts
        total_entities = sum(row.get("count", 0) for row in entity_counts)
        total_relationships = sum(row.get("count", 0) for row in rel_counts)

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "status",
                    "graph_name": graph,
                    "redis_url": redis_url,
                    "connected": True,
                    "entities": {
                        "total": total_entities,
                        "by_type": {
                            row.get("type", "Unknown"): row.get("count", 0) for row in entity_counts
                        },
                    },
                    "relationships": {
                        "total": total_relationships,
                        "by_type": {
                            row.get("type", "Unknown"): row.get("count", 0) for row in rel_counts
                        },
                    },
                }
            )
        else:
            console.print(
                Panel(
                    f"[bold]Graph:[/bold] {graph}\n[bold]Database:[/bold] {redis_url}",
                    title="Code Atlas Status",
                    border_style="green",
                )
            )

            if entity_counts:
                table = Table(title="Entity Counts")
                table.add_column("Type", style="cyan")
                table.add_column("Count", style="green", justify="right")

                for row in entity_counts:
                    table.add_row(row.get("type", "Unknown"), str(row.get("count", 0)))

                table.add_row("[bold]Total[/bold]", f"[bold]{total_entities}[/bold]")
                console.print(table)

            if rel_counts:
                table = Table(title="Relationship Counts")
                table.add_column("Type", style="cyan")
                table.add_column("Count", style="green", justify="right")

                for row in rel_counts:
                    table.add_row(row.get("type", "Unknown"), str(row.get("count", 0)))

                table.add_row("[bold]Total[/bold]", f"[bold]{total_relationships}[/bold]")
                console.print(table)

    except Exception as e:
        output_error("status", "STATUS_FAILED", str(e), {}, json_output)


# =============================================================================
# REPORT COMMAND (updated with --json)
# =============================================================================


@app.command("report")
def generate_report(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_name: str = typer.Option("code_atlas", help="Graph name in FalkorDB."),
    redis_url: str = typer.Option("redis://localhost:6379", help="FalkorDB connection URL."),
    top_n: int = typer.Option(10, help="Number of top entities to show."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing."),
) -> None:
    """Generate summary report from knowledge graph."""
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        output_error(
            "report",
            "CONNECTION_ERROR",
            f"Failed to connect to FalkorDB at {redis_url}",
            {"error": str(e)},
            json_output,
        )
        return

    def query_graph(cypher: str) -> list[list]:
        """Execute Cypher query and return results."""
        try:
            result = client.execute_command("GRAPH.QUERY", graph_name, cypher, "--compact")
            if isinstance(result, list) and len(result) >= 2:
                return result[1] if result[1] else []
            return []
        except redis.RedisError:
            return []

    # Collect all data
    files_query = f"""
        MATCH (f:File)<-[r:MENTIONS]-()
        RETURN f.name, COUNT(r) AS mentions
        ORDER BY mentions DESC
        LIMIT {top_n}
    """
    files_result = query_graph(files_query)

    concepts_query = f"""
        MATCH (c:Concept)<-[r:MENTIONS]-()
        RETURN c.name, COUNT(r) AS mentions
        ORDER BY mentions DESC
        LIMIT {top_n}
    """
    concepts_result = query_graph(concepts_query)

    stats_query = """
        MATCH (s:Session)
        RETURN COUNT(s) AS total_sessions,
               AVG(s.size_bytes) AS avg_size,
               SUM(s.size_bytes) AS total_size
    """
    stats_result = query_graph(stats_query)

    recent_query = f"""
        MATCH (s:Session)
        RETURN s.id, s.project, s.modified_at
        ORDER BY s.modified_at DESC
        LIMIT {top_n}
    """
    recent_result = query_graph(recent_query)

    if json_output:
        output_json(
            {
                "success": True,
                "operation": "report",
                "graph_name": graph_name,
                "top_files": [{"name": row[0], "mentions": row[1]} for row in files_result],
                "top_concepts": [{"name": row[0], "mentions": row[1]} for row in concepts_result],
                "stats": {
                    "total_sessions": stats_result[0][0] if stats_result else 0,
                    "avg_size_kb": round(stats_result[0][1] / 1024, 1) if stats_result else 0,
                    "total_size_mb": round(stats_result[0][2] / (1024 * 1024), 2)
                    if stats_result
                    else 0,
                }
                if stats_result
                else None,
                "recent_sessions": [
                    {"id": row[0], "project": row[1], "modified": row[2]} for row in recent_result
                ],
            }
        )
    else:
        if files_result:
            files_table = Table("File", "Mentions", title=f"Top {top_n} Files")
            for row in files_result:
                files_table.add_row(str(row[0]), str(row[1]))
            console.print(files_table)
        else:
            console.print("[yellow]No files found in graph[/]")

        if concepts_result:
            concepts_table = Table("Concept", "Mentions", title=f"Top {top_n} Concepts")
            for row in concepts_result:
                concepts_table.add_row(str(row[0]), str(row[1]))
            console.print(concepts_table)
        else:
            console.print("[yellow]No concepts found in graph[/]")

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

        if recent_result:
            from datetime import datetime as dt

            recent_table = Table(
                "Session ID", "Project", "Modified", title=f"Recent {top_n} Sessions"
            )
            for row in recent_result:
                session_id = str(row[0])[:12] + "..."
                project = str(row[1])
                modified = dt.fromtimestamp(float(row[2])).strftime("%Y-%m-%d %H:%M")
                recent_table.add_row(session_id, project, modified)
            console.print(recent_table)
        else:
            console.print("[yellow]No recent sessions found[/]")

        if not any([files_result, concepts_result, stats_result, recent_result]):
            console.print(
                "\n[yellow]Graph appears to be empty. Run 'code-atlas index' to populate it.[/]"
            )


# =============================================================================
# INDEXES COMMAND (updated with --json)
# =============================================================================


@app.command("indexes")
def manage_indexes(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    graph_name: str = typer.Option("code_atlas", help="Graph name in FalkorDB."),
    redis_url: str = typer.Option("redis://localhost:6379", help="FalkorDB connection URL."),
    action: str = typer.Option("list", "--action", "-a", help="Action: list, create, verify, drop"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Manage database indexes for optimal query performance."""
    settings = load_settings(config)

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        output_error(
            "indexes",
            "CONNECTION_ERROR",
            f"Failed to connect to FalkorDB at {redis_url}",
            {"error": str(e)},
            json_output,
        )
        return

    populator = GraphPopulator(
        graph_name=graph_name,
        redis_url=redis_url,
        dry_run=False,
        create_indexes=settings.create_db_indexes,
        index_timeout=settings.db_index_creation_timeout,
        verify_indexes_after_creation=settings.verify_indexes,
    )

    if action == "list":
        indexes = populator.list_indexes()

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "indexes",
                    "action": "list",
                    "indexes": indexes,
                }
            )
        else:
            console.print(Panel("Database Index Configuration", expand=False))
            table = Table("Category", "Index Count", "Description")
            category_descriptions = {
                "Session": "Indexes for Session nodes (id, project, modified_at, size)",
                "Entity": "Indexes for File and Concept entities (id, name, type)",
                "Insight": "Indexes for Insight nodes (id)",
                "Relationships": "Indexes for MENTIONS relationships (confidence, timestamp)",
                "FullText": "Full-text search indexes for entity names",
            }
            for category, index_list in indexes.items():
                table.add_row(
                    category, str(len(index_list)), category_descriptions.get(category, "Unknown")
                )
            console.print(table)
            total_indexes = sum(len(indexes) for indexes in indexes.values())
            console.print(f"\n[dim]Total indexes defined: {total_indexes}[/]")

    elif action == "create":
        creation_populator = GraphPopulator(
            graph_name=graph_name,
            redis_url=redis_url,
            dry_run=False,
            create_indexes=True,
            index_timeout=settings.db_index_creation_timeout,
            verify_indexes_after_creation=settings.verify_indexes,
        )
        index_queries = [
            q
            for q in creation_populator.executed_queries
            if "CREATE INDEX" in q or "FULLTEXT INDEX" in q
        ]

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "indexes",
                    "action": "create",
                    "indexes_created": len(index_queries),
                }
            )
        else:
            console.print(f"[green]✅ {len(index_queries)} index creation queries executed[/]")

    elif action == "verify":
        verification_result = populator.verify_indexes()

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "indexes",
                    "action": "verify",
                    "result": verification_result,
                }
            )
        else:
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
                console.print(table)

    elif action == "drop":
        if not json_output:
            if not typer.confirm("This will remove all indexes. Continue?", default=False):
                console.print("[dim]Operation cancelled.[/]")
                return

        populator.drop_indexes()

        if json_output:
            output_json(
                {
                    "success": True,
                    "operation": "indexes",
                    "action": "drop",
                }
            )
        else:
            console.print("[green]✅ Index drop operation completed[/]")
            console.print(
                "[yellow]Note: Some indexes may be automatically recreated on next startup[/]"
            )

    else:
        output_error(
            "indexes",
            "INVALID_ACTION",
            f"Invalid action: {action}",
            {"valid": ["list", "create", "verify", "drop"]},
            json_output,
        )


# =============================================================================
# METRICS COMMAND (updated with --json)
# =============================================================================


@app.command("metrics")
def start_metrics_server(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    host: str | None = typer.Option(None, "--host", help="Override metrics server host."),
    port: int | None = typer.Option(None, "--port", help="Override metrics server port."),
    daemon: bool = typer.Option(False, "--daemon", help="Run metrics server in daemon mode."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing"),
) -> None:
    """Start the Prometheus metrics server for monitoring."""
    import threading

    settings = load_settings(config)

    if host:
        settings.metrics_host = host
    if port:
        settings.metrics_port = port

    if not settings.enable_metrics:
        output_error(
            "metrics",
            "METRICS_DISABLED",
            "Metrics collection is disabled in configuration.",
            {
                "hint": "Set enable_metrics = true in .code-atlas.toml or CODE_ATLAS_ENABLE_METRICS=true"
            },
            json_output,
        )
        return

    if json_output:
        output_json(
            {
                "success": True,
                "operation": "metrics",
                "status": "starting",
                "host": settings.metrics_host,
                "port": settings.metrics_port,
                "daemon": daemon,
            }
        )
    else:
        console.print(
            Panel(
                f"[bold]Metrics Server[/bold]\n"
                f"Host: {settings.metrics_host}\n"
                f"Port: {settings.metrics_port}\n"
                f"Metrics: http://{settings.metrics_host}:{settings.metrics_port}{settings.metrics_path}",
                title="Starting Server",
                expand=False,
            )
        )

    try:
        if daemon:

            def run_server():
                server = MetricsServer(settings)
                server.run()

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            console.print("[green]✅ Metrics server started in daemon mode[/]")
            try:
                while server_thread.is_alive():
                    server_thread.join(timeout=1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping...[/]")
        else:
            server = MetricsServer(settings)
            server.run()
    except Exception as e:
        output_error("metrics", "START_FAILED", str(e), {}, json_output)


# =============================================================================
# SERVE COMMAND
# =============================================================================


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
    """Start the Code Atlas API server."""
    import uvicorn

    from .api.main import create_app

    settings = load_settings(config)
    settings.metrics_host = host
    settings.metrics_port = port
    settings.enable_metrics = True

    console.print(
        Panel.fit(
            f"[bold blue]Code Atlas API Server[/]\n\n"
            f"Host: {host}\nPort: {port}\nWorkers: {workers}\nReload: {reload}\n"
            f"\n[dim]API docs: http://{host}:{port}/docs[/]",
            title="Starting Server",
        )
    )

    if reload:
        uvicorn.run("code_atlas.api.main:app", host=host, port=port, reload=True, log_level="info")
    else:
        app_instance = create_app(settings)
        uvicorn.run(app_instance, host=host, port=port, workers=workers, log_level="info")


if __name__ == "__main__":
    app()
