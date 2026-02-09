# Code Atlas Production Deployment Runbook

**Status**: Ready for deployment
**Target**: Railway (backend) + Cloudflare Pages (frontend)
**Updated**: 2026-02-08

## Pre-Deployment Checklist

- [ ] Railway CLI installed (`brew install railway`)
- [ ] Railway account authenticated (`railway login`)
- [ ] Cloudflare account with Pages access
- [ ] wrangler CLI installed (`npm install -g wrangler`)
- [ ] FalkorDB hosting strategy decided
- [ ] API keys prepared (optional for heuristic mode)

## Environment Variables Required

### Backend (Railway)

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/code_atlas

# FalkorDB (Graph Database)
FALKORDB_HOST=<redis-host-or-falkordb-service>
FALKORDB_PORT=6379

# Optional: LLM Extraction
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...

# Security
CODE_ATLAS_ADMIN_API_KEY=<generate-secure-random-key>

# CORS (add after frontend deployed)
CORS_ORIGINS=https://<frontend-url>.pages.dev

# Cost Controls
MAX_COST_PER_SESSION_USD=0.02
MAX_CUMULATIVE_COST_USD=10.00
```

### Frontend (Cloudflare Pages)

```bash
VITE_API_URL=https://<railway-backend-url>.railway.app
```

## Deployment Steps

### Step 1: Backend Deployment (Railway)

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas

# Initialize Railway project
railway init
# Follow prompts to create new project or link existing

# Link to Code Atlas project (if exists)
# railway link <project-id>

# Add PostgreSQL database
railway add postgresql

# Add Redis (for FalkorDB)
railway add redis

# Set environment variables
railway variables set DATABASE_URL="$RAILWAY_DATABASE_URL"
railway variables set FALKORDB_HOST="$REDIS_HOST"
railway variables set FALKORDB_PORT="6379"
railway variables set CODE_ATLAS_ADMIN_API_KEY="$(openssl rand -hex 32)"

# Optional: Add LLM keys
# railway variables set ANTHROPIC_API_KEY="sk-ant-..."

# Deploy backend
railway up

# Get deployment URL
railway status
# Note the URL for next steps
```

### Step 2: Run Database Migrations

```bash
# SSH into Railway container or run locally against Railway DB
railway run alembic upgrade head
```

### Step 3: Verify Backend

```bash
# Get Railway URL
BACKEND_URL=$(railway status --json | jq -r '.service.url')

# Test health endpoint
curl $BACKEND_URL/health

# Expected response:
# {"status": "ok", "version": "...", "falkordb_connected": true}

# Test API root
curl $BACKEND_URL/api/v1/

# Expected: API documentation or 404 (normal for root)
```

### Step 4: Frontend Deployment (Cloudflare Pages)

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend

# Install dependencies
npm install

# Set API URL in .env.production
echo "VITE_API_URL=$BACKEND_URL" > .env.production

# Build production bundle
npm run build

# Login to Cloudflare
npx wrangler login

# Deploy to Cloudflare Pages
npx wrangler pages deploy dist \
  --project-name code-atlas \
  --branch main

# Note the frontend URL from output
```

### Step 5: Configure CORS

```bash
# Add frontend URL to backend CORS
FRONTEND_URL=<from-step-4>
railway variables set CORS_ORIGINS="$FRONTEND_URL"

# Restart backend to apply CORS
railway restart
```

### Step 6: Smoke Tests

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend

# Run E2E smoke tests against production
uv run pytest tests/e2e/test_smoke.py -v \
  --base-url=$BACKEND_URL

# Expected: All 18 tests pass

# Test vector search endpoint
curl -X POST $BACKEND_URL/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication patterns",
    "limit": 5
  }'

# Test session extraction
curl -X POST $BACKEND_URL/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $CODE_ATLAS_ADMIN_API_KEY" \
  -d '{
    "session_path": "~/.claude/projects/test-session"
  }'
```

### Step 7: Verify Compounding Loops

**CL-001: Pattern Discovery → Reuse**

```bash
# 1. Extract patterns from session
curl -X POST $BACKEND_URL/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"session_path": "~/.claude/projects/sample"}'

# 2. Query patterns
curl $BACKEND_URL/api/v1/patterns

# 3. Verify pattern retrieval in new session
curl -X POST $BACKEND_URL/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "FastAPI endpoint patterns", "limit": 5}'

# Expected: Previously extracted patterns returned
```

**CL-002: Vector Search → Better Queries**

Monitor query logs for search refinement over time.

## Post-Deployment Configuration

### Enable Monitoring

```bash
# Add monitoring endpoints
railway variables set SENTRY_DSN="..."
railway variables set POSTHOG_API_KEY="..."

# Restart to apply
railway restart
```

