# Code Atlas Project Rules

## MVP Status: 95% COMPLETE - DEPLOYMENT READY ✅
**Last Updated:** 2026-02-02
**See:** `.forge/mvp-completion-report.md` for detailed analysis

## Project Overview
Convert Claude Code session logs into a searchable knowledge graph. Scans
`~/.claude/projects` for session files, extracts entities using LLM or heuristics,
and stores in FalkorDB for powerful Cypher queries and visualization.

## Tech Stack
- **Backend**: FastAPI + FalkorDB (graph database)
- **Frontend**: React + TypeScript + Vite + D3.js/Cytoscape
- **AI**: Anthropic Claude or OpenRouter (entity extraction)
- **Storage**: SQLite (job store), Redis (FalkorDB)
- **CLI**: Click + Rich

## Quick Start
```bash
# Setup (installs deps, starts Docker, creates .env)
make setup

# Configure API key (optional - falls back to heuristics)
# ANTHROPIC_API_KEY=sk-ant-... or OPENROUTER_API_KEY=sk-or-...

# Start everything
make dev
```

## Testing Commands
```bash
make test            # All tests (90+ tests)
make test-unit       # Unit tests only (fast)
make test-int        # Integration tests (requires Docker)
make test-cov        # With coverage report
```

## Project Structure
```
code-atlas/
├── backend/
│   └── src/code_atlas/
│       ├── api/v1/           # FastAPI routes
│       ├── auth/             # API key management
│       ├── schemas/          # Pydantic models
│       ├── entity_resolver.py
│       ├── graph_populator.py
│       ├── insight_extractor.py
│       └── pipeline.py
├── frontend/
│   ├── src/pages/
│   └── src/components/
└── docs/
```

## FalkorDB/Neo4j Standards

### Graph Schema
```cypher
// Core node types
(:Session {id, project, timestamp})
(:Entity {id, type, name, description})
(:Decision {id, description, rationale})

// Relationships
(Session)-[:CONTAINS]->(Entity)
(Entity)-[:RELATES_TO]->(Entity)
(Session)-[:MADE]->(Decision)
```

### Query Patterns
```python
# Always use parameterized queries
graph.query(
    "MATCH (e:Entity {name: $name}) RETURN e",
    {"name": entity_name}
)

# Use indexes for frequently queried properties
# CREATE INDEX ON :Entity(name)
```

### Entity Deduplication
- Similarity threshold: 0.85 (configurable)
- Deduplication runs after each batch
- Manual merge available via API

## Cost Controls

### LLM Usage Limits
- Default: $0.02/session maximum
- Cumulative limit: $10.00 default
- Heuristic fallback: Free (no API calls)
- Cost tracking: Per-session and cumulative

### Configuration
```toml
# .code-atlas.toml
[extraction]
use_llm = true
max_cost_per_session_usd = 0.02
```

## API Standards
- Base path: `/api/v1/`
- Authentication: API key (optional in dev)
- WebSocket: `/ws/jobs/{job_id}` for real-time updates
- Rate limiting: None in dev, configurable in prod

## Quality Gates
- [x] Test coverage: 80%+ (30+ test files)
- [x] Graph query (simple): <50ms
- [x] Graph query (complex): <500ms
- [x] Entity extraction: <30s per session

## Environment Variables
See `.env.example`
Required: None (heuristic mode works without API keys)
Optional: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `CODE_ATLAS_ADMIN_API_KEY`

## Current Sprint
See `docs/PLAN.md` for active tasks and blockers.

## Human Gates (Required)
1. **Graph Schema**: Changes to node types or relationships
2. **Entity Extraction**: Changes to LLM prompts
3. **Cost Limits**: Changes to spending thresholds
4. **API Auth**: Changes to authentication logic
