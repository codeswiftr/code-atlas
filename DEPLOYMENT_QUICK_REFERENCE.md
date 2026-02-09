# Code Atlas Deployment - Quick Reference Card

**Task**: TD-005 | **Status**: Ready for Deployment | **Date**: 2026-02-08

---

## TL;DR

```bash
# 1. Make 5 decisions (see DEPLOYMENT_DECISIONS_REQUIRED.md)
# 2. Run these commands:

cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas
railway login
railway init
railway add postgresql redis
railway variables set DATABASE_URL='$RAILWAY_DATABASE_URL' \
  FALKORDB_HOST='$REDIS_HOST' \
  FALKORDB_PORT='6379' \
  CODE_ATLAS_ADMIN_API_KEY="$(openssl rand -hex 32)"
railway up
railway run alembic upgrade head

cd frontend
npm install && npm run build
npx wrangler pages deploy dist --project-name code-atlas

# 3. Test: curl https://<railway-url>/health
# 4. Run smoke tests: uv run pytest tests/e2e/test_smoke.py -v
```

**Time**: 2.5-4 hours | **Cost**: $17-32/month | **Risk**: Low

---

## File Navigator

| What You Need | File to Open |
|---------------|-------------|
| **I want to deploy right now** | `DEPLOY_NOW_QUICKSTART.md` |
| **I need detailed steps** | `DEPLOYMENT_RUNBOOK.md` |
| **I need to make decisions** | `DEPLOYMENT_DECISIONS_REQUIRED.md` |
| **I want comprehensive analysis** | `/Users/bogdan/work/FORGE/docs/deployments/CODE_ATLAS_DEPLOYMENT_REPORT.md` |
| **I want package summary** | `DEPLOYMENT_COMPLETE_PACKAGE.md` |
| **I want machine-readable state** | `/Users/bogdan/work/FORGE/.forge/deployments/code-atlas-deployment-status.json` |

---

## Decision Matrix (5 Decisions Required)

| # | Decision | Quick Choice | Full Choices |
|---|----------|--------------|--------------|
| 1 | FalkorDB Hosting | **A** | A=Railway Redis, B=External, C=SQLite, D=Self-host |
| 2 | LLM Mode | **Heuristic** | Heuristic=Free, LLM=$2/mo, Hybrid=Both |
| 3 | Domain | **Railway Default** | Default=Free, Subdomain=Custom, Separate=New |
| 4 | Monitoring | **Railway Only** | Railway=Free, +Sentry=Errors, +PostHog=Analytics |
| 5 | Rollout | **Soft Launch** | Soft=Internal, Beta=5-10 users, Public=Everyone, Defer=Later |

**Recommended Quick Start**: 1A, 2-Heuristic, 3-Default, 4-Railway, 5-Soft Launch

---

## Environment Variables

### Required (Must Set)
```bash
DATABASE_URL=<Railway auto-provides>
FALKORDB_HOST=<Railway Redis host>
FALKORDB_PORT=6379
```

### Recommended (Should Set)
```bash
CODE_ATLAS_ADMIN_API_KEY=<openssl rand -hex 32>
CORS_ORIGINS=https://<frontend-url>.pages.dev
MAX_COST_PER_SESSION_USD=0.02
MAX_CUMULATIVE_COST_USD=10.00
```

### Optional (Nice to Have)
```bash
ANTHROPIC_API_KEY=sk-ant-...  # If LLM mode
SENTRY_DSN=https://...        # If monitoring
```

---

## Deployment Phases

| Phase | Duration | Status | Key Command |
|-------|----------|--------|-------------|
| 1. Backend Setup | 1.5h | Not Started | `railway up` |
| 2. Frontend Setup | 1h | Not Started | `npx wrangler pages deploy dist` |
| 3. Smoke Tests | 1h | Not Started | `pytest tests/e2e/test_smoke.py -v` |
| 4. Documentation | 0.5h | Not Started | Update README + INFRASTRUCTURE_MAP.md |

**Total**: 2.5-4 hours depending on decisions

---

## Success Criteria Checklist

### Technical (Must Pass All)
- [ ] `curl https://<railway-url>/health` returns 200
- [ ] Frontend loads at `https://<pages-url>` without errors
- [ ] `falkordb_connected: true` in health response
- [ ] All 18 smoke tests pass
- [ ] API docs accessible at `/docs`
- [ ] CORS configured (no browser errors)
- [ ] Migrations applied (no DB errors in logs)

### Business (Validate Within 24h)
- [ ] CL-001 active (pattern discovery working)
- [ ] Cost tracking shows $0 (if heuristic mode)
- [ ] Can extract entities from sample session
- [ ] Can query knowledge graph
- [ ] Vector search returns results

