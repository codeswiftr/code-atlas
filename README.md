# Code Atlas

Convert Claude Code session logs into a searchable knowledge graph.

## Features

- 🔍 **Automatic Discovery** - Scans ~/.claude/projects for session files
- 🧠 **LLM-Powered Extraction** - Uses Claude API to extract entities & relationships
- 💰 **Cost Controls** - Enforces spending limits ($0.02/session default)
- 📊 **Knowledge Graph** - Stores in FalkorDB for powerful queries
- 🔄 **Retry Logic** - Exponential backoff with error quarantine
- 📦 **Token Chunking** - Handles large sessions (>12K tokens)

## Quick Start

### Prerequisites

- **Python 3.11+** (for tomllib support)
- **Docker** (for FalkorDB)
- **Anthropic API key** (optional, falls back to heuristics)

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
model = "claude-3-5-sonnet-latest"
max_cost_per_session_usd = 0.02

[graph]
redis_url = "redis://localhost:6379"

[pipeline]
max_cumulative_cost_usd = 10.0
```

Or use environment variables:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
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

# Run with real extraction and database writes
uv run code-atlas run --no-dry-run --use-llm --limit 10

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
uv run code-atlas run --no-dry-run --use-llm --limit 10

# 6. View results
uv run code-atlas report
```

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
