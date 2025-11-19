# PLAN · Code Atlas MVP

## Goals
Deliver an automated pipeline that ingests Claude Code sessions, extracts structured knowledge, and exposes a searchable graph for Codeswiftr teams. MVP success = process 50 sessions/day with <1% errors and provide at least one actionable insight report.

## Guiding Principles
1. **Automate end-to-end** – no manual copy/paste of conversations.
2. **Graph-first** – relationships unlocked via FalkorDB from day one.
3. **Cost-aware** – keep LLM spend <$0.02/session via batching + fallbacks.
4. **Secure-by-default** – allowlists, redaction, and retention policies baked in.

## Phase Breakdown

| Phase | Target Date | Outcomes |
| --- | --- | --- |
| Phase 0 – Setup | Nov 14 | Repo scaffold, Docker Compose (FalkorDB + Redis), baseline tests |
| Phase 1 – Core Pipeline | Nov 21 | Session discovery, streaming parser, MVP extractor + graph writes, CLI command |
| Phase 2 – Reliability | Nov 28 | Incremental ingest, retries, metrics, cost guards, documentation |
| Phase 3 – Delivery | Dec 6 | Query API, sample dashboards, GraphRAG assistant spike |

## Backlog (Phase 0–1)

### Epic: Environment & Tooling
- [x] Initialize backend repo with uv tooling, Ruff, Pytest.
- [x] Add Docker Compose stack (`falkordb`, `redis`, optional scaffolding for metrics).
- [x] Create `.code-atlas.toml` config (paths, exclusions, LLM settings).

### Epic: Ingestion Pipeline
- [x] Implement `SessionDiscovery` with allow/deny filters + size guard (checkpointing pending).
- [x] Build `SessionParser` (streaming JSONL, dataclasses, tests with fixture logs).
- [ ] Store raw turn metadata in lightweight SQLite cache for debugging (deferred to Phase 2).

### Epic: Insight Extraction
- [x] Author initial Claude prompt template + response schema contract.
- [x] Add LLM client abstraction (Anthropic with heuristic fallback + cost tracking hook).
- [x] Implement heuristic validation (confidence thresholds, dedupe).

### Epic: Knowledge Graph Persistence
- [x] Define base Cypher helpers + deterministic node IDs for session/entity upserts.
- [x] Implement idempotent writes with deterministic hashes (dry-run + Falkor ready).
- [x] Add provenance + TTL metadata, plus export to Neo4j-compatible CSV.

### Epic: Observability & Ops
- [ ] Instrument pipeline with Prometheus counters (sessions_processed, extraction_failures) (optional for MVP).
- [ ] Emit OpenTelemetry spans per stage (optional for MVP).
- [x] Add CLI report command (top entities, error summary).

---

## Detailed Implementation Plan (MVP Completion)

**Status**: ✅ MVP Complete - Ready for Deployment
**Updated**: 2025-01-16
**Completion Date**: 2025-01-16

### Phase 1: Critical Integrations (Week 1) - Priority: CRITICAL

#### Task 1.1: FalkorDB Real Connection & Testing (4h)
**Status**: ✅ Complete
**Files**: `backend/tests/test_graph_populator.py`

**Objectives**:
- Add integration test with real FalkorDB instance via docker-compose
- Verify Cypher query execution and node creation
- Test data cleanup and isolation

**Functions to Add**:
- `test_graph_populator_real_connection()` - Test basic FalkorDB connection
- `test_graph_populator_creates_session_node()` - Verify Session node creation
- `test_graph_populator_cleanup()` - Test data deletion

**Acceptance Criteria**:
- Tests connect to `redis://localhost:6379` (FalkorDB)
- Can create nodes, query them, and cleanup
- Fails gracefully if FalkorDB unavailable

---

#### Task 1.2: Add Provenance Metadata (6h)
**Status**: ✅ Complete
**Files**: `backend/src/code_atlas/graph_populator.py`, `backend/src/code_atlas/models.py`

**Objectives**:
- Attach confidence scores to entities
- Add timestamps to relationships
- Track source metadata (model version, extraction date)

**Functions to Add**:
- `GraphPopulator._add_provenance()` - Generate Cypher for provenance metadata
- `GraphPopulator._enrich_relationship()` - Add metadata to MENTIONS edges

