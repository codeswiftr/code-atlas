# Progress Log · Code Atlas

- **2025-11-12**: Captured feasibility assessment + full technical specification for Claude → knowledge graph pipeline; confirmed access to session data and viable KG engines.
- **2025-11-12**: Created project scaffold (docs + backend/frontend directories) inside `codeswiftr-com` domain to prep for MVP build.
- **2025-11-12**: Documented architecture, ADRs, and execution plan; no code implemented yet.
- **2025-11-12**: Bootstrapped backend package with uv tooling, implemented session discovery/parser modules, Typer CLI, heuristic insight extractor, dry-run FalkorDB populator, and unit tests covering the pipeline skeleton.
- **2025-11-14**: Implemented FalkorDB real connection tests, provenance metadata attachment, LLM extraction with retry logic, end-to-end pipeline integration tests, and retry logic with error quarantine.
- **2025-11-14**: Completed Phase 2 features: cost guards, token chunking for large sessions, and schema validation with Pydantic.
- **2025-11-14**: Completed Phase 3 features: configuration file support (.code-atlas.toml), structured logging with structlog, and CLI report command.
- **2025-01-16**: Implemented structured logging with structlog across all modules. Added contextual metadata (session_id, stage, duration, error types). Configured JSON logging with ISO timestamps and callsite information.
- **2025-01-16**: Completed final validation phase - fixed all linting errors (UP045, B008, E501, I001, UP035, UP031, B904), updated all documentation, improved integration test fixtures, achieved 82% test coverage. MVP ready for deployment.
- **2025-01-16**: Beta launch preparation - consolidating documentation, creating configuration templates, cleaning up outdated files, and preparing beta launch checklist.

## Phase 2.1 Soft Launch (November 2025)

- **2025-11-27**: Implemented comprehensive REST API with FastAPI including session management, graph queries, and visualization endpoints. Added rate limiting middleware and OpenAPI documentation.
- **2025-11-27**: Added OpenRouter multi-provider support via LiteLLM for model flexibility (Grok, Llama, Claude).
- **2025-11-27**: Implemented SQLite-backed job persistence system (`job_store.py`) with status tracking, cleanup policies, and survival across server restarts.
- **2025-11-27**: Implemented API key management system with SHA256 hashing, scoped permissions (read/write/process/admin), rate limiting per key, and full CRUD operations via admin endpoints.
- **2025-11-27**: Added full-text entity search endpoint with fuzzy matching (SequenceMatcher), relevance scoring, and markdown highlighting.
- **2025-11-27**: Added `execute_query()` method to GraphPopulator for read queries with parameter substitution and FalkorDB result parsing.
- **2025-11-27**: Implemented React frontend with TypeScript, Vite, and TailwindCSS including pages for Home, Sessions, Entities, and Graph visualization.
- **2025-11-27**: Created comprehensive test suites: test_job_store.py (11 tests), test_api_keys.py (16 tests), test_graph_search.py (17 tests). Total test count: 73+.

> **Next Update Cadence:** As needed during Phase 2.1 completion and Phase 2.2 planning.
