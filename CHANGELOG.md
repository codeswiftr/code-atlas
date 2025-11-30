# Changelog

All notable changes to Code Atlas will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2.1 Soft Launch (November 2025)

#### Added - REST API
- Full FastAPI REST API with OpenAPI documentation
- Session management endpoints (discover, process, status, list, stats)
- Graph query endpoints (entities, relationships, visualization, stats)
- Admin endpoints for API key management
- Rate limiting middleware (100 req/min standard, 1000 req/min admin)
- CORS support for frontend integration

#### Added - Job Persistence System
- SQLite-backed job storage (`job_store.py`)
- Jobs survive server restarts
- Status tracking with timestamps and metadata
- Automatic cleanup of old jobs (configurable retention)
- Job listing with status filtering

#### Added - API Key Management
- SHA256 hashing for secure key storage
- Scoped permissions (read, write, process, admin)
- Rate limiting per API key
- Usage tracking and statistics
- Full CRUD operations via admin endpoints
- Constant-time comparison for timing attack prevention

#### Added - Full-Text Entity Search
- Search endpoint at `GET /api/v1/graph/entities/search`
- Fuzzy matching using SequenceMatcher for typo tolerance
- Relevance scoring (0.0 to 1.0)
- Markdown highlighting of matched terms
- Filtering by entity type and minimum score

#### Added - React Frontend
- TypeScript with strict type checking
- Vite for fast development and builds
- TailwindCSS for utility-first styling
- Pages: Home, Sessions, Entities, Graph
- API client with full type definitions
- Responsive design for desktop and mobile

#### Added - Multi-Provider LLM Support
- OpenRouter integration via LiteLLM
- Support for Grok, Llama, Claude via unified API
- Cost tracking across providers
- Model selection via configuration

#### Added - GraphPopulator Enhancements
- `execute_query()` method for read operations
- Parameter substitution in queries
- FalkorDB result parsing to Python dicts
- Node and relationship parsing
- Entity deduplication integration via EntityResolver

#### Added - WebSocket Support
- Real-time job status updates via `/ws/jobs/{job_id}`
- WebSocket connection manager for broadcasting updates
- Graceful connection handling and cleanup

#### Added - Entity Deduplication System
- `entity_resolver.py` with similarity-based detection (85% threshold)
- Merge tracking with full history and statistics
- Batch deduplication for processing multiple entities
- Integration with GraphPopulator for automatic deduplication
- Merge record schemas in graph.py (MergeRecordResponse, DeduplicationStatsResponse)

#### Tests
- `test_job_store.py` - 11 tests for job persistence
- `test_api_keys.py` - 16 tests for API key management
- `test_graph_search.py` - 17 tests for entity search
- `test_entity_resolver.py` - 23 tests for entity deduplication
- Total test count: 90+ tests

### Beta Launch Preparation (January 2025)
- Consolidated all documentation files
- Created configuration templates (`.env.example`)
- Archived outdated scaffold directories
- Updated all critical documentation for beta launch
- Created beta launch checklist and summary documents

## [0.1.0-beta] - 2025-01-17

### Added - MVP Features

#### Session Discovery
- Automatic scanning of `~/.claude/projects` for session files
- Configurable session filters (project, date range, token count)
- Size guards to skip large sessions (configurable limit)
- Support for `.code-atlas-ignore` files for exclusions

#### Session Parsing
- Streaming JSONL parser that processes files line-by-line
- Typed models for messages, tool calls, and artifacts
- Provenance tracking (timestamps, tokens, metadata)
- Memory-efficient processing for large sessions

#### Insight Extraction
- LLM-powered extraction using Claude API
- Heuristic fallback mode (no API costs)
- Automatic token chunking for sessions >12K tokens
- Schema validation with Pydantic
- Cost calculation and tracking
- Retry logic with exponential backoff

#### Knowledge Graph Persistence
- FalkorDB integration with deterministic node IDs
- Idempotent writes with deduplication
- Provenance metadata (confidence scores, timestamps, model versions)
- Support for multiple entity types (Session, File, Concept, Tool, Problem, Solution)
- Relationship tracking with metadata
- Export to Neo4j-compatible format (future)

#### CLI Commands
- `discover` - List discovered sessions with metadata
- `run` - Process sessions and populate knowledge graph
- `report` - Generate knowledge graph reports (top entities, statistics)
- Comprehensive CLI options (dry-run, limits, filters, etc.)

#### Configuration
- TOML configuration file support (`.code-atlas.toml`)
- Environment variable overrides (CODE_ATLAS_ prefix)
- Configuration priority: CLI flags > TOML > env vars > defaults
- Example configuration files provided

#### Error Handling
- Retry logic with exponential backoff (3 retries default)
- Error quarantine for permanently failed sessions
- Graceful degradation (heuristics fallback)
- Comprehensive error logging

#### Cost Management
- Per-session cost limits (default: $0.02/session)
- Cumulative cost limits (default: $10.00/run)
- Cost guards that enforce limits before processing
- Cost tracking and reporting

#### Logging
- Structured logging with structlog (JSON format)
- Contextual metadata (session_id, stage, duration, error types)
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- ISO timestamp format with callsite information

#### Testing
- Comprehensive test suite (82% coverage)
- Unit tests for all modules
- Integration tests with real FalkorDB instance
- End-to-end pipeline tests
- Test fixtures and sample data

### Fixed
- All linting errors resolved (Ruff, mypy)
- Memory efficiency improvements for large sessions
- Cost calculation accuracy
- Error handling robustness

### Documentation
- Complete user guide (README.md)
- Operations runbook (RUNBOOK.md)
- Deployment procedures (DEPLOYMENT.md)
- Implementation plan (PLAN.md)
- Beta launch checklist (BETA-LAUNCH.md)
- Beta summary (BETA-SUMMARY.md)
- Configuration reference
- Troubleshooting guides

### Security
- API keys stored securely (not committed)
- Environment variable validation
- Cost limits to prevent runaway spending
- Session filtering capabilities

## [0.0.1] - 2025-11-12

### Added
- Initial project scaffold
- Architecture documentation
- Technical specifications
- ADR (Architecture Decision Records)

---

## Release Notes Format

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Version History

- **0.1.0-beta** - Beta launch with complete MVP features
- **0.0.1** - Initial project setup

## Future Releases

### Planned for 0.2.0 (Phase 2.1) - COMPLETE
- ✅ FastAPI REST API with OpenAPI docs
- ✅ Job persistence with SQLite
- ✅ API key management with scoped permissions
- ✅ Full-text entity search with fuzzy matching
- ✅ React frontend (TypeScript/Vite/TailwindCSS)
- ✅ WebSocket real-time job updates
- ✅ Entity deduplication with merge tracking

### Planned for 0.3.0 (Phase 2.2)
- Incremental ingest via file watcher
- Advanced redaction and compliance checks
- Prometheus metrics and Grafana dashboards
- Batch scheduling (cron/GitHub Actions)
- Enhanced monitoring and alerting
- WebSocket for real-time updates

### Planned for 0.4.0 (Phase 3)
- GraphRAG assistant integration
- Slack/MCP integration
- Knowledge insights dashboard
- Advanced graph analytics
- Export/import functionality

