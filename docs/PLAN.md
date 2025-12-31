# PLAN - Code Atlas Phase 4

## Current Status: Phase 4 Complete
## Last Updated: 2025-12-31

---

## Phase Summary

| Phase | Status | Outcomes |
|-------|--------|----------|
| Phase 0-2.5 | ✅ Complete | Core pipeline, API, frontend, tests |
| Phase 3 | ✅ Complete | GraphRAG, MCP structure, monitoring |
| Phase 4 | ✅ Complete | LLM integration, security, E2E |

---

## Phase 4 Overview

**Goal:** Complete RAG with actual LLM answers, add security headers, validate MCP, expand E2E tests.

**Key Insight from Evaluation:**
- Rate limiting is ALREADY IMPLEMENTED in `middleware.py` (lines 15-132)
- RAG service has complete structure but placeholder at line 201-204
- MCP server is structural - needs SDK installation
- Only 12 E2E tests exist, no coverage for RAG or Graph pages

---

# Epic 1: RAG LLM Integration

## Problem
RAG endpoint (`/api/v1/insights/rag/query`) returns context but generates placeholder answers instead of real LLM responses.

**Location:** `backend/src/code_atlas/rag_service.py:201-204`
```python
# TODO: Integrate with actual LLM client (Anthropic, OpenAI, etc.)
# For now, return placeholder
logger.info("LLM answer generation (placeholder)")
return self._generate_answer_from_context_simple(question, context)
```

## Files to Change

| File | Changes |
|------|---------|
| `backend/src/code_atlas/rag_service.py` | Add Anthropic client, implement `_generate_answer_with_llm` |
| `backend/src/code_atlas/api/v1/insights.py` | Pass Anthropic client to RAG service (line 438) |
| `backend/src/code_atlas/config.py` | Add RAG cost limit settings |
| `backend/tests/test_rag_llm.py` | New unit tests for LLM integration |

## Functions

### `rag_service.py`

**`_generate_answer_with_llm(self, question: str, context: str) -> str`**
Replace placeholder with actual Anthropic API call. Uses claude-3-haiku for cost efficiency. Constructs prompt with context and returns generated answer.

**`_create_rag_prompt(self, question: str, context: str) -> str`**
Builds structured prompt for RAG answer generation. Includes system instructions, context from knowledge graph, and user question.

**`_estimate_rag_cost(self, prompt_tokens: int, completion_tokens: int) -> float`**
Calculate cost for RAG query based on Haiku pricing. Used for cost tracking and limits.

### `insights.py`

**`_get_anthropic_client() -> Anthropic | None`**
Factory function to create Anthropic client from environment. Returns None if API key not configured, enabling graceful fallback.

## Tests

| Test Name | Behavior |
|-----------|----------|
| `test_rag_with_llm_client_generates_answer` | LLM client called, answer returned |
| `test_rag_without_llm_falls_back_to_context` | No LLM returns context-based answer |
| `test_rag_llm_prompt_includes_context` | Prompt contains retrieved entities |
| `test_rag_cost_tracked_per_query` | Cost recorded after LLM call |
| `test_rag_handles_llm_api_error_gracefully` | API error returns fallback answer |
| `test_rag_respects_max_tokens_limit` | Response truncated at limit |

---

# Epic 2: Security Headers Middleware

## Problem
Application has rate limiting but lacks security headers (HSTS, CSP, X-Frame-Options) required for production deployment.

## Files to Change

| File | Changes |
|------|---------|
| `backend/src/code_atlas/api/middleware.py` | Add `SecurityHeadersMiddleware` class |
| `backend/src/code_atlas/api/main.py` | Register security middleware |
| `backend/tests/test_security_headers.py` | New tests for header presence |

## Functions

### `middleware.py`

**`SecurityHeadersMiddleware.__init__(self, app, *, hsts_max_age: int, csp_policy: str, frame_options: str)`**
Initialize security headers middleware with configurable policies. Defaults to strict HSTS (1 year), basic CSP, and DENY frame options.

**`SecurityHeadersMiddleware.dispatch(self, request, call_next) -> Response`**
Add security headers to every response. Headers: Strict-Transport-Security, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.

### `main.py`

**Update `_create_app()` (line ~130)**
Add SecurityHeadersMiddleware after CORS middleware. Use environment-aware defaults (relaxed in dev, strict in prod).

## Tests

| Test Name | Behavior |
|-----------|----------|
| `test_response_includes_hsts_header` | HSTS header present with max-age |
| `test_response_includes_csp_header` | CSP header present |
| `test_response_includes_frame_options` | X-Frame-Options DENY present |
| `test_response_includes_content_type_options` | X-Content-Type-Options nosniff |
| `test_security_headers_on_api_endpoints` | All /api/ paths have headers |
| `test_security_headers_configurable` | Custom values applied correctly |

---

# Epic 3: MCP SDK Integration

## Problem
MCP server exists structurally but SDK not installed. Server raises ImportError when instantiated.

**Location:** `backend/src/code_atlas/mcp/server.py:17-23`
```python
try:
    from mcp import Server  # type: ignore[import-untyped]
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
```

## Files to Change

| File | Changes |
|------|---------|
| `backend/pyproject.toml` | Add `mcp` dependency |
| `backend/src/code_atlas/mcp/server.py` | Verify SDK compatibility, fix any API mismatches |
| `backend/src/code_atlas/mcp/tools.py` | Ensure tool definitions match SDK format |
| `backend/tests/test_mcp_integration.py` | New integration tests |
| `README.md` | Add MCP setup instructions |

## Functions

### `server.py`

