# Code Atlas Quick Start

Get up and running in 5 minutes. Turn your Claude Code sessions into a searchable knowledge graph.

## Prerequisites

- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Docker (for FalkorDB graph database)
- Claude Code with some session history

---

## 1. Install

```bash
cd code-atlas

# Install dependencies, start Docker, create .env
make setup
```

This installs Python deps, starts FalkorDB via Docker, and creates your `.env` file.

---

## 2. Configure API Key (Optional)

Code Atlas works without an API key using free heuristic extraction. For smarter entity extraction with LLM:

```bash
# Edit .env
nano .env

# Add your key (choose one):
ANTHROPIC_API_KEY=sk-ant-...    # Anthropic Claude
# or
OPENROUTER_API_KEY=sk-or-...    # OpenRouter (free tier available)
```

**Without an API key**, extraction uses pattern matching (free but less accurate).
**With an API key**, it uses Claude for context-aware extraction (~$0.02/session).

---

## 3. Run Your First Scan

```bash
# Discover available sessions
make discover

# Run pipeline (dry run first)
make run-dry
```

The dry run shows what will be extracted without writing to the graph. To actually process:

```bash
# Heuristic extraction (free)
make run-heuristics

# Or with LLM (costs ~$0.02/session)
make run-llm
```

---

## 4. Query the Graph

### CLI Queries

```bash
# Search for entities
uv run code-atlas search "redis"

# Generate a report
uv run code-atlas report --top-n 10
```

### API Server

Start the API server:

```bash
make backend
```

Then query via the API:

```bash
# List all entities
curl http://localhost:8000/api/v1/graph/entities

# Search entities
curl "http://localhost:8000/api/v1/graph/entities/search?q=authentication"

# Full-text search
curl "http://localhost:8000/api/v1/graph/entities/search?q=postgres&limit=5"
```

### Web UI

```bash
make frontend
```

Open http://localhost:5173 to browse entities and visualize the graph.

---

## Common Commands

| Command | What it does |
|---------|--------------|
| `make dev` | Start full stack (Docker + backend + frontend) |
| `make discover` | List available Claude sessions |
| `make run-dry` | Preview extraction without writing |
| `make run-heuristics` | Extract with pattern matching (free) |
| `make run-llm` | Extract with Claude (costs ~$0.02/session) |
| `make test` | Run tests |

---

## What's Next?

- **API docs**: http://localhost:8000/docs
- **MCP server**: Connect Claude Desktop directly — see `docs/mcp-server.md`
- **GraphRAG**: Ask natural language questions — see `docs/graphrag.md`
- **Configuration**: Tune extraction in `.code-atlas.toml`

---

## Troubleshooting

**FalkorDB won't start?**
```bash
docker compose up -d
docker logs code-atlas-falkordb-1
```

**No sessions found?**
```bash
# Check your Claude projects path
ls ~/.claude/projects/

# Override path
uv run code-atlas run --root /path/to/projects
```

**Cost too high?**
```bash
# Lower cost limits in .env
CODE_ATLAS_MAX_COST_PER_SESSION=0.01
CODE_ATLAS_MAX_CUMULATIVE_COST=1.0
```
