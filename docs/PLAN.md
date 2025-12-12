# PLAN - Code Atlas

## Current Status: Phase 4 Ready
## Last Updated: 2025-12-12

---

## Phase Summary

| Phase | Status | Outcomes |
|-------|--------|----------|
| Phase 0 – Setup | ✅ Complete | Repo scaffold, Docker Compose, baseline tests |
| Phase 1 – Core Pipeline | ✅ Complete | Session discovery, parser, extractor, graph writes, CLI |
| Phase 1.5 – Foundational Stability | ✅ Complete | Logging, exceptions, memory efficiency, parallel processing, metrics |
| Phase 2 – Production Viability | ✅ Complete | REST API, authentication, frontend, job persistence |
| Phase 2.5 – Quality & Testing | ✅ Complete | Frontend tests (66/66), backend tests (289), E2E framework |
| Phase 3 – GraphRAG & Integration | ✅ Complete | Embeddings, vector storage, hybrid search, RAG, MCP, monitoring |
| **Phase 4 – Completion & Hardening** | 📋 **Ready** | LLM integration, E2E validation, security, documentation |

---

# Phase 4: Integration, LLM Completion & Production Hardening

## Overview

Phase 4 completes the Phase 3 implementation by integrating the LLM for RAG answer generation, validating all features through comprehensive testing, and hardening the system for production deployment.

**Key Objectives:**
1. Complete RAG with actual LLM answer generation
2. Validate Phase 3 features through E2E and integration testing
3. Add production security hardening (rate limiting, security headers)
4. Polish documentation and user experience

## Success Criteria

- [ ] RAG endpoint generates answers using Claude/Anthropic API
- [ ] All E2E tests pass (12 existing + 6 new)
- [ ] MCP server works with Claude Desktop
- [ ] Rate limiting middleware active
- [ ] Security headers (HSTS, CSP) in place
- [ ] README updated with Phase 3/4 features
- [ ] All tests pass with no deprecation warnings

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│    + RAG.tsx (Q&A Interface)                               │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI Backend                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ RAG API  │  │  Graph   │  │  MCP     │  │  Security   │ │
│  │ +LLM Int │  │   API    │  │  Server  │  │  Middleware │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └─────────────┘ │
├───────┼──────────────────────────────────────────────────────┤
│  ┌────▼─────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Anthropic│  │ Hybrid   │  │ Vector   │                  │
│  │ Client   │  │ Search   │  │ Store    │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### RAG LLM Integration

**Current State:** RAG retrieves context but uses placeholder for answer generation (line 201 in `rag_service.py`)

**Target State:** Full LLM integration using existing Anthropic client pattern from `insight_extractor.py`