**`MCPServer._setup_resources(self) -> None`**
Update resource registration to match MCP SDK API. Ensure async handlers return correct format.

**`MCPServer._setup_tools(self) -> None`**
Update tool registration to match MCP SDK API. Verify tool schemas are valid.

**`MCPServer.run(self, stdio: bool) -> None`**
Verify SDK's run method signature. Handle both stdio and potential HTTP transport.

### New: `cli_mcp.py`

**`start_mcp_server() -> None`**
CLI entrypoint for MCP server. Creates dependencies, initializes server, runs event loop.

## Tests

| Test Name | Behavior |
|-----------|----------|
| `test_mcp_server_initializes_with_sdk` | Server creates without ImportError |
| `test_mcp_list_resources_returns_valid_format` | Resources match MCP schema |
| `test_mcp_list_tools_returns_valid_format` | Tools match MCP schema |
| `test_mcp_call_tool_query_graph_works` | query_graph tool executes |
| `test_mcp_call_tool_search_entities_works` | search_entities tool executes |
| `test_mcp_server_handles_malformed_request` | Invalid request returns error |

---

# Epic 4: E2E Test Expansion

## Problem
Only 12 E2E tests exist covering navigation. No tests for RAG page, Graph visualization, or API error states.

## Files to Change

| File | Changes |
|------|---------|
| `frontend/e2e/rag.spec.ts` | New file: RAG page tests |
| `frontend/e2e/graph.spec.ts` | New file: Graph visualization tests |
| `frontend/e2e/navigation.spec.ts` | Add RAG link test, fix any failures |
| `frontend/playwright.config.ts` | Verify test configuration |

## Test Suites

### `rag.spec.ts` (New)

| Test Name | Behavior |
|-----------|----------|
| `test_rag_page_loads_with_input_form` | Page has question input and submit |
| `test_rag_submitting_question_shows_loading` | Loading state appears on submit |
| `test_rag_displays_answer_after_query` | Answer text visible after API call |
| `test_rag_shows_source_entities` | Sources section lists entities |
| `test_rag_handles_empty_results` | Empty state message shown |
| `test_rag_handles_api_error` | Error message displayed gracefully |

### `graph.spec.ts` (New)

| Test Name | Behavior |
|-----------|----------|
| `test_graph_page_loads_visualization` | Canvas/SVG element present |
| `test_graph_shows_loading_initially` | Loading indicator before data |
| `test_graph_displays_nodes_after_load` | Nodes visible in visualization |
| `test_graph_node_click_shows_details` | Click node opens details panel |
| `test_graph_filter_by_entity_type` | Filter updates visible nodes |
| `test_graph_handles_empty_graph` | Empty state for no entities |

### `navigation.spec.ts` (Update)

| Test Name | Behavior |
|-----------|----------|
| `test_navigate_to_rag_page` | Click RAG link, verify URL and heading |

---

## Implementation Order

```
Epic 1: RAG LLM Integration     [HIGHEST PRIORITY - Core Functionality]
    │
    ├── 1.1 Add Anthropic client to RAG service
    ├── 1.2 Update insights.py to pass client
    ├── 1.3 Add cost tracking settings
    └── 1.4 Write unit tests

Epic 2: Security Headers        [HIGH PRIORITY - Production Requirement]
    │
    ├── 2.1 Create SecurityHeadersMiddleware
    ├── 2.2 Register in main.py
    └── 2.3 Write tests

Epic 3: MCP SDK Integration     [MEDIUM PRIORITY - Feature Completion]
    │
    ├── 3.1 Install MCP SDK
    ├── 3.2 Verify server compatibility
    ├── 3.3 Write integration tests
    └── 3.4 Update README

Epic 4: E2E Test Expansion      [MEDIUM PRIORITY - Quality Assurance]
    │
    ├── 4.1 Create rag.spec.ts
    ├── 4.2 Create graph.spec.ts
    └── 4.3 Update navigation.spec.ts
```

---

## Effort Estimates

| Epic | Tasks | Estimate |
|------|-------|----------|
| Epic 1: RAG LLM | 4 | 3h |
| Epic 2: Security Headers | 3 | 1.5h |
| Epic 3: MCP SDK | 4 | 2h |
| Epic 4: E2E Tests | 3 | 2h |
| **Total** | **14** | **8.5h** |

---

## Success Criteria

- [x] `POST /api/v1/insights/rag/query` returns LLM-generated answers (commit: a460720)
- [x] All API responses include security headers (HSTS, CSP, X-Frame-Options) (commit: 1452f2a)
- [x] MCP server starts without ImportError (commit: a261b49)
- [x] 30 E2E tests (12 existing + 18 new) (commit: 3d15cba)
- [x] All unit tests pass with no warnings

---

## Dependencies

**Installed:**
- `anthropic` - For LLM integration
- `numpy`, `sentence-transformers` - For embeddings
- `mcp` - Model Context Protocol SDK (v1.25.0)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM API costs | Use Haiku model, add per-query cost limit |
| MCP SDK API changes | Check SDK version, pin dependency |
| E2E test flakiness | Use stable selectors, add retries |
| Security header conflicts | Test CORS compatibility |

---

**Plan Created:** 2025-12-12
**Phase 4 Completed:** 2025-12-31

## Commits

| Epic | Commit | Description |
|------|--------|-------------|
| Epic 1 | a460720 | feat(rag): integrate Anthropic LLM for answer generation |
| Epic 2 | 1452f2a | feat(security): add security headers middleware |
| Epic 3 | a261b49 | feat(mcp): install SDK and update server implementation |
| Epic 4 | 3d15cba | test(e2e): add RAG and Graph page E2E tests |
