# Code Atlas - Deploy Now Quickstart

**For the impatient**: Copy-paste these commands to deploy Code Atlas in under 3 hours.

**Prerequisites**: Railway account, Railway CLI installed (`brew install railway`)

---

## Option 1: Minimal Deployment (2.5 hours, $17/month)

**Good for**: Internal testing, validation, immediate deployment

### Step 1: Backend Setup (45 minutes)

```bash
# Navigate to project
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas

# Login to Railway
railway login

# Initialize project
railway init
# Follow prompts, choose "Create new project", name it "code-atlas"

# Add services
railway add postgresql
railway add redis

# Set environment variables
railway variables set DATABASE_URL='$RAILWAY_DATABASE_URL'
railway variables set FALKORDB_HOST='$REDIS_HOST'
railway variables set FALKORDB_PORT='6379'
railway variables set CODE_ATLAS_ADMIN_API_KEY="$(openssl rand -hex 32)"
railway variables set MAX_COST_PER_SESSION_USD='0.02'
railway variables set MAX_CUMULATIVE_COST_USD='10.00'
railway variables set USE_LLM='false'  # Heuristic mode

# Deploy
railway up

# Wait for deployment (2-3 minutes)
railway status

# Run migrations
railway run alembic upgrade head

# Get your backend URL
BACKEND_URL=$(railway status --json | jq -r '.serviceInstances[0].domains[0].domain')
echo "Backend URL: https://$BACKEND_URL"

# Test health check
curl https://$BACKEND_URL/health
```

**Expected Output**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "falkordb_connected": true,
  "database_connected": true
}
```

### Step 2: Frontend Setup (30 minutes)

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend

# Install dependencies
npm install

# Set API URL
echo "VITE_API_URL=https://$BACKEND_URL" > .env.production

# Build
npm run build

# Login to Cloudflare
npx wrangler login

# Deploy
npx wrangler pages deploy dist \
  --project-name code-atlas \
  --branch main

# Note the frontend URL from output
# Example: https://code-atlas-xyz.pages.dev
```

### Step 3: Configure CORS (5 minutes)

```bash
# Get frontend URL from previous step
FRONTEND_URL="https://code-atlas-xyz.pages.dev"  # Replace with your URL

# Add to backend CORS
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas
railway variables set CORS_ORIGINS="$FRONTEND_URL"

# Restart backend
railway restart
```

### Step 4: Smoke Tests (30 minutes)

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend

# Run E2E tests against production
uv run pytest tests/e2e/test_smoke.py -v \
  --base-url=https://$BACKEND_URL

# Expected: All 18 tests pass

# Test API manually
curl -X POST https://$BACKEND_URL/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication patterns",
    "limit": 5
  }'

# Expected: JSON response with search results

# Test frontend
open $FRONTEND_URL
# Verify page loads, no console errors
```

### Step 5: Verify Compounding Loop (15 minutes)

```bash
# Test CL-001: Pattern Discovery → Reuse
ADMIN_KEY=$(railway variables get CODE_ATLAS_ADMIN_API_KEY)

# 1. Extract patterns from sample session
curl -X POST https://$BACKEND_URL/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{
    "session_path": "~/.claude/projects/test-session"
  }'

# 2. Query patterns
curl https://$BACKEND_URL/api/v1/patterns

# 3. Search for patterns
curl -X POST https://$BACKEND_URL/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "FastAPI patterns",
    "limit": 5
  }'

# If patterns returned from previous extraction → CL-001 ACTIVE ✅
```

### Done! 🎉

**Production URLs**:
- Backend: `https://$BACKEND_URL`
- Frontend: `$FRONTEND_URL`
- API Docs: `https://$BACKEND_URL/docs`

**Cost**: ~$17/month (Railway Hobby + PostgreSQL + Redis)

---

## Option 2: Optimal Deployment (4 hours, $27/month)

**Good for**: Public beta, professional setup, LLM-enabled

### Additional Steps Beyond Option 1:

#### A. Enable LLM Mode

```bash
# Add Anthropic API key
railway variables set ANTHROPIC_API_KEY="sk-ant-your-key-here"
railway variables set USE_LLM="true"

# Restart
railway restart
```

#### B. Custom Domain