**Changes**:
- Update `ExtractionResult` schema with confidence per entity
- Modify `_entity_queries()` to propagate metadata
- Add source tracking ("code_atlas", model version)

**Tests**: Provenance attached, confidence persisted, timestamps accurate

---

#### Task 1.3: LLM Extraction Testing & Cost Validation (8h)
**Status**: ✅ Complete
**Files**: `backend/tests/test_insight_extractor.py`, `backend/src/code_atlas/insight_extractor.py`

**Objectives**:
- Test real Anthropic API integration
- Validate extraction schema compliance
- Implement accurate cost calculation
- Add retry logic with exponential backoff

**Functions to Add**:
- `InsightExtractor._calculate_cost()` - Calculate cost from input/output tokens
- `InsightExtractor._validate_schema()` - Pydantic validation before return
- `InsightExtractor._retry_with_backoff()` - Exponential backoff for API failures

**Tests to Add**:
- `test_insight_extractor_llm_real_api()` - Real API call with cost tracking
- `test_insight_extractor_schema_validation()` - Malformed JSON handling
- `test_insight_extractor_cost_calculation()` - Cost accuracy verification

**Acceptance Criteria**:
- Real Claude API tested with minimal cost
- Schema validation prevents bad data
- Cost <$0.02/session verified

---

#### Task 1.4: End-to-End Pipeline Integration Test (6h)
**Status**: ✅ Complete
**New File**: `backend/tests/test_pipeline_integration.py`

