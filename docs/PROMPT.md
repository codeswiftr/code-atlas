# Agent Continuation Prompt

## Project Overview
**Project**: Code Atlas
**Purpose**: Transform Claude Code sessions into a searchable knowledge graph for developer insights
**Tech Stack**: Python 3.11+ (FastAPI, FalkorDB, Anthropic), React 18 (TypeScript, Vite, TailwindCSS)
**Repository**: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas`

---

## Current State

### Branch
`main` - Production branch with all P0/P1/P2 improvements merged

### Recent Progress
- ✅ Soft Launch Review completed - Frontend ready for GA
- ✅ P0 fixes: TypeScript config, ESLint setup, unused dependencies removed
- ✅ P1-1: Test infrastructure (tsconfig.test.json, vitest.config.ts, setup.ts)
- ✅ P1-2: Error boundaries with retry functionality
- ✅ P1-3: Dynamic connection status (polls every 30s)
- ✅ P1-4: Home page stats connected to API
- ✅ P1-5: Code splitting with React.lazy() (bundle 530KB → 469KB)
- ✅ P2 features: Export button, job cancellation UI, ARIA labels
- ✅ Phase 2.2-2.5: Graph Query UI, Insights Dashboard, Monitoring, UX improvements
- ✅ Backend: 266 tests passing across 17 test files (82% coverage)
- ✅ Comprehensive codebase audit completed (see `docs/CODEBASE_AUDIT.md`)

### Current Focus
Phase 2.5: Quality & Testing improvements - addressing critical test gaps

### Blockers/Issues
- 🔴 **8/22 frontend tests failing** (Sessions.test.tsx - mock hoisting, test expectations)
- 🔴 **Insights API 0% test coverage** (6 endpoints untested)
- 🟡 **Graph Query UI 0% test coverage** (new feature)
- 🟡 **API key management TODO** in dependencies.py:60
- 🟢 ESLint has 2 errors (empty interfaces in types/api.ts), 23 warnings (mostly `any` types)

---

## Active Plan
**Plan File**: `docs/PLAN.md`
**Current Phase**: Phase 2.5 - Quality & Testing
**Current Task**: Address critical test coverage gaps
**Status**: 95% complete, test hardening in progress

### Immediate Next Steps (Phase 2.5 - Sprint 1)
1. **🔴 P0**: Fix frontend test failures (8/22 failing) - 2-3h
   - Fix `renderWithQueryClient` export in test utils
   - Update test expectations to match component behavior
2. **🔴 P0**: Add Insights API tests (0% → 80%) - 4-6h
   - 6 endpoints need unit tests
   - File: `backend/tests/test_insights_api.py`
3. **🟡 P1**: Add Graph Query component tests - 3-4h
   - QueryBuilder, QueryResults components
4. **🟡 P1**: Complete API key manager integration - 2-3h
   - Replace TODO with full validation
5. **🟡 P1**: Set up E2E test framework - 8-12h
   - Playwright for critical user journeys

---

## Key Context

### Important Files
| File | Purpose |
|------|---------|
| `frontend/src/App.tsx` | Root app with routing, error boundaries, lazy loading |
| `frontend/src/components/error/ErrorBoundary.tsx` | Error handling component |
| `frontend/src/components/layout/Layout.tsx` | Main layout with dynamic connection status |
| `frontend/src/pages/Home.tsx` | Landing page with API-connected stats |
| `frontend/src/pages/Graph.tsx` | Graph visualization with Query UI |
| `frontend/src/pages/Insights.tsx` | Insights dashboard |
| `frontend/src/api/client.ts` | API client class |
| `backend/src/code_atlas/server.py` | FastAPI server entry point |
| `backend/src/code_atlas/api/v1/insights.py` | Insights API endpoints (0% test coverage) |
| `docs/CODEBASE_AUDIT.md` | Comprehensive codebase audit with test gap analysis |
| `docs/PLAN.md` | Overall implementation plan with Phase 2.5 details |

### Recent Decisions
- **Code splitting via lazy()**: Improves initial load time, separate chunks per page
- **Nested error boundaries**: One around entire app, one around routes for isolation
- **30-second connection polling**: Balance between responsiveness and overhead
- **Removed d3/cytoscape**: Unused dependencies causing build issues

### Gotchas Discovered
- ⚠️ TypeScript 4.9.x does NOT support `moduleResolution: "bundler"` - use `"node"`
- ⚠️ Vitest mocks need to be declared before `vi.mock()` for hoisting to work
- ⚠️ `lucide-react` doesn't export `Tool` icon - use `Wrench` instead
- ⚠️ Frontend `node_modules` was accidentally committed - now in .gitignore

### Patterns to Follow
- **React Query**: Use for all API calls with proper query keys
- **Error handling**: Wrap components with ErrorBoundary, use try/catch in async
- **Tailwind classes**: Use `atlas-*` custom colors defined in tokens.css
- **Testing**: API client tests use global fetch mock, page tests need QueryClient wrapper

### Things to Avoid
- ❌ Don't commit `frontend/node_modules/` - it's gitignored
- ❌ Don't use TypeScript 5+ features (project uses 4.9.x)
- ❌ Don't use `import.meta.env.DEV` without Vite types configured
- ❌ Don't use d3/cytoscape - Graph page uses custom force simulation

---

## Commands to Run

### Verify Environment
```bash
# Backend
cd backend && uv run pytest --co -q

