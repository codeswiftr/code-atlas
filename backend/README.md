## Code Atlas Backend

Quick start guide for Code Atlas backend. For complete documentation, see the [root README](../README.md).

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management (or pip as fallback)
- Docker and Docker Compose (for FalkorDB)

### Installation

```bash
cd code-atlas/backend
uv sync
```

Or with pip:
```bash
pip install -e .
```

### Quick Start

1. **Start Services**
   ```bash
   docker compose up -d
   ```

2. **Discover Sessions**
   ```bash
   uv run code-atlas discover --limit 10
   ```

3. **Run Pipeline (Dry Run)**
   ```bash
   uv run code-atlas run --dry-run --limit 5
   ```

4. **Run with LLM Extraction**
   ```bash
   uv run code-atlas run --no-dry-run --use-llm --limit 10
   ```

5. **Generate Report**
   ```bash
   uv run code-atlas report --top-n 20
   ```

### Configuration

**Option 1: Environment Variables**
```bash
cp .env.example .env
# Edit .env with your settings
```

**Option 2: Configuration File**
Create `.code-atlas.toml` in project root (see [README](../README.md#configuration) for format).

**Option 3: CLI Flags**
```bash
uv run code-atlas run --root ~/.claude/projects --limit 10
```

Configuration priority: CLI flags > `.code-atlas.toml` > environment variables > defaults

### Environment Variables

Key variables (see `.env.example` for complete list):
- `ANTHROPIC_API_KEY` - Required for LLM extraction (optional, falls back to heuristics)
- `CODE_ATLAS_CLAUDE_ROOT` - Claude projects directory (default: `~/.claude/projects`)
- `CODE_ATLAS_MAX_COST_PER_SESSION` - Cost limit per session (default: `0.02`)
- `CODE_ATLAS_MAX_CUMULATIVE_COST` - Total cost limit per run (default: `10.0`)
- `CODE_ATLAS_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: `INFO`)

### Testing

```bash
# All tests
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/ -v -m "not integration"

# Integration tests (requires FalkorDB running)
docker compose up -d
uv run pytest tests/ -m integration -v
```

### Documentation

- **[README](../README.md)** - Complete documentation and user guide
- **[RUNBOOK](../docs/RUNBOOK.md)** - Operations guide and troubleshooting
- **[DEPLOYMENT](../docs/DEPLOYMENT.md)** - Deployment procedures
- **[PLAN](../docs/PLAN.md)** - Implementation plan and status
