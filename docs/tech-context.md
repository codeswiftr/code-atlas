# Technical Context & ADRs · Code Atlas

## Stack Snapshot
- **Language**: Python 3.11+
- **Runtime**: Poetry/uv-managed env, Docker for services
- **LLM Providers**: Anthropic Claude (default), OpenRouter (via LiteLLM), Local Llama 3.3 70B via Ollama fallback
- **Knowledge Graph**: FalkorDB (Redis protocol), optional Neo4j adapter
- **Task Orchestration**: Asyncio workers + optional Celery for large batches
- **Monitoring**: Prometheus + Grafana, OpenTelemetry traces

---

## ADR-001 · Knowledge Graph Engine
- **Status**: Accepted · 2025-11-12
- **Context**: Need graph optimized for AI/GraphRAG workloads with low-latency traversal and simple deployment.
- **Options Considered**:
  1. Neo4j Aura (managed) – mature ecosystem, higher cost, JVM footprint.
  2. Memgraph – performant, but smaller community, limited GraphRAG references.
  3. FalkorDB – Redis-compatible, C-based, 200x faster benchmarks, GraphRAG docs.
- **Decision**: Use **FalkorDB** for MVP. It provides single-binary deployment (Docker), OpenCypher support, and GraphRAG utilities while keeping infra lean.
- **Consequences**:
  - ✅ Fast ingestion + traversal, easy to run locally.
  - ✅ Works with existing Redis clients (simpler ops).
  - ⚠️ Fewer managed offerings; need to own backup/HA story.
  - Mitigation: Provide migration path to Neo4j via exporter script before public GA.

## ADR-002 · LLM Extraction Strategy
- **Status**: Accepted · 2025-11-12, Updated 2025-01-16
- **Context**: Need structured entity/relationship extraction with controllable cost and privacy guarantees.
- **Options**:
  1. Anthropic Claude Sonnet – high quality, moderate cost.
  2. Claude Haiku – cheaper, slightly lower fidelity.
  3. OpenRouter (via LiteLLM) – access to multiple models (Grok, Llama, etc.) with unified API.
  4. Local Llama 3.3 70B via Ollama – zero marginal cost, heavier infra.
- **Decision**: Default to **Claude Sonnet** for production pipelines; support **OpenRouter** via LiteLLM for model flexibility and cost optimization. Expose configuration to switch between providers. Provide redaction + chunking to keep request cost <$0.02/session.
- **Consequences**:
  - ✅ High accuracy out-of-box; fewer false relations.
  - ✅ Multi-provider support enables cost optimization and model selection flexibility.
  - ⚠️ Requires API key management + spend monitoring.
  - ⚠️ OpenRouter pricing varies by model; use LiteLLM's cost tracking for accurate estimates.
  - Mitigation: Implement usage quotas + fallback path; document how to run offline with Llama.

## ADR-003 · Streaming Parser vs Bulk Load
- **Status**: Accepted · 2025-11-12
- **Context**: Claude session files can exceed 100 MB. Loading entire JSONL would spike memory and increase latency.
- **Decision**: Implement streaming parser using Python generators (line-by-line), assembling typed messages incrementally. Persist intermediate state for crash recovery.
- **Consequences**:
  - ✅ Predictable memory footprint, supports arbitrarily large sessions.
  - ✅ Allows early filtering (skip tool output noise) before LLM invocation.
  - ⚠️ Slightly more complex code and testing.

## ADR-004 · Graph-first vs Document Store
- **Status**: Accepted · 2025-11-12
- **Context**: Could store extracted summaries as flat Markdown/JSON and use vector search, but we need relationship queries (“which library keeps failing in security scans?”).
- **Decision**: Graph-first persistence (FalkorDB) with optional vector index augmentation later.
- **Consequences**:
  - ✅ Enables Cypher queries, GraphRAG, multi-hop analytics.
  ﻿
- ⚠️ Engineers must learn Cypher; provide DSL snippets + helper CLI.

## ADR-005 · Deployment & Packaging
- **Status**: Proposed · Target decision 2025-11-19
- **Options**:
  1. Pure CLI + `docker compose up` for FalkorDB/Redis (fastest path).
  2. Full FastAPI service from day one with REST endpoints + UI.
- **Recommendation**: Start CLI-first (Phase 1-2), layer FastAPI/GraphQL service in Phase 3 once ingestion proves stable.
- **Pending Actions**: Evaluate need for multi-tenant auth, rate limiting, and secret handling before finalizing.
