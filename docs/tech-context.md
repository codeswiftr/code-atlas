# Technical Context & ADRs · Code Atlas

## Stack Snapshot
- **Language**: Python 3.11+
- **Runtime**: uv-managed env, Docker for services
- **API Framework**: FastAPI with Pydantic v2
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **LLM Providers**: Anthropic Claude (default), OpenRouter (via LiteLLM), Local Llama 3.3 70B via Ollama fallback
- **Knowledge Graph**: FalkorDB (Redis protocol), optional Neo4j adapter
- **Job Storage**: SQLite (persistent job state, API keys)
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
- **Status**: Accepted · Updated 2025-11-27
- **Context**: Started CLI-first (Phase 1), now moving to full API service for Phase 2.
- **Options Evaluated**:
  1. Pure CLI + `docker compose up` for FalkorDB/Redis (MVP path - completed).
  2. Full FastAPI service with REST endpoints + UI (Phase 2.1).
- **Decision**: Implemented FastAPI REST API in Phase 2.1 with React frontend.
- **Consequences**:
  - ✅ Full programmatic access to all features via REST API
  - ✅ Interactive UI for session browsing and graph exploration
  - ✅ API key authentication with scoped permissions
  - ✅ Rate limiting middleware for production use
  - ⚠️ Additional operational complexity (frontend deployment)

## ADR-006 · Job Persistence
- **Status**: Accepted · 2025-11-27
- **Context**: Background processing jobs lost state on server restart; need durability.
- **Options Considered**:
  1. Redis for job state - simple but requires Redis running
  2. PostgreSQL - overkill for job tracking
  3. SQLite - lightweight, file-based, no additional dependencies
- **Decision**: Use **SQLite** for job persistence with file-based storage.
- **Consequences**:
  - ✅ Jobs survive server restarts
  - ✅ No additional service dependencies
  - ✅ Simple backup (single file)
  - ✅ Status tracking with timestamps and metadata
  - ⚠️ Not suitable for multi-instance deployment without shared storage

## ADR-007 · API Key Management
- **Status**: Accepted · 2025-11-27
- **Context**: Need secure API authentication with fine-grained permissions.
- **Options Considered**:
  1. JWT tokens - complex, requires refresh flow
  2. API keys with hashing - simple, stateless validation
  3. OAuth2 - overkill for current use case
- **Decision**: Implement **API key system** with SHA256 hashing and scoped permissions.
- **Consequences**:
  - ✅ Simple integration (single header)
  - ✅ Scoped permissions (read/write/process/admin)
  - ✅ Rate limiting per key
  - ✅ Usage tracking and statistics
  - ⚠️ Keys are long-lived; consider rotation policy

## ADR-008 · Frontend Technology
- **Status**: Accepted · 2025-11-27
- **Context**: Need web UI for session browsing, entity exploration, and graph visualization.
- **Options Considered**:
  1. Server-side rendering (Jinja2) - simple but limited interactivity
  2. React + TypeScript - modern, type-safe, rich ecosystem
  3. Vue.js - similar to React, smaller community
- **Decision**: Use **React 18 with TypeScript**, Vite for build tooling, TailwindCSS for styling.
- **Consequences**:
  - ✅ Strong type safety with TypeScript
  - ✅ Fast development with Vite HMR
  - ✅ Utility-first CSS with TailwindCSS
  - ✅ Rich ecosystem for graph visualization (D3.js, Cytoscape.js)
  - ⚠️ Separate build/deploy pipeline from backend

## ADR-009 · WebSocket for Real-Time Updates
- **Status**: Accepted · 2025-11-30
- **Context**: Processing jobs can take significant time; users need real-time feedback without polling.
- **Options Considered**:
  1. HTTP polling - simple but inefficient, high latency
  2. Server-Sent Events (SSE) - unidirectional, simpler than WebSocket
  3. WebSocket - bidirectional, low latency, well supported
- **Decision**: Use **WebSocket** via FastAPI's native WebSocket support.
- **Consequences**:
  - ✅ Real-time updates with minimal latency
  - ✅ Native FastAPI support via Starlette
  - ✅ Connection manager handles multiple concurrent clients
  - ⚠️ Requires connection state management
  - ⚠️ Need reconnection logic in frontend

## ADR-010 · Entity Deduplication Strategy
- **Status**: Accepted · 2025-11-30
- **Context**: Same entities extracted from multiple sessions create duplicates; need merge capability.
- **Options Considered**:
  1. Exact match only - misses variations like "auth" vs "authentication"
  2. Fuzzy matching with Levenshtein distance - common approach, moderate accuracy
  3. Fuzzy matching with SequenceMatcher - Python standard library, good balance
  4. ML-based entity resolution - most accurate, but complex and resource-intensive
- **Decision**: Use **SequenceMatcher** from Python's `difflib` with 85% similarity threshold.
- **Implementation**:
  - `EntityResolver` class with find_similar, resolve, merge_entities methods
  - Merge tracking with full history (source, target, timestamp, similarity score)
  - Batch deduplication for processing multiple entities efficiently
  - Integration with GraphPopulator via lazy initialization
- **Consequences**:
  - ✅ Catches common variations (case, typos, abbreviations)
  - ✅ No external dependencies
  - ✅ Full merge history for auditing
  - ✅ Batch processing for efficiency
  - ⚠️ May miss semantic similarity ("OAuth" vs "authentication")
  - Mitigation: Add synonym support in future version
