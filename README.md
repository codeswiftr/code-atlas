# Code Atlas – Claude Session Knowledge Graph

Code Atlas converts Claude Code session logs into a searchable knowledge graph so Codeswiftr teams can reuse insights, spot patterns, and power GraphRAG workflows.

## Structure
```
codeswiftr-com/code-atlas
├── backend/        # Python pipeline + services (to be implemented)
├── frontend/       # Future UI/console placeholder
└── docs/           # Living documentation (brief, plan, ADRs, etc.)
```

## Quick Start (Planned)
```bash
# Launch services
docker compose up -d falkordb redis

# Run pipeline (placeholder)
uv run python -m code_atlas.cli run --days-back 7
```

See `docs/` for project brief, active context, system patterns, ADRs, progress, and plan.
