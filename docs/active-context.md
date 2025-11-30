# Active Context · Code Atlas
**Last Updated:** 2025-11-30
**Owner:** Codeswiftr Infra / Knowledge Systems Guild

## Current Status
- ✅ MVP Complete (Beta launched January 2025)
- ✅ **Phase 2.1 Soft Launch COMPLETE** (November 2025)
- ✅ REST API implemented with FastAPI (sessions, graph, admin endpoints)
- ✅ Job Persistence System (SQLite-backed) for server restart survival
- ✅ API Key Management with scoped permissions and rate limiting
- ✅ Full-Text Entity Search with fuzzy matching
- ✅ React Frontend with TypeScript/Vite/TailwindCSS
- ✅ WebSocket support for real-time job updates
- ✅ Entity Deduplication with similarity detection and merge tracking

## Phase 2.1 Features (Completed)
1. **REST API**: Full FastAPI service with OpenAPI documentation
2. **Job Persistence**: SQLite-backed storage surviving server restarts
3. **API Key Management**: SHA256 hashing, scoped permissions (read/write/process/admin)
4. **Full-Text Search**: Fuzzy matching with relevance scoring on entities
5. **React Frontend**: TypeScript, Vite, TailwindCSS with Home/Sessions/Entities/Graph pages
6. **Multi-Provider LLM**: OpenRouter support via LiteLLM (Grok, Llama, Claude)
7. **Rate Limiting**: Built-in rate limiting middleware (100/min standard, 1000/min admin)
8. **WebSocket Support**: Real-time job status updates via `/ws/jobs/{job_id}`
9. **Entity Deduplication**: Similarity-based detection (85% threshold), merge tracking, batch deduplication

## MVP Features (Completed)
1. **Session Discovery**: Scans Claude project directories with filtering and size guards
2. **Session Parsing**: Streaming JSONL parser with typed models
3. **LLM Extraction**: Anthropic/OpenRouter integration with retries, chunking, cost controls
4. **Graph Population**: FalkorDB integration with provenance metadata
5. **Retry Logic**: Exponential backoff with error quarantine
6. **Cost Guards**: Per-session ($0.02 default) and cumulative limits enforced
7. **Token Chunking**: Handles large sessions (>12K tokens) with overlap
8. **Schema Validation**: Pydantic validation with graceful fallback
9. **Structured Logging**: JSON logs with contextual metadata
10. **CLI Commands**: discover, run, report, serve
11. **Configuration**: TOML file + environment variable support

## Immediate Objectives (Phase 2.1 Completion)
1. ✅ Job Persistence System
2. ✅ API Key Management
3. ✅ Full-Text Entity Search
4. ✅ Entity Deduplication
5. ✅ WebSocket real-time updates
6. ✅ All test failures resolved (73+ tests passing)
7. ✅ Documentation updated

## Architecture Overview
```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│    (TypeScript, Vite, TailwindCSS)                         │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI Backend                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Sessions │  │  Graph   │  │  Admin   │  │    Auth     │ │
│  │   API    │  │   API    │  │   API    │  │  Middleware │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘ │
├───────┼─────────────┼─────────────┼───────────────┼────────┤
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌──────▼──────┐ │
│  │ JobStore │  │  Graph   │  │ APIKey   │  │   Rate      │ │
│  │ (SQLite) │  │Populator │  │ Manager  │  │  Limiter    │ │
│  └──────────┘  └────┬─────┘  └──────────┘  └─────────────┘ │
├─────────────────────┼───────────────────────────────────────┤
│               ┌─────▼─────┐                                 │
│               │ FalkorDB  │  (Redis protocol)               │
│               └───────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Files (Phase 2.1)
- `backend/src/code_atlas/job_store.py` - SQLite job persistence
- `backend/src/code_atlas/auth/api_keys.py` - API key management
- `backend/src/code_atlas/entity_resolver.py` - Entity deduplication system
- `backend/src/code_atlas/api/websocket.py` - WebSocket real-time updates
- `backend/src/code_atlas/api/v1/admin.py` - Admin endpoints (key CRUD)
- `backend/src/code_atlas/api/v1/graph.py` - Graph API with search
- `backend/src/code_atlas/schemas/auth.py` - Auth schemas
- `backend/src/code_atlas/schemas/graph.py` - Graph schemas (includes merge tracking)
- `frontend/src/` - React TypeScript frontend

## Resolved Blockers
- ✅ **Claude session location**: User-configurable via config file or CLI flags
- ✅ **LLM cost ceilings**: Cost guards enforce $0.02/session default
- ✅ **Graph bloat**: Deduplication implemented
- ✅ **Job persistence**: SQLite-backed storage implemented
- ✅ **API authentication**: API key system with scoped permissions

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic, SQLite
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **Database**: FalkorDB (graph), SQLite (jobs/keys)
- **LLM**: Anthropic Claude, OpenRouter (via LiteLLM)

## Milestones
- **2025-11-30**: ✅ Phase 2.1 COMPLETE - All 4 epics implemented and tested
- **2025-12-15**: Phase 2.2 planning (monitoring, advanced graph analytics, CI/CD)
- **2025-01-15**: Phase 3 preparation (GraphRAG assistant, Slack integration)

## References
- [PLAN.md](PLAN.md) - Implementation plan with epic details
- [SPRINT_PHASE_2_1.md](SPRINT_PHASE_2_1.md) - Phase 2.1 sprint plan
- [RUNBOOK.md](RUNBOOK.md) - Operations guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment checklist