# Frontend
cd frontend && npm run build
```

### Run Tests
```bash
# Backend (266 tests, 82% coverage)
cd backend && uv run pytest -v

# Frontend (14/22 passing - 8 failing in Sessions.test.tsx)
cd frontend && npm test -- --run
```

### Start Development
```bash
# Backend server
cd backend && uv run python -m code_atlas.server

# Frontend dev server
cd frontend && npm run dev
```

---

## Project Structure

```
code-atlas/
├── backend/
│   ├── src/code_atlas/      # Python source
│   │   ├── server.py        # FastAPI endpoints
│   │   ├── pipeline.py      # Processing pipeline
│   │   ├── graph_*.py       # Graph operations
│   │   └── models.py        # Data models
│   └── tests/               # 263 pytest tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Root with routing
│   │   ├── api/client.ts    # API client
│   │   ├── components/      # React components
│   │   ├── pages/           # Route pages
│   │   └── test/setup.ts    # Test setup
│   └── dist/                # Built output
└── docs/
    ├── PLAN.md              # Implementation plan
    ├── SOFT_LAUNCH_REVIEW.md # Review report
    ├── CODEBASE_AUDIT.md    # Comprehensive codebase audit (2025-01-30)
    └── PROMPT.md            # This file
```

---

## Instructions for New Agent

### Mindset
You are a pragmatic senior engineer completing GA preparation. Your approach:
- Apply Pareto principle - 20% effort for 80% value
- Test-driven development for business logic
- YAGNI - don't build what isn't needed
- Clean architecture with clear separation

### Workflow
1. Read this context and the plan file
2. Run tests to verify current state
3. Continue from the current task
4. Commit after each completed task
5. Update plan status as you progress

### Quality Gates
After each change:
1. Run affected tests
2. Ensure no regressions
3. Commit with conventional message
4. Continue to next task

### If Stuck
- Use `/debug` for complex issues
- Use `/feedback` to review approach
- Check related tests for expected behavior
- Ask for clarification if requirements unclear

---

## Resume Command

To continue work, start with:
```
Read docs/PROMPT.md and docs/CODEBASE_AUDIT.md, verify build passes, then address Phase 2.5 test coverage gaps (frontend tests, Insights API tests).
DO NOT STOP! Continue with the plan like an empowered, pragmatic senior engineer.
```
