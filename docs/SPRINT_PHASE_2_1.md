# Sprint Plan: Phase 2.1 - API + Minimal UI

**Sprint Goal**: Deliver REST API and basic web interface for Soft Launch
**Duration**: 6 weeks (starting 2025-11-26)
**Target**: Mid-January 2025

---

## Sprint Overview

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | API Foundation | FastAPI app, schemas, session endpoints |
| 2 | Graph API | Query endpoints, entity search, visualization data |
| 3 | Authentication | API keys, middleware, rate limiting |
| 4 | Basic UI | Landing page, session list, entity browser |
| 5 | Graph Visualization | Interactive graph view, entity details |
| 6 | Polish & Deploy | Testing, docs, production deployment |

---

## Week 1: API Foundation

### Day 1-2: FastAPI Application Setup
- [x] Create `api/` module structure
- [x] Unified server with metrics + REST API
- [x] Pydantic schemas for API requests/responses
- [x] Error handling middleware
- [x] CORS configuration

### Day 3-4: Session Processing Endpoints
- [x] `POST /api/v1/sessions/discover` - Discover available sessions
- [x] `POST /api/v1/sessions/process` - Submit sessions for processing
- [x] `GET /api/v1/sessions/{job_id}/status` - Get processing status
- [x] `GET /api/v1/sessions` - List processed sessions

### Day 5: Background Processing
- [ ] Async job queue for session processing
- [ ] Job status tracking
- [ ] Processing stats endpoint

**Acceptance Criteria**:
- API server starts with unified routes
- Sessions can be discovered via API
- Processing jobs can be submitted and tracked
- OpenAPI docs accessible at `/docs`

---

## Week 2: Graph Query API

### Day 1-2: Entity Search Endpoints
- [ ] `GET /api/v1/graph/entities` - List entities with filters
- [ ] `GET /api/v1/graph/entities/{id}` - Get entity details
- [ ] `GET /api/v1/graph/entities/search` - Full-text search

### Day 3-4: Relationship & Query Endpoints
- [ ] `GET /api/v1/graph/relationships` - List relationships
- [ ] `POST /api/v1/graph/query` - Execute Cypher queries (limited)
- [ ] `GET /api/v1/graph/paths` - Find paths between entities

### Day 5: Visualization Data
- [ ] `GET /api/v1/graph/visualization` - Graph data for D3/Cytoscape
- [ ] Node/edge formatting for frontend consumption
- [ ] Pagination for large graphs

**Acceptance Criteria**:
- Entities searchable via API
- Relationships queryable
- Graph visualization data endpoint works
- All responses follow schema

---

## Week 3: Authentication

### Day 1-2: API Key System
- [ ] API key generation and storage
- [ ] Key validation middleware
- [ ] Rate limiting per key
- [ ] Key management endpoints

### Day 3-4: Security Hardening
- [ ] Request authentication for all protected routes
- [ ] Audit logging for API access
- [ ] Input validation and sanitization
- [ ] Security headers (HSTS, CSP, etc.)

### Day 5: Admin Endpoints
- [ ] `POST /api/v1/admin/keys` - Generate API key
- [ ] `GET /api/v1/admin/keys` - List API keys
- [ ] `DELETE /api/v1/admin/keys/{id}` - Revoke key
- [ ] `GET /api/v1/admin/usage` - Usage statistics

**Acceptance Criteria**:
- All API endpoints require authentication
- API keys can be generated and revoked
- Rate limiting enforced
- Audit trail for all requests

---

## Week 4: Basic Web UI

### Day 1-2: Frontend Setup
- [ ] React + TypeScript project initialization
- [ ] Tailwind CSS with design system tokens
- [ ] API client setup with TanStack Query
- [ ] Routing with React Router

### Day 3-4: Core Pages
- [ ] Landing page with value proposition
- [ ] Session discovery interface
- [ ] Session list with status indicators
- [ ] Processing progress view

### Day 5: Entity Browser
- [ ] Entity list with filtering
- [ ] Entity detail view
- [ ] Basic relationship display
- [ ] Search functionality

**Acceptance Criteria**:
- Frontend builds and runs
- Can discover and process sessions via UI
- Entity browser functional
- Responsive design (mobile-friendly)

