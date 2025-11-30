# Code Atlas

Convert Claude Code session logs into a searchable knowledge graph.

## Features

- **Session Discovery** - Scans ~/.claude/projects for session files
- **LLM-Powered Extraction** - Uses Anthropic Claude or OpenRouter APIs
- **Knowledge Graph** - Stores in FalkorDB for powerful Cypher queries
- **REST API** - Full API for session management and graph queries
- **React Frontend** - Interactive UI for browsing entities and visualizing graphs
- **Entity Deduplication** - Automatic merging of similar entities
- **Real-Time Updates** - WebSocket support for live job status
- **Cost Controls** - Enforces spending limits ($0.02/session default)

## Quick Start (3 Steps)

### Prerequisites
- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Docker (for FalkorDB)
- Node.js 18+ (for frontend)

### 1. Setup

```bash
# Clone and enter directory
cd code-atlas

# Run setup (installs deps, starts Docker, creates .env)
make setup
```

### 2. Configure

```bash
# Edit .env with your API key (optional - falls back to heuristics)
nano .env

# Add one of:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENROUTER_API_KEY=sk-or-...
```

### 3. Start Development

```bash
# Start everything (FalkorDB + Backend + Frontend)
make dev

# Or start components individually:
make docker-up   # Just FalkorDB
make backend     # Just API server
make frontend    # Just React app
```

**Access:**
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Common Commands

```bash
# Development
make dev          # Start full dev environment
make test         # Run all tests
make test-unit    # Run unit tests only (fast)
make lint         # Check code quality
make format       # Auto-format code

# CLI Pipeline
make discover     # Find Claude sessions
make run-dry      # Preview pipeline (no writes)
make run-heuristics  # Run without LLM (free)
make run-llm      # Run with LLM extraction

# Utilities
make help         # Show all commands
make clean        # Remove caches
make docker-down  # Stop Docker services
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sessions/discover` | GET | Discover available sessions |
| `/api/v1/sessions/process` | POST | Process sessions (background) |
| `/api/v1/sessions/{job_id}/status` | GET | Get processing status |
| `/api/v1/graph/entities` | GET | List entities |
| `/api/v1/graph/entities/search` | GET | Full-text search |
| `/api/v1/graph/visualization` | GET | Get D3.js/Cytoscape data |
| `/ws/jobs/{job_id}` | WS | Real-time job updates |

Full API documentation at http://localhost:8000/docs

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# LLM Provider (choose one)
ANTHROPIC_API_KEY=sk-ant-...      # Anthropic Claude
OPENROUTER_API_KEY=sk-or-...      # OpenRouter (Grok, Llama, etc.)
CODE_ATLAS_LLM_PROVIDER=anthropic  # or "openrouter"

# API Authentication (optional for dev)
CODE_ATLAS_API_KEY_REQUIRED=false
CODE_ATLAS_ADMIN_API_KEY=your-admin-key

# Cost Limits
CODE_ATLAS_MAX_COST_PER_SESSION=0.02
CODE_ATLAS_MAX_CUMULATIVE_COST=10.0
```

### Configuration File

Create `.code-atlas.toml` for persistent settings:

```toml
[discovery]
claude_root = "~/.claude/projects"

[extraction]
use_llm = true
llm_provider = "anthropic"
max_cost_per_session_usd = 0.02

[graph]
redis_url = "redis://localhost:6379"
enable_deduplication = true
similarity_threshold = 0.85
```

**Priority**: CLI flags > `.code-atlas.toml` > environment variables > defaults

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│    (TypeScript, Vite, TailwindCSS, D3.js)                  │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI Backend                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Sessions │  │  Graph   │  │  Admin   │  │  WebSocket  │ │
│  │   API    │  │   API    │  │   API    │  │   Updates   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────────────┘ │
├───────┼─────────────┼─────────────┼─────────────────────────┤
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐                  │
│  │ JobStore │  │  Graph   │  │ APIKey   │                  │
│  │ (SQLite) │  │Populator │  │ Manager  │                  │
│  └──────────┘  └────┬─────┘  └──────────┘                  │
├─────────────────────┼──────────────────────────────────────┤
│               ┌─────▼─────┐                                │
│               │ FalkorDB  │  (Graph Database)              │
│               └───────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

- **SessionDiscovery** - Finds session files with filtering
- **InsightExtractor** - LLM or heuristic entity extraction
- **GraphPopulator** - FalkorDB writes with deduplication
- **EntityResolver** - Similarity-based entity merging
- **JobStore** - SQLite persistence for background jobs
- **APIKeyManager** - Scoped API key authentication

## Testing

```bash
# All tests (90+ tests)
make test

# Quick unit tests
make test-unit

# Integration tests (requires Docker)
make docker-up
make test-int

# With coverage report
make test-cov
open backend/htmlcov/index.html
```

## Project Structure

```
code-atlas/
├── backend/
│   ├── src/code_atlas/
│   │   ├── api/              # FastAPI routes
│   │   │   ├── v1/           # API v1 endpoints
│   │   │   └── websocket.py  # WebSocket handlers
│   │   ├── auth/             # API key management
│   │   ├── schemas/          # Pydantic models
│   │   ├── entity_resolver.py
│   │   ├── graph_populator.py
│   │   ├── insight_extractor.py
│   │   ├── job_store.py
│   │   └── pipeline.py
│   ├── tests/                # 90+ tests
│   └── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── components/       # UI components
│   │   └── api/              # API client
│   └── package.json
├── docs/                     # Documentation
├── Makefile                  # Development commands
└── .env.example              # Environment template
```

## Troubleshooting

### Docker Issues

```bash
# Check if services are running
docker ps | grep code-atlas

# View logs
make docker-logs

# Restart services
make docker-down && make docker-up
```

### Connection Errors

```bash
# Verify FalkorDB is accessible
redis-cli -p 6379 PING

# Check API health
curl http://localhost:8000/health
```

### No Sessions Found

```bash
# Check Claude projects directory
ls ~/.claude/projects

# Override path
uv run code-atlas discover --root /custom/path
```

## Documentation

- [RUNBOOK.md](docs/RUNBOOK.md) - Operations guide
- [PLAN.md](docs/PLAN.md) - Implementation plan
- [Active Context](docs/active-context.md) - Current status
- [Tech Context](docs/tech-context.md) - Architecture decisions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run `make check` before committing
4. Submit a pull request

We follow:
- **Code Style**: Ruff formatting
- **Type Safety**: Full mypy coverage
- **Testing**: 80%+ coverage target
- **Commits**: Conventional commits

## License

MIT