**Objectives**:
- Test complete pipeline flow from discovery to graph
- Verify stats accuracy
- Test error isolation (one failure doesn't kill pipeline)

**Functions to Add**:
- `sample_session_files()` - Pytest fixture with 3 test JSONL sessions
- `test_pipeline_end_to_end_dry_run()` - Full pipeline without DB
- `test_pipeline_end_to_end_with_falkordb()` - Full pipeline with real DB
- `test_pipeline_error_recovery()` - Malformed session handling

**Tests**: Complete flow, node creation, relationship verification, error isolation

---

#### Task 1.5: Retry Logic & Error Recovery (6h)
**Status**: ✅ Complete
**Files**: `backend/src/code_atlas/pipeline.py`, `backend/src/code_atlas/exceptions.py`

**Objectives**:
- Retry failed sessions up to 3 times
- Quarantine permanently failed sessions
- Track retry attempts in stats

**Functions to Add**:
- `PipelineRunner._process_session_with_retry()` - Retry with exponential backoff
- `PipelineRunner._quarantine_session()` - Save failed session details
- `PipelineConfig` dataclass - Configure retries, delays, quarantine path

**Tests**: Retry on transient failure, quarantine permanent failures, limit enforcement

---

### Phase 2: Cost Guards & Validation (Week 1-2) - Priority: HIGH

#### Task 2.1: Implement Cost Guards (4h)
**Status**: ✅ Complete
**Files**: `backend/src/code_atlas/config.py`, `backend/src/code_atlas/insight_extractor.py`, `backend/tests/test_cost_guard.py`

**Objectives**:
- Enforce $0.02 per session limit
- Track cumulative cost across pipeline run
- Raise exception when limits exceeded

**Functions to Add**:
- `CostGuard.__init__()` - Initialize with limits
- `CostGuard.check_session()` - Verify session cost before processing
- `CostGuard.record()` - Track cumulative cost and enforce limits

**Tests**: Session limit enforced, cumulative limit enforced, exceptions raised

---

#### Task 2.2: Token Chunking for Large Sessions (6h)
**Status**: ✅ Complete
**File**: `backend/src/code_atlas/insight_extractor.py`

**Objectives**:
- Handle sessions >12K tokens
- Split into overlapping chunks
- Merge and deduplicate extractions

**Functions to Add**:
- `InsightExtractor._chunk_session()` - Split into 12K token chunks with overlap
- `InsightExtractor._format_chunk()` - Format chunk for LLM prompt
- `InsightExtractor._merge_extractions()` - Deduplicate entities across chunks

**Tests**: Large session chunking, overlap preservation, deduplication

---

#### Task 2.3: Schema Validation with Pydantic (3h)
**Status**: ✅ Complete
**File**: `backend/src/code_atlas/insight_extractor.py`

**Objectives**:
- Validate LLM responses before accepting
- Fallback to heuristics on validation failure
- Log validation errors for debugging

**Changes**:
- Add Pydantic validation in `_call_llm()`
- Log errors with session context
- Graceful fallback to heuristics

**Tests**: Validation success, fallback on failure, error logging

---

### Phase 3: Configuration & Observability (Week 2) - Priority: MEDIUM

#### Task 3.1: Structured Logging (4h)
**Status**: ✅ Complete
**Files**: All modules in `backend/src/code_atlas/`

**Objectives**:
- Replace console.print() with structlog
- Add contextual metadata
- Configure log levels

**Changes**:
- Migrate all logging to structlog
- Add session_id, stage, duration to logs
- Configure DEBUG, INFO, WARNING, ERROR levels

**Tests**: Log format, metadata inclusion, level filtering

---

#### Task 3.2: Configuration File Support (4h)
**Status**: ✅ Complete
**New Files**: `.code-atlas.toml` (example), `backend/src/code_atlas/config.py`

**Objectives**:
- Support .code-atlas.toml configuration
- Merge with environment variables (env takes precedence)
- Provide example configuration

**Functions to Add**:
- `AtlasSettings.from_toml()` - Load from TOML with section flattening
- `AtlasSettings.merge()` - Merge TOML and environment configs

**Tests**: TOML parsing, env override, defaults, invalid TOML handling

---

#### Task 3.3: CLI Report Command (3h)
**Status**: ✅ Complete
**File**: `backend/src/code_atlas/cli.py`

**Objectives**:
- Query FalkorDB for insights summary
- Display top entities and problems
- Show error summary

**Functions to Add**:
- `generate_report()` - Query graph and format output
- `_format_entity_table()` - Rich table with mentions and confidence
- `_format_error_summary()` - Display recent errors

**Tests**: Report generation, Cypher queries, table formatting

---

### Phase 4: Documentation (Week 2) - Priority: HIGH

#### Task 4.1: Update README (2h)
**Status**: ✅ Complete
**File**: `README.md`

**Sections to Add**:
- Quick start (prerequisites, installation)
- Configuration guide (.env and TOML)
- First pipeline run walkthrough
- Troubleshooting common issues

---

#### Task 4.2: Create Runbook (3h)
**Status**: ✅ Complete
**File**: `docs/RUNBOOK.md`

**Sections**:
- System requirements and deployment
- Configuration reference (all settings)
- Common operations (run, query, debug)
- Error codes and remediation steps
- Monitoring and backup procedures

---

#### Task 4.3: Final PLAN.md Updates (2h)
**Status**: ✅ Complete
**File**: `docs/PLAN.md` (this file)

**Objectives**:
- Check off completed tasks
- Update phase completion estimates
- Validate Definition of Done criteria
- Document any scope changes

## Phase 2 Preview
- Incremental ingest via file watcher, resume on failure.
- Sensitive content redaction + compliance checks.
- Batch scheduling via GitHub Actions or cron.

## Phase 3 Preview
- FastAPI query service (Cypher proxy, GraphRAG endpoint).
- Slack/MCP integration for natural language queries.
- Knowledge insights dashboard (superset/metabase) fed by Prometheus + graph stats.

## Dependencies & Risks
- Anthropic API quota + latency; need fallback path (local Llama) before scale.
- Disk + memory limits when scanning very large session directories.
- Potential legal review needed before ingesting customer-specific logs.

## Definition of Done (MVP)
1. ✅ CLI processes sessions from configurable directory and populates FalkorDB.
2. ✅ At least 5 entity types + 4 relationship types queryable via Cypher.
3. ✅ Automated test suite covering discovery, parsing, extraction schema validation (82% coverage).
4. ✅ Runbook + onboarding guide checked into repo.

## MVP Deployment Checklist
- [x] All Phase 1-3 tasks completed
- [x] Code quality validated (linting errors fixed)
- [x] Test suite passing (82% coverage)
- [x] Documentation updated and accurate
- [ ] Deployment checklist created
- [ ] End-to-end validation in clean environment
- [ ] Production deployment and smoke tests
