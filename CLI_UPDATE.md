# Code Atlas CLI Update

## Summary

Updated the Code Atlas CLI with new commands following the graphrag-starter pattern. All commands now support `--json` flag for agent parsing.

## Commands

| Command | Description | JSON Support |
|---------|-------------|--------------|
| `discover` | List discovered Claude sessions | ✅ |
| `index` | Index sessions into knowledge graph | ✅ |
| `run` | Legacy alias for `index` | ✅ |
| `query` | Query knowledge graph with natural language | ✅ |
| `export` | Export graph data (JSON/Cypher/GraphML) | ✅ |
| `status` | Show graph statistics | ✅ |
| `report` | Generate summary report | ✅ |
| `indexes` | Manage database indexes | ✅ |
| `metrics` | Start Prometheus metrics server | ✅ |
| `serve` | Start FastAPI server | N/A |

## Usage Examples

### Discover Sessions
```bash
# List all sessions
code-atlas discover

# Filter by project with JSON output
code-atlas discover --include-project my-project --json
```

### Index Sessions
```bash
# Index 10 sessions (dry run by default)
code-atlas index --limit 10

# Index with LLM extraction and write to DB
code-atlas index --no-dry-run --use-llm --json
```

### Query Graph
```bash
# Natural language query
code-atlas query "How do I implement OAuth?"

# Query with filtering
code-atlas query "What files were modified?" --entity-type File --json
```

### Export Data
```bash
# Export to JSON
code-atlas export --output backup.json

# Export to Cypher for Neo4j import
code-atlas export --format cypher --output import.cypher

# Export only File entities
code-atlas export --entity-type File --output files.json
```

### Check Status
```bash
# Show graph statistics
code-atlas status

# JSON output for automation
code-atlas status --json
```

## JSON Output Format

All commands support `--json` for structured output:

```json
{
  "success": true,
  "operation": "discover",
  "count": 42,
  "sessions": [...]
}
```

Errors also return JSON:

```json
{
  "success": false,
  "operation": "query",
  "error": {
    "code": "CONNECTION_ERROR",
    "message": "Failed to connect to FalkorDB"
  }
}
```

## Design Decisions

1. **Unified `--json` flag**: All commands support `--json` for agent-friendly output
2. **`index` command**: New primary command for processing sessions (replaces `run`)
3. **Backward compatibility**: `run` command preserved as alias
4. **Rich by default**: Human-friendly output when not in JSON mode
5. **Standard error handling**: Consistent error format across all commands
