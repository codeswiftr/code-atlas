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
- ✅ Comprehensive codebase audit completed (see `docs/CODEBASE_AUDIT.md`)

### Phase 2.5 Quality & Testing (COMPLETE)
- ✅ Task 2.5.1: Frontend test failures fixed (66/66 tests passing)
- ✅ Task 2.5.2: Insights API tests verified (23 tests passing)
- ✅ Task 2.5.3: Graph Query component tests verified (44 tests passing)
- ✅ Task 2.5.4: API key management documented (MVP-ready)
- ✅ Task 2.5.5: E2E test framework set up (Playwright configured)

### Current Focus
Phase 3: Production readiness and documentation

### Blockers/Issues
- 🟢 All critical blockers resolved
- 🟡 ESLint has 2 errors (empty interfaces in types/api.ts), 23 warnings (mostly `any` types)

---

## Test Coverage Summary

| Area | Tests | Status |
|------|-------|--------|
| Backend (pytest) | 289 tests | ✅ All passing |
| Frontend (vitest) | 66 tests | ✅ All passing |
| Insights API | 23 tests | ✅ All passing |
| Graph Query Components | 44 tests | ✅ All passing |
| E2E (Playwright) | 11 tests | ✅ Framework ready |

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
| `frontend/e2e/navigation.spec.ts` | E2E tests for critical user journeys |
| `backend/src/code_atlas/server.py` | FastAPI server entry point |
| `backend/src/code_atlas/api/v1/insights.py` | Insights API endpoints |
| `docs/CODEBASE_AUDIT.md` | Comprehensive codebase audit with test gap analysis |
| `docs/PLAN.md` | Overall implementation plan |

### Recent Decisions
- **Code splitting via lazy()**: Improves initial load time, separate chunks per page
- **Nested error boundaries**: One around entire app, one around routes for isolation
- **30-second connection polling**: Balance between responsiveness and overhead
- **Removed d3/cytoscape**: Unused dependencies causing build issues
- **Playwright for E2E**: Lightweight, single-browser setup for CI

### Gotchas Discovered
- ⚠️ TypeScript 4.9.x does NOT support `moduleResolution: "bundler"` - use `"node"`
- ⚠️ Vitest mocks need to be declared before `vi.mock()` for hoisting to work
- ⚠️ `lucide-react` doesn't export `Tool` icon - use `Wrench` instead
- ⚠️ Frontend `node_modules` was accidentally committed - now in .gitignore
- ⚠️ Test utils file must be `.tsx` for JSX syntax support

### Patterns to Follow
- **React Query**: Use for all API calls with proper query keys
- **Error handling**: Wrap components with ErrorBoundary, use try/catch in async
- **Tailwind classes**: Use `atlas-*` custom colors defined in tokens.css
- **Testing**: API client tests use global fetch mock, page tests need QueryClient wrapper
- **E2E Testing**: Use Playwright with `npm run test:e2e`

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
# Backend (289 tests)
cd backend && uv run pytest -v

# Frontend unit tests (66 tests)
cd frontend && npm test -- --run

# Frontend E2E tests (11 tests)
cd frontend && npm run test:e2e
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
│   └── tests/               # 289 pytest tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Root with routing
│   │   ├── api/client.ts    # API client
│   │   ├── components/      # React components
│   │   ├── pages/           # Route pages
│   │   └── test/setup.ts    # Test setup
│   ├── e2e/                 # Playwright E2E tests
│   └── dist/                # Built output
└── docs/
    ├── PLAN.md              # Implementation plan
    ├── SOFT_LAUNCH_REVIEW.md # Review report
    ├── CODEBASE_AUDIT.md    # Comprehensive codebase audit
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
Read docs/PROMPT.md, verify all tests pass, then identify next priorities for Phase 3.
DO NOT STOP! Continue with the plan like an empowered, pragmatic senior engineer.
```