---

## Week 5: Graph Visualization

### Day 1-2: Graph Component
- [ ] D3.js or Cytoscape.js integration
- [ ] Node rendering by entity type
- [ ] Edge rendering by relationship type
- [ ] Zoom and pan controls

### Day 3-4: Interactivity
- [ ] Node selection and details panel
- [ ] Entity filtering in graph
- [ ] Layout options (force, hierarchical)
- [ ] Export graph as image

### Day 5: Polish
- [ ] Loading states and error handling
- [ ] Empty states
- [ ] Tooltips and help text
- [ ] Performance optimization

**Acceptance Criteria**:
- Graph visualization renders knowledge graph
- Interactive node selection
- Multiple layout options
- Performant with 1000+ nodes

---

## Week 6: Polish & Deploy

### Day 1-2: Testing
- [ ] API integration tests (80% coverage)
- [ ] Frontend component tests
- [ ] E2E tests with Playwright
- [ ] Load testing

### Day 3-4: Documentation
- [ ] API documentation in OpenAPI
- [ ] User guide for web UI
- [ ] Deployment documentation
- [ ] Troubleshooting guide

### Day 5: Production Deployment
- [ ] Multi-stage Dockerfile
- [ ] Production docker-compose
- [ ] Environment configuration
- [ ] Health monitoring setup
- [ ] Smoke tests

**Acceptance Criteria**:
- All tests passing
- Documentation complete
- Production deployment successful
- Monitoring active

---

## Technical Architecture

### Backend Structure
```
backend/src/code_atlas/
├── api/
│   ├── __init__.py
│   ├── main.py          # Unified FastAPI app
│   ├── dependencies.py  # Dependency injection
│   ├── middleware.py    # Auth, CORS, logging
│   └── v1/
│       ├── __init__.py
│       ├── sessions.py  # Session endpoints
│       ├── graph.py     # Graph query endpoints
│       └── admin.py     # Admin endpoints
├── schemas/
│   ├── __init__.py
│   ├── sessions.py      # Session schemas
│   ├── graph.py         # Graph schemas
│   └── common.py        # Shared schemas
└── auth/
    ├── __init__.py
    ├── api_keys.py      # API key management
    └── middleware.py    # Auth middleware
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/           # Base components
│   │   ├── graph/        # Graph visualization
│   │   ├── sessions/     # Session components
│   │   └── layout/       # Layout components
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── Sessions.tsx
│   │   ├── Graph.tsx
│   │   └── Entities.tsx
│   ├── api/
│   │   └── client.ts     # API client
│   ├── styles/
│   │   └── tokens.css    # Design system
│   └── App.tsx
└── package.json
```

---

## Definition of Done

### API Endpoints
- [ ] All endpoints documented in OpenAPI
- [ ] Request/response validation
- [ ] Error handling with proper status codes
- [ ] Authentication required
- [ ] Rate limiting applied
- [ ] Logging and metrics

### Web UI
- [ ] Responsive design (mobile + desktop)
- [ ] Loading and error states
- [ ] Accessibility (WCAG AA)
- [ ] Design system compliance
- [ ] Cross-browser testing

### Deployment
- [ ] Docker image builds successfully
- [ ] Health checks passing
- [ ] Metrics exposed
- [ ] Logs aggregated
- [ ] Backup configured

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Graph visualization performance | Pagination, node limiting, clustering |
| API security vulnerabilities | Security audit, input validation, rate limiting |
| Frontend complexity | Keep MVP minimal, defer advanced features |
| Deployment issues | Comprehensive testing, rollback plan |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| API response time (p95) | <500ms |
| Frontend load time | <3s |
| Test coverage (API) | >80% |
| Accessibility score | >90 |
| User onboarding success | >80% |

---

## Dependencies

- FalkorDB running and accessible
- Anthropic API key for LLM extraction
- Docker for containerization
- Node.js 18+ for frontend development

---

## Next Steps After Sprint

1. **User feedback collection** - Survey, interviews
2. **Performance optimization** - Based on metrics
3. **Feature prioritization** - For Phase 2.2
4. **Production hardening** - Security audit, load testing