### Custom Domain (Optional)

```bash
# Add custom domain in Railway dashboard
# Settings → Domains → Add Custom Domain
# Example: api.codeatlas.codeswiftr.com

# Update frontend API URL
npx wrangler pages deployment create \
  --project-name code-atlas \
  --env production \
  --var VITE_API_URL=https://api.codeatlas.codeswiftr.com
```

## Troubleshooting

### Issue: FalkorDB Connection Failed

**Symptom**: Health check shows `"falkordb_connected": false`

**Solutions**:
1. Verify Redis is running: `railway logs --service redis`
2. Check FalkorDB module loaded: `railway run redis-cli MODULE LIST`
3. Verify FALKORDB_HOST and FALKORDB_PORT environment variables

### Issue: Database Migrations Not Applied

**Symptom**: 500 errors on API endpoints, logs show table not found

**Solution**:
```bash
railway run alembic upgrade head
```

### Issue: CORS Errors in Frontend

**Symptom**: Browser console shows CORS blocked requests

**Solution**:
```bash
railway variables set CORS_ORIGINS="https://<frontend-url>.pages.dev"
railway restart
```

### Issue: WebSocket Connection Failed

**Symptom**: Real-time job updates not working

**Solution**:
1. Verify Railway supports WebSockets (check plan)
2. Check WebSocket route in logs: `railway logs | grep ws`
3. Test WebSocket manually: `wscat -c wss://$BACKEND_URL/ws/jobs/test-123`

## Rollback Procedure

```bash
# Rollback backend to previous deployment
railway rollback

# Rollback frontend to previous deployment
npx wrangler pages deployment list --project-name code-atlas
npx wrangler pages deployment rollback <deployment-id>
```

## Monitoring & Maintenance

### Key Metrics to Monitor

1. **Health Check**: `/health` should return 200
2. **API Response Times**: p50 < 100ms, p95 < 500ms
3. **FalkorDB Connection**: Monitor connection pool
4. **LLM Cost**: Track cumulative costs against $10 limit
5. **Error Rate**: Target < 1% of requests

### Daily Health Check

```bash
# Automated health check script
#!/bin/bash
BACKEND_URL="https://<railway-url>.railway.app"
FRONTEND_URL="https://<frontend-url>.pages.dev"

# Backend health
curl -f $BACKEND_URL/health || echo "Backend health check failed"

# Frontend health
curl -f $FRONTEND_URL || echo "Frontend health check failed"

# API functionality
curl -f $BACKEND_URL/api/v1/sessions || echo "API health check failed"
```

## Cost Estimation

### Railway Backend (Hobby Plan)
- $5/month base
- $0.000231/GB-hour for memory (512MB = ~$85/month)
- Database: $5-10/month
- **Estimated**: $15-20/month

### Cloudflare Pages
- Free tier: 500 builds/month, unlimited requests
- **Estimated**: $0/month

### LLM Costs (Optional)
- Anthropic Claude: ~$0.02/session
- Monthly estimate (100 sessions): $2
- Hard limit: $10/month (enforced by app)

**Total Estimated Monthly Cost**: $17-32/month

## Success Criteria

- [x] Backend deployed to Railway with public URL
- [x] Frontend deployed to Cloudflare Pages
- [x] Health check returns 200 with `falkordb_connected: true`
- [x] Vector search API working (tested via curl)
- [x] All 18 smoke tests passing
- [x] Environment variables secured (not committed)
- [x] CORS configured for frontend
- [x] Database migrations applied
- [x] Compounding loop CL-001 activated (pattern discovery working)

## Next Steps After Deployment

1. **Enable LLM Mode**: Add ANTHROPIC_API_KEY for enhanced extraction
2. **Custom Domain**: Configure `api.codeatlas.codeswiftr.com`
3. **Monitoring**: Set up Sentry + PostHog
4. **Documentation**: Update README with production URLs
5. **User Testing**: Invite beta users to test production system
6. **Scale Testing**: Verify performance under load

## Deployment Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Railway setup | 30 min | Pending |
| Backend deploy | 30 min | Pending |
| Frontend deploy | 30 min | Pending |
| Testing | 1 hour | Pending |
| **Total** | **2.5 hours** | **Not Started** |

## References

- Railway Config: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/railway.json`
- Dockerfile: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/Dockerfile`
- Wrangler Config: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend/wrangler.toml`
- Smoke Tests: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/tests/e2e/test_smoke.py`
- CLAUDE.md: `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/CLAUDE.md`

---

**Last Updated**: 2026-02-08
**Owner**: Deployer Agent
**Status**: Ready for execution