```bash
# In Railway dashboard:
# 1. Settings → Domains → Add Custom Domain
# 2. Enter: api.codeatlas.codeswiftr.com
# 3. Add CNAME record in Cloudflare DNS:
#    api.codeatlas.codeswiftr.com → <railway-domain>

# Wait for SSL provisioning (5-10 minutes)

# Update frontend
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend
echo "VITE_API_URL=https://api.codeatlas.codeswiftr.com" > .env.production
npm run build
npx wrangler pages deploy dist --project-name code-atlas

# Update CORS
railway variables set CORS_ORIGINS="https://codeatlas.codeswiftr.com"

# Deploy frontend to custom domain
npx wrangler pages deploy dist \
  --project-name code-atlas \
  --branch main \
  --commit-message "Production deploy with custom domain"

# In Cloudflare Pages dashboard:
# 1. Go to code-atlas project
# 2. Custom Domains → Add domain
# 3. Enter: codeatlas.codeswiftr.com
```

#### C. Add Sentry Monitoring

```bash
# Sign up at sentry.io (free tier)
# Get DSN from project settings

railway variables set SENTRY_DSN="https://xxx@sentry.io/xxx"
railway restart
```

**Cost**: ~$27/month (Railway + LLM usage)

---

## Troubleshooting

### Issue: Health check fails with `falkordb_connected: false`

**Solution**:
```bash
# Check if Redis is running
railway logs --service redis

# Verify FalkorDB module loaded
railway run redis-cli MODULE LIST
# Should show FalkorDB in list

# If module not loaded, check Railway Redis version
# May need to use external FalkorDB service
```

### Issue: CORS errors in browser

**Solution**:
```bash
# Verify CORS_ORIGINS matches frontend URL
railway variables get CORS_ORIGINS

# Update if needed
railway variables set CORS_ORIGINS="https://your-frontend-url.pages.dev"
railway restart
```

### Issue: Alembic migrations fail

**Solution**:
```bash
# Check database connection
railway run python -c "from sqlalchemy import create_engine; engine = create_engine('$DATABASE_URL'); print(engine.connect())"

# Run migrations with verbose output
railway run alembic upgrade head --sql  # Preview SQL
railway run alembic upgrade head  # Apply
```

### Issue: Frontend can't connect to backend

**Solution**:
```bash
# Verify backend URL in frontend .env.production
cat frontend/.env.production

# Test backend from browser console
# Open frontend in browser, press F12, run:
fetch('https://your-backend-url/health').then(r => r.json()).then(console.log)

# Should return health status
```

---

## Quick Rollback

If something goes wrong:

```bash
# Rollback backend
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas
railway rollback

# Rollback frontend
npx wrangler pages deployment list --project-name code-atlas
npx wrangler pages deployment rollback <previous-deployment-id>
```

---

## Post-Deployment Checklist

- [ ] Health check returns 200 ✅
- [ ] API docs accessible at `/docs` ✅
- [ ] Frontend loads without errors ✅
- [ ] CORS configured correctly ✅
- [ ] All 18 smoke tests pass ✅
- [ ] Compounding loop CL-001 active ✅
- [ ] Production URLs documented ✅
- [ ] Admin API key secured ✅
- [ ] Cost tracking enabled ✅
- [ ] Monitoring configured (Railway minimum) ✅

---

## What's Next?

**Day 1**:
- Monitor logs for errors
- Test all user flows manually
- Share URLs with team for internal testing

**Week 1**:
- Invite 5-10 beta testers
- Gather feedback
- Monitor costs and performance

**Month 1**:
- Analyze compounding loop effectiveness
- Optimize slow queries
- Consider enabling LLM mode (if started with heuristic)

---

## Quick Reference

**Key Commands**:
```bash
# View logs
railway logs --tail

# Restart service
railway restart

# Check status
railway status

# SSH into container
railway shell

# View environment variables
railway variables

# Update variable
railway variables set KEY=value
```

**Key URLs**:
- Railway Dashboard: https://railway.app/dashboard
- Cloudflare Pages: https://dash.cloudflare.com/pages
- Backend Health: https://<your-url>/health
- API Docs: https://<your-url>/docs

---

## Support

**Issues?** Check:
1. `DEPLOYMENT_RUNBOOK.md` - Detailed step-by-step guide
2. `DEPLOYMENT_DECISIONS_REQUIRED.md` - Decision matrix
3. Railway logs: `railway logs --tail`
4. Sentry dashboard (if configured)

**Still stuck?** Review `CODE_ATLAS_DEPLOYMENT_REPORT.md` for comprehensive analysis.

---

**Created**: 2026-02-08
**Status**: Ready for execution
**Estimated Time**: 2.5-4 hours
**Confidence**: High