---

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| Railway Backend (Hobby) | $15-20 |
| PostgreSQL (Railway) | Included |
| Redis (Railway) | Included |
| Cloudflare Pages | $0 |
| FalkorDB Hosting | $0-10 |
| LLM API (optional) | $0-2 |
| **TOTAL** | **$17-32** |

---

## Common Issues & Fixes

| Issue | Quick Fix |
|-------|-----------|
| Health check fails | Check Railway logs: `railway logs --tail` |
| FalkorDB not connected | Verify Redis module: `railway run redis-cli MODULE LIST` |
| CORS errors | Update: `railway variables set CORS_ORIGINS=<frontend-url>` |
| Migrations fail | Run manually: `railway run alembic upgrade head` |
| Frontend 404 | Check API URL in `.env.production` |

---

## Rollback Procedure

```bash
# Backend rollback (30 seconds)
railway rollback

# Frontend rollback (30 seconds)
npx wrangler pages deployment list --project-name code-atlas
npx wrangler pages deployment rollback <previous-deployment-id>
```

**Total Rollback Time**: 5 minutes

---

## Production URLs (Fill After Deployment)

```
Backend API: https://_____________________.railway.app
Frontend UI: https://_____________________.pages.dev
API Docs: https://_____________________.railway.app/docs
Health Check: https://_____________________.railway.app/health
Admin API Key: _________________________________ (stored in Railway secrets)
```

---

## Key Commands Reference

```bash
# Railway
railway login                          # Authenticate
railway init                           # Create/link project
railway add <service>                  # Add PostgreSQL, Redis, etc.
railway variables set KEY=value        # Set env var
railway up                             # Deploy
railway logs --tail                    # View logs
railway status                         # Check status
railway rollback                       # Rollback
railway run <command>                  # Run command in Railway env

# Cloudflare Pages
npx wrangler login                     # Authenticate
npx wrangler pages deploy dist         # Deploy frontend
npx wrangler pages deployment list     # List deployments
npx wrangler pages deployment rollback # Rollback

# Testing
uv run pytest tests/e2e/test_smoke.py -v  # Run smoke tests
curl https://<url>/health                  # Test health
```

---

## Compounding Loops to Verify

1. **CL-001** (Primary): Pattern Discovery → Reuse
   - Extract patterns → Query patterns → Search returns patterns
   - **Test**: `curl -X POST <url>/api/v1/extract` then `curl <url>/api/v1/patterns`

2. **CL-002**: Vector Search → Better Queries
   - Monitor search quality over time
   - **Test**: Compare search results before/after extracting 10+ sessions

3. **CL-003**: Knowledge Graph → Insights
   - Graph reveals entity relationships
   - **Test**: Query graph after extracting 10+ sessions

---

## Post-Deployment Tasks

**Day 1**:
- [ ] Monitor logs for 24h
- [ ] Test all critical flows
- [ ] Document production URLs

**Week 1**:
- [ ] Invite beta testers (if applicable)
- [ ] Gather feedback
- [ ] Monitor performance

**Month 1**:
- [ ] Analyze compounding loops
- [ ] Add custom domain (if not initial)
- [ ] Enable LLM mode (if not initial)

---

## Support Resources

| Need Help With | Look Here |
|----------------|-----------|
| Step-by-step deployment | `DEPLOYMENT_RUNBOOK.md` |
| Quick copy-paste commands | `DEPLOY_NOW_QUICKSTART.md` |
| Making decisions | `DEPLOYMENT_DECISIONS_REQUIRED.md` |
| Technical deep-dive | `CODE_ATLAS_DEPLOYMENT_REPORT.md` |
| Package overview | `DEPLOYMENT_COMPLETE_PACKAGE.md` |
| Railway docs | https://docs.railway.app |
| Cloudflare Pages docs | https://developers.cloudflare.com/pages |

---

## Status Tracking

**Current Status**: 🟡 Ready for Deployment (Awaiting Decisions)

**Progress**:
- [x] Infrastructure configs created
- [x] Tests written (6,935 lines)
- [x] Deployment documentation complete
- [ ] Decisions made (5 needed)
- [ ] Deployment executed
- [ ] Smoke tests passed
- [ ] Production URLs documented
- [ ] Compounding loops verified

**Next Action**: Make 5 decisions, then execute deployment

---

## Contact

**Prepared By**: The Deployer Agent
**Task**: TD-005
**Date**: 2026-02-08
**Time to Deploy**: 2.5-4 hours (after decisions)
**Confidence**: 95%

**All files saved in**: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/`

🚀 **Ready when you are!**
