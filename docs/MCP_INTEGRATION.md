# MCP Integration Guide

This guide explains how to set up and use Code Atlas with the Model Context Protocol (MCP) for integration with Claude Desktop and other MCP clients.

## Overview

The Model Context Protocol (MCP) enables Code Atlas to be accessed directly from Claude Desktop, allowing you to ask Claude about your codebase knowledge graph during conversations.

## Installation

### Prerequisites

1. Install MCP SDK:
```bash
cd backend
uv add mcp
```

2. Ensure Code Atlas API is running:
```bash
uv run code-atlas serve
```

## Configuration

### Claude Desktop Configuration

Add Code Atlas MCP server to Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "code-atlas": {
      "command": "python",
      "args": [
        "-m",
        "code_atlas.mcp.server",
        "--stdio"
      ],
      "env": {
        "CODE_ATLAS_REDIS_URL": "redis://localhost:6379",
        "CODE_ATLAS_GRAPH_NAME": "code_atlas"
      }
    }
  }
}
```

## Available Resources

### Sessions
- **URI Pattern**: `sessions://{session_id}`
- **Description**: Access session data and metadata
- **Example**: `sessions://session-abc123`

### Entities
- **URI Pattern**: `entities://{entity_id}`
- **Description**: Access entity details and relationships
- **Example**: `entities://concept-auth-system`

### Insights
- **URI Pattern**: `insights://{insight_type}`
- **Description**: Access insight data
- **Types**: `top-entities`, `recurring-problems`, `popular-tools`
- **Example**: `insights://top-entities`

### Graph
- **URI Pattern**: `graph://data`
- **Description**: Access graph visualization data

## Available Tools

### query_graph
Execute read-only Cypher queries against the knowledge graph.

**Parameters:**
- `query` (string, required): Cypher query (MATCH/RETURN only)
- `parameters` (object, optional): Query parameters
- `limit` (integer, optional): Maximum results (default: 100)

**Example:**
```json
{
  "name": "query_graph",
  "arguments": {
    "query": "MATCH (e:Concept) RETURN e.name, e.mention_count ORDER BY e.mention_count DESC LIMIT 10"
  }
}
```

### search_entities
Search entities by name or type.

**Parameters:**
- `query` (string, required): Search query
- `entity_type` (string, optional): Filter by type
- `limit` (integer, optional): Maximum results (default: 20)

**Example:**
```json
{
  "name": "search_entities",
  "arguments": {
    "query": "authentication",
    "entity_type": "Concept",
    "limit": 10
  }
}
```

### get_insights
Get insights from the knowledge graph.

**Parameters:**
- `insight_type` (string, required): Type of insight
- `limit` (integer, optional): Maximum results (default: 10)

**Example:**
```json
{
  "name": "get_insights",
  "arguments": {
    "insight_type": "recurring-problems",
    "limit": 20
  }
}
```

### process_sessions
Submit sessions for processing (placeholder).

**Parameters:**
- `session_paths` (array, required): List of session file paths
- `use_llm` (boolean, optional): Use LLM extraction (default: true)
- `dry_run` (boolean, optional): Validate without writing (default: false)

## Usage Examples

### In Claude Desktop

Once configured, you can ask Claude:

- "Query the code atlas graph for all authentication-related entities"
- "What are the top problems in my codebase?"
- "Show me entities related to database connections"
- "Get insights about popular tools used in sessions"

Claude will use the MCP tools to query Code Atlas and provide answers based on your knowledge graph.

## Development

### Running MCP Server Standalone

```bash
cd backend
uv run python -m code_atlas.mcp.server --stdio
```

### Testing MCP Server

Use MCP client tools to test:

```bash
# List resources
mcp-client list-resources

# Call tool
mcp-client call-tool query_graph '{"query": "MATCH (e) RETURN count(e)"}'
```

## Troubleshooting

### MCP Server Not Found
- Verify MCP SDK is installed: `uv list | grep mcp`
- Check Python path in Claude Desktop config

### Connection Issues
- Ensure Code Atlas API is running
- Verify Redis/FalkorDB is accessible
- Check environment variables in config

### Tool Execution Errors
- Verify graph database has data
- Check query syntax (read-only queries only)
- Review server logs for details

## Future Enhancements

- Full pipeline integration for process_sessions tool
- WebSocket transport for web clients
- Resource caching for performance
- Tool result pagination
- Authentication and authorization
