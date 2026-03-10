# Code Atlas — Operator MVP Spec

**Status:** DRAFT
**Created:** 2026-03-10 (S113)
**Goal:** Narrow Code Atlas to ONE paid workflow

---

## Current State

Code Atlas is a comprehensive session intelligence tool with:
- GraphRAG for Q&A over session history
- MCP integration for Claude Desktop
- `/sessions/report` endpoint — generates project intelligence reports
- 90+ tests passing
- Deploy configs ready (Railway + Cloudflare Pages)

**Problem:** Too many features, no clear paid product. The "Swiss Army knife" approach doesn't sell.

---

## The ONE Workflow

**Paid workflow:** `POST /api/v1/sessions/report`

**What it does:**
- Takes a `project_path` (path to Claude Code session files)
- Analyzes all `.jsonl` sessions in that directory
- Returns: `top_files`, `top_entities`, `key_insights`, `summary`, `cost_usd`

**Value proposition:**
> "Turn your Claude Code session history into actionable project intelligence in seconds."

**Target customer:**
- Teams using Claude Code on large codebases
- Need to understand what was discussed/decided across sessions
- Want onboarding intelligence for new team members

---

## What To Build

### 1. Public API Surface (1 day)

| Endpoint | Purpose |
|----------|---------|
| `POST /sessions/report` | Core intelligence report (exists) |
| `GET /health` | Health check (exists) |
| `POST /auth/api-keys` | Create API key (exists) |

**Changes needed:**
- [ ] Add rate limiting per API key (10 reports/day free tier, 100/day paid)
- [ ] Add usage tracking to database
- [ ] Add `X-API-Key` header validation (currently has auth but needs polish)

### 2. Billing Layer (1 day)

| Component | Implementation |
|-----------|---------------|
| Stripe checkout | `POST /billing/checkout` → Stripe session |
| Webhook handler | `POST /billing/webhook` → update subscription |
| Tier enforcement | Free=10/day, Pro=$29/mo=100/day, Team=$99/mo=1000/day |

**Dependencies:**
- `stripe` Python package (add to pyproject.toml)
- Stripe keys in Railway (human gate: Bogdan)

### 3. Landing Page (1 day)

**Route:** `/` (replace current dashboard with public landing)

**Sections:**
1. Hero: "Session Intelligence for Claude Code"
2. Demo: Input project path → Show sample report
3. Pricing: Free / Pro / Team tiers
4. CTA: "Get API Key" → Stripe checkout

**Implementation:**
- New `frontend/src/pages/Landing.tsx`
- Replace authenticated dashboard with `/dashboard` route
- Add marketing copy

### 4. Usage Dashboard (0.5 day)

**Route:** `/dashboard`

**Shows:**
- API key management
- Reports generated this month
- Subscription status
- Billing history

---

## What To Cut (Defer)

| Feature | Reason |
|---------|--------|
| GraphRAG Q&A | Not the paid workflow — could be upsell later |
| MCP integration | Internal value, not external packaging |
| Graph visualization | Cool but not essential for reports |
| Real-time WebSocket | Not needed for batch reports |

---

## Migration Path

### Phase 1: Polish Core (this session)
1. Add rate limiting per API key
2. Add usage tracking table
3. Write Stripe billing scaffold

### Phase 2: Landing + Billing (next session)
1. Build landing page
2. Wire Stripe checkout
3. Test end-to-end flow

### Phase 3: Launch (human gate)
1. Deploy to Railway
2. Add Stripe production keys
3. Announce on LinkedIn

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Reports generated | 100/week |
| Paid conversions | 5/month |
| API response time | <500ms p95 |
| Support tickets | <5/month |

---

## Files To Change

| File | Change |
|------|--------|
| `backend/src/code_atlas/api/routes/billing.py` | NEW — Stripe checkout/webhook |
| `backend/src/code_atlas/middleware/rate_limit.py` | NEW — per-key rate limiting |
| `backend/src/code_atlas/models/usage.py` | NEW — usage tracking |
| `frontend/src/pages/Landing.tsx` | NEW — public landing |
| `frontend/src/pages/Dashboard.tsx` | UPDATE — move here from `/` |
| `backend/pyproject.toml` | ADD — stripe package |

---

## Human Gates

| Gate | Owner | Blocks |
|------|-------|--------|
| Stripe production keys | Bogdan | Paid subscriptions |
| Railway deploy | Bogdan | Public access |
| Domain DNS | Bogdan | Custom domain |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Low demand | Medium | Free tier allows validation before paid push |
| Stripe integration bugs | Low | Webhook testing with Stripe CLI |
| API abuse | Medium | Rate limiting + API key validation |
| FalkorDB connection issues | Low | Railway managed Redis with FalkorDB module |

---

## Estimated Effort

| Phase | Time |
|-------|------|
| Phase 1: Core polish | 1 day |
| Phase 2: Landing + Billing | 1 day |
| Phase 3: Launch (human) | 0.5 day |
| **Total** | **2.5 days** |

---

## Next Immediate Action

Add rate limiting middleware to `/sessions/report` endpoint with per-API-key tracking.

```python
# backend/src/code_atlas/middleware/rate_limit.py
class RateLimitMiddleware:
    def __init__(self, app, limits: dict[str, int]):
        # limits = {"free": 10, "pro": 100, "team": 1000}
        ...

    async def __call__(self, request, call_next):
        api_key = request.headers.get("X-API-Key")
        tier = await self.get_tier(api_key)
        if await self.is_over_limit(api_key, tier):
            return JSONResponse({"error": "Rate limit exceeded"}, 429)
        return await call_next(request)
```
