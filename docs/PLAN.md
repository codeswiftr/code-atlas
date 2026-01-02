# PLAN - Code Atlas Phase 5

## Current Status: Phase 5 Complete
## Last Updated: 2025-01-02

---

## Phase Summary

| Phase | Status | Outcomes |
|-------|--------|----------|
| Phase 0-2.5 | ✅ Complete | Core pipeline, API, frontend, tests |
| Phase 3 | ✅ Complete | GraphRAG, MCP structure, monitoring |
| Phase 4 | ✅ Complete | LLM integration, security, E2E |
| Phase 5 | ✅ Complete | Deployment, migrations, production |

---

## Phase 5 Overview

**Goal:** Deploy Code Atlas to production with Railway (backend) + Cloudflare Pages (frontend), establish database migrations, and ensure production monitoring.

**Key Findings from Codebase Audit:**
- Backend Docker config is 95% ready (minor fixes needed)
- CI/CD pipeline exists but lacks deployment triggers
- No Railway or Cloudflare Pages configuration files
- No database migration framework (risk for schema changes)
- Frontend lacks environment-aware builds
- Monitoring stack (Prometheus/Grafana) fully configured

---

# Epic 1: Railway Backend Deployment

## Problem
Backend has comprehensive Docker setup but no Railway platform configuration. CD pipeline builds images but doesn't trigger deployment.

## Files to Create/Change

| File | Action | Changes |
|------|--------|---------|
| `railway.json` | CREATE | Service definitions, env mapping |
| `railway.toml` | CREATE | Build configuration |
| `.github/workflows/cd.yml` | UPDATE | Add Railway deployment job |
| `backend/Dockerfile` | UPDATE | Fix README.md conditional copy |

## Functions/Tasks

### `railway.json` (New)
Define backend service with FalkorDB and Redis as attached services. Map environment variables from Railway dashboard. Configure health check endpoint `/health`.

### `railway.toml` (New)
Configure build settings: Dockerfile path, port exposure (8000), restart policy, and deployment triggers on main branch.

### `.github/workflows/cd.yml:deploy-railway` (New Job)
Add deployment job that triggers after Docker build. Uses Railway CLI to deploy latest image. Requires `RAILWAY_TOKEN` secret.

### `backend/Dockerfile:25` (Fix)
Change `COPY pyproject.toml uv.lock README.md ./` to conditional copy or create placeholder README if missing.

## Tests

| Test | Behavior |
|------|----------|
| `test_railway_config_valid_json` | railway.json is valid JSON |
| `test_railway_env_vars_mapped` | All required env vars documented |
| Manual: Railway deploy | Image deploys and health check passes |

---

# Epic 2: Cloudflare Pages Frontend Deployment

## Problem
Frontend builds with Vite but has no Cloudflare Pages configuration. Environment variables hardcoded to localhost.

## Files to Create/Change

| File | Action | Changes |
|------|--------|---------|
| `frontend/wrangler.toml` | CREATE | Cloudflare Pages config |
| `frontend/.env.production` | CREATE | Production environment |
| `frontend/vite.config.ts` | UPDATE | Environment detection |
| `.github/workflows/cd.yml` | UPDATE | Add Cloudflare deploy job |

## Functions/Tasks

### `frontend/wrangler.toml` (New)
Configure Pages project: build command `npm run build`, output directory `dist`, compatibility date. Set environment-specific variables for API URL.

### `frontend/.env.production` (New)
```
VITE_API_URL=https://api.codeatlas.dev
VITE_FORGE_CORE_URL=https://forge.codeswiftr.com
```

### `frontend/vite.config.ts:define` (Update)
Add environment variable injection for build-time configuration. Remove hardcoded localhost proxy in production builds.

### `.github/workflows/cd.yml:deploy-cloudflare` (New Job)
Add Cloudflare Pages deployment using `wrangler pages deploy`. Requires `CLOUDFLARE_API_TOKEN` secret.

## Tests

