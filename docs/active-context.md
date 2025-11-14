# Active Context · Code Atlas
**Last Updated:** 2025-11-12  
**Owner:** Codeswiftr Infra / Knowledge Systems Guild

## Current Status
- ✅ Feasibility study + full technical specification completed (Claude → FalkorDB pipeline proven)
- ✅ Tech stack decisions drafted (Python 3.11, FalkorDB, Anthropic API with local LLM fallback)
- ✅ Backend repo bootstrapped with uv tooling, discovery/parser modules, heuristic extractor, dry-run graph populator, and Typer CLI + unit tests.
- 🟡 Insight extraction still uses heuristics by default; FalkorDB writes currently dry-run.

## Immediate Objectives (Week 1)
1. Enable Anthropic (and local Llama) extraction path with schema validation + retries.
2. Connect GraphPopulator to real FalkorDB instance (configurable URL) and add provenance metadata.
3. Process five historical Claude Code sessions end-to-end into FalkorDB and capture metrics output from CLI.

## Blockers & Risks
- **Claude session location variability**: need user-configurable path + permission checks.
- **LLM cost ceilings**: extraction per session must stay <$0.02 or use on-prem model.
- **Graph bloat**: deduplication + TTL policies required to keep FalkorDB performant.
- **PII/compliance**: filters for secrets/governed repos must be in place before wide rollout.

## Decisions Pending
- Final call on default LLM tier (Claude Sonnet vs Haiku vs local Llama 3.3 70B).
- Whether to include a lightweight web console in MVP or defer to CLI/queries.
- Governance workflow for redacting confidential customer data before persistence.

## Next Milestones
- **2025-11-19**: MVP pipeline demo (CLI processing 50 sessions with metrics).
- **2025-11-29**: Incremental ingest + monitoring, FalkorDB dashboards live.
- **2025-12-06**: Knowledge graph powered assistant prototype (GraphRAG query path).

## References
- Feasibility + spec summary (user-provided brief)
- Architecture review compilation `knowledge/research/architecture-reviews/2025-11-12-COMPILATION-all-architecture-reviews.md`
- FalkorDB + Anthropic integration notes (to be added under `research/`).
