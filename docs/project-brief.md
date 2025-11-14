# Project Brief · Code Atlas – Claude Session Knowledge Graph

## Vision
Turn every Claude Code session into durable, queryable product knowledge by automatically extracting concepts, files, problems, and solutions into a high-fidelity knowledge graph. Code Atlas gives Codeswiftr teams searchable memory, accelerates code reviews, and unlocks pattern discovery across all agentic coding efforts.

## Problem
- Claude Code stores session logs locally as JSONL blobs that quickly become unmanageable once multiple projects and agents are involved.
- Engineers repeatedly solve the same problems because there is no persistent knowledge base that links conversations, files, and outcomes.
- Manual curation does not scale; exporting and summarizing logs steals time from delivery and is inconsistently performed.
- Leadership lacks visibility into recurring risks, libraries, or architecture decisions discussed in AI-assisted sessions.

## Target Users & Market
- **Primary**: Codeswiftr internal engineers, AI agents, and diligence analysts who rely on Claude Code for daily development.
- **Secondary**: Portfolio founders who want searchable institutional memory, compliance teams needing immutable audit trails.
- **Opportunity**: Any organization adopting agentic coding workflows needs a memory layer; productizable as SaaS data plane for AI coding platforms.

## Solution Overview
1. **Session Discovery** – Scan `~/.claude/projects/**.jsonl` for new sessions, normalize metadata (project, timestamp, tokens).
2. **Streaming Parser** – Convert JSONL into structured turns (user, assistant, tool call, artifacts) without loading entire files into memory.
3. **Insight Extraction Engine** – Use Claude API or local Llama 3.3 70B to pull entities (concepts, files, tools, problems, solutions) plus relationships.
4. **Knowledge Graph Populator** – Persist nodes/edges in FalkorDB (preferred) with deduplication, lineage, and embeddings for hybrid search.
5. **Query & Retrieval Layer** – Cypher/GraphQL endpoints, semantic search, and pre-built reports (e.g., “Top recurring performance bugs this week”).

## Key Features (MVP Scope)
- Configurable session filters (project, date range, token count)
- Deterministic parser with per-turn provenance
- LLM-powered extraction prompts + validation heuristics
- FalkorDB schema: Session, Concept, File, Tool, Problem, Solution, Relationship edges
- Batch job CLI + Docker Compose runtime
- Metrics + dashboards for processed sessions, entity counts, relationship density

## Differentiators
- Purpose-built for Claude Code workflows (no generic chat export)
- Graph-first design (FalkorDB) enabling fast GraphRAG queries vs. flat doc stores
- Modular LLM adapter (Anthropic API by default, pluggable local models to control cost)
- Full provenance: every node traces back to session + message timestamp
- Ready for compliance (retention windows, opt-out filters, encrypted lightweight artifacts)

## Technical Stack
- **Language**: Python 3.11+
- **LLM**: Anthropic Claude API (Haiku/Sonnet) or local Llama 3.3 70B via Ollama
- **Knowledge Graph**: FalkorDB (primary), optional Neo4j adapter
- **Storage**: Redis for task queue + state, optional Postgres for metrics
- **Containerization**: Docker Compose (FalkorDB, Redis, worker)
- **Monitoring**: Prometheus counters + Grafana dashboards, OpenTelemetry spans for each extraction stage

## Success Metrics
- Process 1,000 sessions/hour with <1% failure rate
- 20+ unique entities and 10+ relationships extracted per meaningful session
- Query latency <150 ms for common graph traversals
- 30% reduction in duplicated engineering effort (measured via qualitative feedback)
- Zero PII leakage: 100% of sensitive files honor allow/deny lists

## Go-to-Market & Extensions
- Internal adoption across Codeswiftr diligence pods
- Package CLI + Docker Compose for enterprise customers using Claude Code
- Future: push summarized insights back into Claude Projects via MCP, GraphRAG assistant for diligence teams, SOC2-ready audit exports.
