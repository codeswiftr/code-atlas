# Code Atlas

Convert Claude Code session logs into a searchable knowledge graph.

## Features

- 🔍 **Automatic Discovery** - Scans ~/.claude/projects for session files
- 🧠 **LLM-Powered Extraction** - Uses Anthropic Claude or OpenRouter APIs to extract entities & relationships
- 💰 **Cost Controls** - Enforces spending limits ($0.02/session default)
- 📊 **Knowledge Graph** - Stores in FalkorDB for powerful queries
- 🔄 **Retry Logic** - Exponential backoff with error quarantine
- 📦 **Token Chunking** - Handles large sessions (>12K tokens)
- 🔌 **Multi-Provider Support** - Supports Anthropic Claude and OpenRouter (via LiteLLM)
- 🌐 **REST API** - Full API for session management and graph queries
- 🛡️ **Rate Limiting** - Built-in rate limiting with configurable limits

## Quick Start

### Prerequisites

- **Python 3.11+** (for tomllib support)
- **Docker** (for FalkorDB)
- **LLM API key** (optional, falls back to heuristics):
  - **Anthropic API key** (`ANTHROPIC_API_KEY`) for Claude models
  - **OpenRouter API key** (`OPENROUTER_API_KEY`) for OpenRouter models

### Installation

```bash
# Clone and navigate
cd code-atlas/backend

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Start Services

```bash
# Start FalkorDB
docker compose up -d

# Verify it's running
docker ps | grep falkordb
```

### Configuration

Create `.code-atlas.toml` in your project root:

```toml
[discovery]
claude_root = "~/.claude/projects"

[extraction]
use_llm = true
llm_provider = "openrouter"  # or "anthropic"
openrouter_model = "x-ai/grok-4.1-fast"  # for OpenRouter
model = "claude-3-5-sonnet-latest"  # for Anthropic
max_cost_per_session_usd = 0.02

[graph]
redis_url = "redis://localhost:6379"

[pipeline]
max_cumulative_cost_usd = 10.0
```

Or use environment variables:
```bash
# For Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export CODE_ATLAS_LLM_PROVIDER=anthropic

# For OpenRouter
export OPENROUTER_API_KEY=sk-or-...
export OPENROUTER_MODEL=x-ai/grok-4.1-fast
export CODE_ATLAS_LLM_PROVIDER=openrouter

# Common settings
export CODE_ATLAS_CLAUDE_ROOT=~/.claude/projects
export CODE_ATLAS_MAX_SESSION_MB=50
```

**Configuration Priority**: `--config` flag > `.code-atlas.toml` > environment variables > defaults

### Usage

```bash
# Discover sessions
uv run code-atlas discover --limit 10

# Run pipeline (dry-run mode - no database writes)
uv run code-atlas run --dry-run --limit 5

# Run with real extraction and database writes (Anthropic)
uv run code-atlas run --no-dry-run --use-llm --provider anthropic --limit 10

# Run with OpenRouter
uv run code-atlas run --no-dry-run --use-llm --provider openrouter --limit 10

# Use custom config file
uv run code-atlas run --config prod.toml --limit 100

# Generate knowledge graph report
uv run code-atlas report --top-n 20
```

### Example Workflow

```bash
# 1. Start services
docker compose up -d

# 2. Test discovery
uv run code-atlas discover --limit 5

# 3. Dry run to preview
uv run code-atlas run --dry-run --limit 3

# 4. Run with heuristics (fast, no API cost)
uv run code-atlas run --no-dry-run --no-use-llm --limit 10

# 5. Run with LLM extraction (higher quality)
# Using Anthropic
uv run code-atlas run --no-dry-run --use-llm --provider anthropic --limit 10

# Or using OpenRouter
uv run code-atlas run --no-dry-run --use-llm --provider openrouter --limit 10

# 6. View results
uv run code-atlas report
```

## REST API

Code Atlas provides a full REST API for programmatic access to session management and knowledge graph queries.

### Starting the API Server

```bash
# Start API server
uv run code-atlas serve

# With custom host/port
uv run code-atlas serve --host 0.0.0.0 --port 8080

# With hot reload (development)
uv run code-atlas serve --reload

# With multiple workers (production)
uv run code-atlas serve --workers 4
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sessions/discover` | GET | Discover available sessions |
| `/api/v1/sessions/process` | POST | Process sessions (background) |
| `/api/v1/sessions/{session_id}/status` | GET | Get processing status |
| `/api/v1/sessions` | GET | List processed sessions |
| `/api/v1/sessions/stats` | GET | Get session statistics |
| `/api/v1/graph/entities` | GET | Search entities |
| `/api/v1/graph/relationships` | GET | Query relationships |
| `/api/v1/graph/query` | POST | Execute Cypher query |
| `/api/v1/graph/visualization` | GET | Get D3.js/Cytoscape data |
| `/api/v1/graph/stats` | GET | Get graph statistics |

### Authentication

Set `CODE_ATLAS_API_KEY_REQUIRED=true` to require API keys:

```bash
# Enable authentication
export CODE_ATLAS_API_KEY_REQUIRED=true
export CODE_ATLAS_ADMIN_API_KEY=your-admin-key-here