| Test | Behavior |
|------|----------|
| `test_build_uses_production_env` | Build outputs correct API URL |
| Manual: Cloudflare deploy | Site accessible at domain |
| E2E: smoke-test.spec.ts | Core navigation works on production |

---

# Epic 3: Database Migrations Framework

## Problem
No schema versioning for SQLite (job store) or FalkorDB (graph schema). Breaking changes not traceable.

## Files to Create/Change

| File | Action | Changes |
|------|--------|---------|
| `backend/alembic.ini` | CREATE | Alembic configuration |
| `backend/alembic/` | CREATE | Migrations directory |
| `backend/src/code_atlas/database.py` | CREATE | SQLAlchemy engine setup |
| `Makefile` | UPDATE | Add migration commands |

## Functions/Tasks

### `backend/alembic/env.py` (New)
Configure Alembic to use SQLModel models. Support both synchronous and asynchronous migrations. Configure target metadata from existing models.

### `backend/src/code_atlas/database.py` (New)
**`get_engine() -> Engine`**
Create SQLAlchemy engine from config. Use SQLite for local, PostgreSQL for production (future).

**`init_db() -> None`**
Initialize database with all tables. Run pending migrations on startup.

### `backend/alembic/versions/001_initial.py` (New)
Initial migration capturing current schema: jobs table, api_keys table. Mark as baseline.

### `Makefile` additions
```makefile
migrate:           # Run pending migrations
migrate-create:    # Create new migration
migrate-history:   # Show migration history
```

## Tests

| Test | Behavior |
|------|----------|
| `test_alembic_config_valid` | Can load alembic.ini |
| `test_migrations_up_down` | All migrations reversible |
| `test_init_db_creates_tables` | Tables created on fresh DB |

---

# Epic 4: Production Environment Configuration

## Problem
Same configuration used for dev/staging/prod. No environment detection or configuration switching.

## Files to Create/Change

| File | Action | Changes |
|------|--------|---------|
| `backend/src/code_atlas/config.py` | UPDATE | Add environment detection |
| `backend/.env.production.example` | CREATE | Production template |
| `docs/DEPLOYMENT.md` | UPDATE | Environment setup guide |

## Functions/Tasks

### `config.py:Environment` (New Enum)
```python
class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
```

### `config.py:Settings.environment` (New Field)
Detect environment from `CODE_ATLAS_ENV` variable. Default to development. Adjust settings based on environment (debug mode, log level, security strictness).

### `config.py:get_settings_for_environment()` (New)
Factory function returning environment-appropriate settings. Production: strict security, JSON logging, no debug. Development: relaxed CORS, console logging, debug enabled.

## Tests

| Test | Behavior |
|------|----------|
| `test_env_detection_from_variable` | CODE_ATLAS_ENV sets environment |
| `test_production_disables_debug` | debug=False in production |
| `test_development_enables_debug` | debug=True in development |

---

# Epic 5: Deployment Documentation

## Problem
Existing DEPLOYMENT.md is comprehensive but lacks Railway/Cloudflare specific steps.

## Files to Create/Change

| File | Action | Changes |
|------|--------|---------|
| `docs/DEPLOYMENT.md` | UPDATE | Add Railway/Cloudflare sections |
| `docs/RUNBOOK.md` | UPDATE | Add production troubleshooting |
| `README.md` | UPDATE | Quick deployment section |

## Documentation Sections

### DEPLOYMENT.md additions
1. **Railway Setup** - Project creation, service linking, env vars
2. **Cloudflare Pages Setup** - Project creation, build settings
3. **Domain Configuration** - DNS records, SSL certificates
4. **Secrets Management** - Where to store API keys
5. **Rollback Procedures** - How to revert deployments

### RUNBOOK.md additions
1. **Production Health Checks** - Endpoints to monitor
2. **Common Issues** - FalkorDB connection, rate limits
3. **Scaling Procedures** - When and how to scale
4. **Incident Response** - Alert handling, escalation

---

## Implementation Order

