# Code Atlas - Complete Codebase Analysis

## Project Structure
```
code-atlas/
├── backend/
│   ├── src/code_atlas/           # Core Python modules (9 files)
│   │   ├── cli.py               # CLI entrypoint with Typer
│   │   ├── config.py            # Settings management with TOML support
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── graph_populator.py   # FalkorDB integration
│   │   ├── insight_extractor.py # LLM & heuristic extraction
│   │   ├── models.py            # Pydantic data models
│   │   ├── pipeline.py          # Orchestration with retry logic
│   │   ├── session_discovery.py # File discovery
│   │   └── session_parser.py    # JSONL streaming parser
│   ├── tests/                    # Test suite (7 files)
│   │   ├── test_chunking.py      # Token chunking tests
│   │   ├── test_config.py        # Configuration tests
│   │   ├── test_cost_guard.py    # Cost guard tests
│   │   ├── test_graph_populator.py # Database tests
│   │   ├── test_insight_extractor.py # LLM tests
│   │   ├── test_pipeline_integration.py # Integration tests
│   │   ├── test_session_discovery.py # Discovery tests
│   │   └── test_session_parser.py # Parser tests
│   ├── pyproject.toml            # Dependencies and config
│   ├── docker-compose.yml        # FalkorDB + Redis
│   └── .code-atlas.toml          # Configuration example
├── docs/
│   ├── PLAN.md                    # Implementation plan
│   ├── RUNBOOK.md                 # Operations guide
│   └── *.md                       # Documentation
└── README.md                      # Project overview
```

## Core Architecture

### Data Flow Pipeline
```
Claude Sessions (.jsonl)
    ↓ SessionDiscovery
File Scanning + Filtering
    ↓ SessionParser
Streaming JSONL Parser
    ↓ InsightExtractor
LLM Extraction (Claude) or Heuristics
    ↓ GraphPopulator
FalkorDB (Knowledge Graph)
```

### Key Components

#### 1. Session Discovery (session_discovery.py)
- Scans `~/.claude/projects/**/*.jsonl`
- Gitignore-style filtering
- Size guards (max 50MB per file)
- Project-based filtering

#### 2. Session Parser (session_parser.py)
- Streaming JSONL parser (memory-efficient)
- Message normalization (user/assistant/system/tool)
- Token counting from metadata
- File reference extraction

#### 3. Insight Extractor (insight_extractor.py)
- Dual mode: LLM (Claude API) + heuristic fallback
- Entity types: concept, file, tool, problem, solution
- Relationship extraction with confidence scores
- Cost calculation from actual token usage
- Schema validation with Pydantic
- Retry logic with exponential backoff
- Token chunking for sessions >12K tokens

#### 4. Graph Populator (graph_populator.py)
- FalkorDB integration via Redis protocol
- Deterministic node IDs (SHA1 hashing)
- Idempotent MERGE operations
- Provenance metadata (confidence, timestamps, source)
- Cypher query generation

#### 5. Pipeline Orchestrator (pipeline.py)
- End-to-end coordination
- Retry logic (3 attempts, 1s/2s/4s backoff)
- Error quarantine system
- Statistics tracking
- Cost guard integration

#### 6. CLI Interface (cli.py)
- `discover` command: List sessions
- `run` command: Execute pipeline
- `report` command: Query graph for insights
- Rich table output
- Configuration management (TOML + env vars)

## Configuration System

### Configuration Priority
1. `--config` flag
2. `.code-atlas.toml`
3. Environment variables
4. Default values

### Key Settings
- Claude API configuration
- Cost limits ($0.02/session, $10 cumulative)
- Discovery filters and size limits
- Graph connection settings
- Retry and quarantine configuration

## Cost Management

### Multi-Layer Protection
1. **Pre-flight estimation** - Check cost before API call
2. **Per-session limit** - $0.02 default
3. **Cumulative limit** - $10.00 default
4. **Graceful fallback** - Heuristics when limits exceeded

### Token Handling
- Real cost calculation from API usage data
- Token chunking for large sessions (>12K)
- Overlapping chunks (2 messages) for context