# Make authenticated requests
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/sessions
```

### Rate Limiting

Built-in rate limiting protects the API:
- **Standard keys**: 100 requests/minute
- **Admin keys**: 1000 requests/minute

Configure in `.code-atlas.toml`:
```toml
[api]
rate_limit_per_minute = 100
admin_rate_limit_per_minute = 1000
```

### Example Requests

```bash
# Discover sessions
curl http://localhost:8000/api/v1/sessions/discover?limit=10

# Process sessions
curl -X POST http://localhost:8000/api/v1/sessions/process \
  -H "Content-Type: application/json" \
  -d '{"session_ids": ["session-123"], "use_llm": true}'

# Query entities
curl "http://localhost:8000/api/v1/graph/entities?entity_type=Concept&limit=20"

# Execute Cypher query
curl -X POST http://localhost:8000/api/v1/graph/query \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (n:Concept) RETURN n LIMIT 10"}'

# Get visualization data
curl "http://localhost:8000/api/v1/graph/visualization?format=d3"
```

### Interactive Documentation

Access Swagger UI at `http://localhost:8000/docs` or ReDoc at `http://localhost:8000/redoc`.

## Testing

```bash
# All tests
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/ -v -m "not integration"

# Integration tests (requires FalkorDB)
docker compose up -d
uv run pytest tests/ -m integration -v

# With coverage
uv run pytest tests/ --cov=code_atlas --cov-report=html
open htmlcov/index.html
```

## Architecture

```
Claude Sessions (.jsonl)
    ↓ Discovery
SessionDiscovery
    ↓ Parse
SessionParser
    ↓ Extract
InsightExtractor (LLM or Heuristics)
    ↓ Populate
GraphPopulator
    ↓
FalkorDB Knowledge Graph
```

### Components

- **SessionDiscovery**: Finds session files in ~/.claude/projects with filtering
- **SessionParser**: Parses .jsonl format into structured models
- **InsightExtractor**: Extracts entities/relationships (LLM or heuristics)
- **GraphPopulator**: Writes to FalkorDB with retry logic
- **PipelineRunner**: Orchestrates entire workflow with cost tracking

## Development

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Type check
uv run mypy src/
```

### Project Structure

```
code-atlas/
├── backend/
│   ├── src/code_atlas/
│   │   ├── cli.py              # Typer CLI commands
│   │   ├── config.py           # Settings with TOML support
│   │   ├── session_discovery.py
│   │   ├── session_parser.py
│   │   ├── insight_extractor.py
│   │   ├── graph_populator.py
│   │   ├── pipeline.py
│   │   └── models.py
│   ├── tests/
│   │   ├── test_config.py
│   │   ├── test_session_discovery.py
│   │   └── test_integration.py
│   ├── pyproject.toml
│   └── docker-compose.yml
├── docs/
│   └── RUNBOOK.md             # Operations guide
└── .code-atlas.toml           # Example config
```

## Cost Management

Code Atlas includes multiple layers of cost protection:

1. **Per-Session Limit**: `max_cost_per_session_usd = 0.02` (default)
2. **Cumulative Limit**: `max_cumulative_cost_usd = 10.0` (default)
3. **Token Chunking**: Splits large sessions to fit within token limits
4. **Dry-Run Mode**: Test pipelines without API calls

### Cost Estimation

- Small session (1K tokens): ~$0.003
- Medium session (5K tokens): ~$0.015
- Large session (12K tokens): ~$0.036
- Pipeline (100 sessions): ~$1.50 average

## Troubleshooting

### FalkorDB Connection Error

```bash
# Check if FalkorDB is running
docker ps | grep falkordb

# If not running
docker compose up -d

# Check logs
docker compose logs falkordb
```

### No Sessions Discovered

```bash
# Verify Claude root path
ls -la ~/.claude/projects

# Check config
uv run code-atlas discover --limit 5

# Override path
uv run code-atlas discover --root /custom/path
```

### Cost Limit Exceeded

```bash
# Increase limits in .code-atlas.toml
max_cumulative_cost_usd = 20.0

# Or process in batches
uv run code-atlas run --limit 50
uv run code-atlas run --limit 50  # Run again for next batch
```

## Documentation

- [RUNBOOK.md](docs/RUNBOOK.md) - Operations guide with detailed troubleshooting
- [Project Brief](docs/project-brief.md) - Project overview and goals
- [Active Context](docs/active-context.md) - Current status and objectives
- [System Patterns](docs/system-patterns.md) - Architecture and design patterns
- [PLAN.md](docs/PLAN.md) - Implementation plan and progress

## Contributing

See project structure above. We follow:
- **Code Style**: Ruff formatting
- **Type Safety**: Full mypy coverage
- **Testing**: 80%+ coverage target
- **Commits**: Conventional commits

## License

MIT