```python
# Integration approach - reuse existing Anthropic client
from anthropic import Anthropic

class RAGService:
    def __init__(self, ..., anthropic_client: Anthropic | None = None):
        self.llm_client = anthropic_client or Anthropic()

    async def _generate_answer_with_llm(self, question: str, context: str) -> str:
        response = self.llm_client.messages.create(
            model="claude-3-haiku-20240307",  # Cost-effective for Q&A
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

### Security Middleware

**New middleware stack:**
1. Rate limiting (existing config, needs middleware)
2. Security headers (HSTS, CSP, X-Frame-Options)
3. Request size limits

### Dependencies

**Existing (already installed):**
- anthropic (for LLM)
- numpy, sentence-transformers (for embeddings)
- fastapi, uvicorn (API framework)

**New (to install):**
- mcp (Model Context Protocol SDK)

---

## Implementation Plan

### Phase 4.1: RAG LLM Integration (Priority 1)

| Task | Description | Agent/Skill | Est |
|------|-------------|-------------|-----|
| 4.1.1 | Integrate Anthropic client into RAGService | backend-engineer | 2h |
| 4.1.2 | Add streaming support for long answers | backend-engineer | 1h |
| 4.1.3 | Add cost tracking for RAG queries | backend-engineer | 1h |
| 4.1.4 | Create unit tests for LLM integration | qa-test-guardian | 1h |
| 4.1.5 | Test with real questions on live graph | - | 1h |

**Checkpoint:** RAG endpoint returns LLM-generated answers with source citations

---

### Phase 4.2: E2E Testing Validation (Priority 1)

| Task | Description | Agent/Skill | Est |
|------|-------------|-------------|-----|
| 4.2.1 | Run existing Playwright tests, fix failures | qa-test-guardian | 2h |
| 4.2.2 | Add E2E tests for RAG page | qa-test-guardian | 2h |
| 4.2.3 | Add E2E tests for Graph visualization | qa-test-guardian | 1h |
| 4.2.4 | Add API integration tests for new endpoints | qa-test-guardian | 2h |
| 4.2.5 | Document test results and coverage | - | 1h |

**Checkpoint:** All E2E tests pass, critical user flows validated

---

### Phase 4.3: MCP Integration Validation (Priority 2)

| Task | Description | Agent/Skill | Est |
|------|-------------|-------------|-----|
| 4.3.1 | Install MCP SDK (`uv add mcp`) | - | 10m |
| 4.3.2 | Test MCP server startup and tool listing | - | 1h |
| 4.3.3 | Test MCP with Claude Desktop | - | 2h |
| 4.3.4 | Fix any integration issues found | backend-engineer | 2h |
| 4.3.5 | Document MCP setup in README | - | 1h |

**Checkpoint:** MCP server works with Claude Desktop for queries

---

### Phase 4.4: Production Security Hardening (Priority 2)

| Task | Description | Agent/Skill | Est |
|------|-------------|-------------|-----|
| 4.4.1 | Add rate limiting middleware | backend-engineer | 2h |
| 4.4.2 | Add security headers middleware | security-auditor | 1h |
| 4.4.3 | Add request size limits | backend-engineer | 30m |
| 4.4.4 | Review error responses for info leakage | security-auditor | 1h |
| 4.4.5 | Add API key expiration enforcement | backend-engineer | 1h |
| 4.4.6 | Security audit of new endpoints | security-auditor | 1h |

**Checkpoint:** Security headers present, rate limiting active, no info leakage

---

### Phase 4.5: Documentation & Polish (Priority 3)

| Task | Description | Agent/Skill | Est |
|------|-------------|-------------|-----|
| 4.5.1 | Update README with GraphRAG features | - | 1h |
| 4.5.2 | Update README with MCP integration | - | 1h |
| 4.5.3 | Add RAG usage examples to docs | - | 1h |
| 4.5.4 | Improve RAG page loading states | frontend-builder | 1h |
| 4.5.5 | Add error messages and help text | frontend-builder | 1h |
| 4.5.6 | Update API documentation | - | 1h |

**Checkpoint:** Documentation complete, frontend polished

---

## Testing Strategy

### Unit Tests
- **RAG LLM Integration:** Mock Anthropic client, test prompt construction, error handling
- **Rate Limiting:** Test request counting, limit enforcement
- **Security Headers:** Verify headers present in responses
- **Coverage Target:** 80%+

### Integration Tests
- **RAG Pipeline:** End-to-end test with real embeddings and graph
- **MCP Tools:** Test each tool returns valid data
- **API Key Flow:** Test creation, validation, expiration

### E2E Tests (Playwright)
- **Navigation:** Home, Sessions, Entities, Graph, Insights, RAG pages
- **RAG Flow:** Ask question → see answer → view sources
- **Graph Viz:** Load graph → filter entities → click node
- **Error States:** Invalid routes, API errors, empty states

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM costs exceed budget | Medium | Use Haiku model, add cost limits per query |
| MCP SDK compatibility | Low | SDK is stable, fallback to HTTP if needed |
| Rate limiting complexity | Low | Use simple in-memory counter first |
| E2E test flakiness | Medium | Add retries, use stable selectors |

---

## Task Summary

| Phase | Tasks | Total Est | Priority |
|-------|-------|-----------|----------|
| 4.1: RAG LLM | 5 | 6h | P1 |
| 4.2: E2E Testing | 5 | 8h | P1 |
| 4.3: MCP Validation | 5 | 6h | P2 |
| 4.4: Security | 6 | 7h | P2 |
| 4.5: Documentation | 6 | 6h | P3 |
| **Total** | **27** | **33h** | - |

**Estimated Duration:** 4-5 days

---

## References

- [Anthropic API Docs](https://docs.anthropic.com)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [Playwright Docs](https://playwright.dev)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [docs/GRAPHRAG.md](./GRAPHRAG.md) - GraphRAG architecture
- [docs/MCP_INTEGRATION.md](./MCP_INTEGRATION.md) - MCP setup guide
- [docs/STRATEGIC_ASSESSMENT.md](./STRATEGIC_ASSESSMENT.md) - Phase 4 priorities

---

## Historical Phases (Complete)

<details>
<summary>Phase 0-1.5 Details (Click to expand)</summary>

### Phase 1.5 Completion Summary ✅

**Completion Date**: 2025-01-16

#### Critical Technical Debt Resolved

1. **Structured Logging** - JSON/console renderers, ISO timestamps, context variables
2. **Exception Hierarchy** - `CodeAtlasError` base class, specific error types
3. **Memory Efficiency** - `discover_generator()` for streaming processing
4. **Parallel Processing** - `ProcessPoolExecutor` for concurrent sessions
5. **Database Indexing** - Comprehensive FalkorDB indexing
6. **Metrics & Monitoring** - Prometheus metrics, health endpoints

</details>

<details>
<summary>Phase 2-2.5 Details (Click to expand)</summary>

### Phase 2.5 Completion Summary ✅

**Completion Date**: 2025-12-07

#### Features Delivered

1. **REST API** - 29 endpoints across 5 modules
2. **Authentication** - API key management with SHA256 hashing
3. **Frontend** - React + TypeScript + TailwindCSS
4. **Job Persistence** - SQLite-backed background jobs
5. **WebSocket** - Real-time job status updates
6. **Testing** - 66/66 frontend tests, 289 backend tests

</details>

<details>
<summary>Phase 3 Details (Click to expand)</summary>

### Phase 3 Completion Summary ✅

**Completion Date**: 2025-12-12

#### Features Delivered

1. **GraphRAG Foundation**
   - Embedding generation (sentence-transformers)
   - Vector storage (FalkorDB properties)
   - Hybrid search (Cypher + vector similarity)
   - RAG service (context retrieval)

2. **MCP Integration**
   - MCP server with stdio transport
   - Resources: sessions, entities, insights, graph
   - Tools: query_graph, search_entities, get_insights

3. **Enhanced Monitoring**
   - Grafana dashboards (cost, user activity, errors)
   - Prometheus alerting rules
   - Business metrics

4. **Quality Fixes**
   - E2E navigation role
   - FastAPI type fixes
   - Frontend RAG page

</details>

---

**Plan Created:** 2025-12-12
**Last Updated:** 2025-12-12