## Error Handling & Reliability

### Retry Strategy
- 3 attempts with exponential backoff
- Transient vs permanent failure detection
- Quarantine directory for failed sessions

### Error Types Handled
- Claude API errors
- JSON parsing errors
- Database connection issues
- File system errors
- Schema validation failures

## Testing Strategy

### Test Coverage (58 tests total)
- Unit tests: Core module functionality
- Integration tests: End-to-end pipeline
- Mock-based tests: API retry logic
- Real API tests: Claude integration (optional)

### Test Categories
1. Discovery & parsing tests
2. LLM extraction & cost tests
3. Graph population tests
4. Pipeline integration tests
5. Configuration tests
6. Chunking tests
7. Cost guard tests

## Current Limitations & Gaps

### Known Issues
1. **No real-time monitoring** - No metrics/alerting system
2. **Manual scaling** - No parallel processing
3. **Basic query interface** - CLI only, no REST API
4. **No data retention policies** - No TTL or cleanup
5. **No incremental processing** - Processes all sessions each run

### Missing Features for Production Scale
1. **File watcher** - Real-time session processing
2. **Batch scheduling** - Automated processing
3. **Metrics & Observability** - Prometheus/Grafana
4. **Query API** - FastAPI REST endpoints
5. **Dashboard** - Graph visualization
6. **Data lifecycle management** - Retention policies

### Security & Compliance Gaps
1. **PII detection** - No sensitive content filtering
2. **Access control** - No authentication/authorization
3. **Audit logging** - Limited security event tracking
4. **Data encryption** - No at-rest encryption
5. **Network security** - Basic Docker networking only

### Performance Limitations
1. **Memory usage** - All sessions loaded in discovery phase
2. **Processing speed** - Sequential processing only
3. **Database optimization** - No query optimization
4. **Cache layer** - No caching for repeated queries

## Technical Debt

### Code Quality Issues
1. **Logging inconsistency** - Mix of console.print() and logging
2. **Error handling** - Some generic exceptions
3. **Configuration validation** - Limited validation rules
4. **Type safety** - Some untyped functions

### Architecture Limitations
1. **Tight coupling** - Some circular dependencies
2. **Single responsibility** - Some classes doing too much
3. **Extension points** - Limited plugin architecture
4. **Testing isolation** - Some integration dependencies

## Future Enhancement Opportunities

### Phase 2 Enhancements
1. **Real-time Processing**
   - File watcher with inotify
   - Incremental processing
   - Resume capability

2. **Observability Stack**
   - Prometheus metrics
   - OpenTelemetry tracing
   - Grafana dashboards

3. **Query Interface**
   - FastAPI REST endpoints
   - GraphQL interface
   - GraphRAG capabilities

### Phase 3 Advanced Features
1. **Machine Learning**
   - Entity recognition models
   - Relationship prediction
   - Similarity matching

2. **Data Management**
   - Data retention policies
   - Automated cleanup
   - Backup/restore

3. **Enterprise Features**
   - Multi-tenant support
   - RBAC system
   - Audit trails
   - Compliance reporting

## Dependencies Analysis

### Core Dependencies
- **anthropic**: Claude API client
- **redis**: FalkorDB connectivity
- **pydantic**: Data validation
- **typer**: CLI framework
- **rich**: Terminal output
- **structlog**: Structured logging

### Security Considerations
- API key management
- Input validation
- SQL injection prevention
- Data exposure risks

### Performance Dependencies
- Connection pooling (Redis)
- Memory efficiency (streaming)
- Query optimization
- Batch processing capabilities

## Deployment & Operations

### Current Deployment
- Docker Compose (development)
- Single-node architecture
- Manual process execution
- Basic monitoring

### Production Requirements
- Container orchestration (Kubernetes)
- High availability setup
- Automated scaling
- Comprehensive monitoring
- Backup and disaster recovery

### Operations Tasks
- Health checks
- Performance monitoring
- Cost tracking
- Error alerting
- Capacity planning
- Security scanning
- Compliance reporting