```
Epic 1: Railway Deployment           [CRITICAL - Backend Production]
    │
    ├── 1.1 Create railway.json
    ├── 1.2 Create railway.toml
    ├── 1.3 Fix Dockerfile
    └── 1.4 Add CD deploy job

Epic 2: Cloudflare Frontend          [CRITICAL - Frontend Production]
    │
    ├── 2.1 Create wrangler.toml
    ├── 2.2 Create .env.production
    ├── 2.3 Update vite.config.ts
    └── 2.4 Add CD deploy job

Epic 3: Database Migrations          [HIGH - Schema Safety]
    │
    ├── 3.1 Initialize Alembic
    ├── 3.2 Create database.py
    ├── 3.3 Create initial migration
    └── 3.4 Add Makefile commands

Epic 4: Environment Config           [MEDIUM - Operational Safety]
    │
    ├── 4.1 Add Environment enum
    ├── 4.2 Update Settings class
    └── 4.3 Create production template

Epic 5: Documentation                [MEDIUM - Operational Readiness]
    │
    ├── 5.1 Update DEPLOYMENT.md
    ├── 5.2 Update RUNBOOK.md
    └── 5.3 Update README.md
```

---

## Success Criteria

- [x] `railway.json` validates and Railway CLI accepts it
- [x] Backend deploys to Railway with working health check (config ready)
- [x] Frontend deploys to Cloudflare Pages with correct API URL (config ready)
- [x] Alembic can run migrations up and down
- [x] Environment detection works (dev/staging/prod)
- [x] DEPLOYMENT.md has Railway + Cloudflare sections
- [x] All existing tests still pass

---

## Effort Estimates

| Epic | Tasks | Estimate |
|------|-------|----------|
| Epic 1: Railway | 4 | 3h |
| Epic 2: Cloudflare | 4 | 2h |
| Epic 3: Migrations | 4 | 3h |
| Epic 4: Environment | 3 | 2h |
| Epic 5: Documentation | 3 | 2h |
| **Total** | **18** | **12h** |

---

## Dependencies

**Platform Accounts Required:**
- Railway account with project created
- Cloudflare account with Pages enabled
- GitHub secrets: `RAILWAY_TOKEN`, `CLOUDFLARE_API_TOKEN`

**Already Installed:**
- Docker, docker-compose
- GitHub Actions workflows
- Prometheus/Grafana monitoring stack

**To Install:**
- `alembic` - Database migrations
- Railway CLI (for local testing)
- Wrangler CLI (for local testing)

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Railway config mismatch | Medium | High | Test with Railway CLI locally first |
| Cloudflare build failures | Medium | Medium | Test build locally, check logs |
| Migration breaks existing data | Low | High | Backup before migration, test rollback |
| Env var misconfiguration | Medium | High | Document all required vars, validate on startup |
| DNS propagation delays | Low | Low | Plan deployment during low-traffic period |

---

## Post-Deployment Checklist

After Phase 5 completion:
- [ ] Health check endpoint responding
- [ ] API endpoints return correct responses
- [ ] Frontend loads and connects to API
- [ ] Prometheus metrics collecting
- [ ] Grafana dashboards accessible
- [ ] Error rates within acceptable range
- [ ] Response times within SLA (<200ms p95)

---

## Phase 4 Reference (Completed)

| Epic | Commit | Description |
|------|--------|-------------|
| Epic 1 | a460720 | feat(rag): integrate Anthropic LLM |
| Epic 2 | 1452f2a | feat(security): add security headers middleware |
| Epic 3 | a261b49 | feat(mcp): install SDK and update server |
| Epic 4 | 3d15cba | test(e2e): add RAG and Graph page tests |
| Docs | a23ad76 | docs: mark Phase 4 complete |

---

**Plan Created:** 2025-12-31
**Phase 5 Completed:** 2025-01-02

## Commits

| Epic | Commit | Description |
|------|--------|-------------|
| All | b22f85c | feat(deploy): add Railway and Cloudflare deployment configuration |
