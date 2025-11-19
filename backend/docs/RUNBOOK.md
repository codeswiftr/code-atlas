# Code Atlas Operations Runbook

## System Requirements

### Hardware
- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum, 8GB recommended for large batch processing
- **Disk**: 10GB+ for session files + graph data
- **Network**: Internet connection for Claude API (optional)

### Software
- **Python 3.11+** - Required for tomllib support
- **Docker 20.10+** - For FalkorDB database
- **uv** - Recommended Python package manager

## Installation & Setup

### Local Development

```bash
# Clone repository
cd code-atlas/backend

# Install dependencies
uv sync

# Start FalkorDB
docker compose up -d

# Verify services
docker ps | grep falkordb

# Test installation
uv run code-atlas discover --limit 5
```

## Common Operations

### Discovery & Testing

```bash
# Discover available sessions
uv run code-atlas discover --limit 20

# Test with dry run (no database writes)
uv run code-atlas run --dry-run --limit 10

# Test with heuristics only (no API cost)
uv run code-atlas run --no-dry-run --no-use-llm --limit 50

# Test with LLM extraction
uv run code-atlas run --no-dry-run --use-llm --limit 10
```

### Reporting & Monitoring

```bash
# Generate knowledge graph report
uv run code-atlas report --top-n 20

# Custom graph name
uv run code-atlas report --graph-name custom_graph

# Different FalkorDB instance
uv run code-atlas report --redis-url redis://remote-host:6379
```

## Troubleshooting

### FalkorDB Connection Failed
**Symptom**: `ConnectionError: Could not connect to redis://localhost:6379`

**Solution**:
```bash
# Check if FalkorDB is running
docker ps | grep falkordb

# Start FalkorDB
docker compose up -d falkordb

# Test connection manually
redis-cli -h localhost -p 6379 ping
```

### No Sessions Discovered
**Symptom**: `No sessions processed. Check filters/root path.`

**Solution**:
```bash
# Check Claude directory
ls -la ~/.claude/projects

# Override via CLI
uv run code-atlas discover --root /absolute/path
```

### Cost Limit Exceeded
**Symptom**: `CostLimitExceeded: Cumulative cost $10.50 exceeds limit $10.00`

**Solution**:
```bash
# Process in smaller batches
uv run code-atlas run --limit 25
uv run code-atlas run --limit 25
```

## Security

### API Key Management

```bash
# Secure API key storage
chmod 600 .env
echo ".env" >> .gitignore

# Use restricted keys with minimal scope
```

## Performance Tuning

### Optimizing for Scale

```bash
# Use heuristics for bulk processing
uv run code-atlas run --no-use-llm --limit 1000

# Process in smaller batches for memory efficiency
uv run code-atlas run --limit 50
```
