## Code Atlas Backend

Utilities and services that power the Claude-session → knowledge graph pipeline.

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Docker (for FalkorDB/Redis stack)

### Install & Test
```bash
cd codeswiftr-com/code-atlas/backend
uv sync
uv run pytest
```

### CLI Preview
```bash
# List latest sessions
uv run code-atlas discover --root /path/to/projects --limit 3

# Parse a handful of sessions and print summaries
uv run code-atlas run --root /path/to/projects --limit 5
```

### Services
Bring up FalkorDB + Redis for local development:
```bash
docker compose up -d
```

### Environment Configuration
Create a `.env` (ignored from git) to point the pipeline at your preferred LLM/router:
```env
LLM_PROVIDER=anthropic
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_API_KEY=...
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_MODEL=glm-4.6
```
`InsightExtractor` reads these values automatically; omit them to stay in heuristic/offline mode.
