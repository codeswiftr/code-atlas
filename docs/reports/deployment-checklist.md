# Code Atlas Deployment Checklist

**MVP Status:** 95% COMPLETE - DEPLOYMENT READY ✅
**Date:** 2026-02-02

---

## Pre-Deployment Setup

### 1. Platform Accounts
- [ ] Railway account created
- [ ] Railway CLI installed: `npm install -g @railway/cli`
- [ ] Cloudflare account created
- [ ] Cloudflare Wrangler CLI installed: `npm install -g wrangler`

### 2. GitHub Repository Setup
- [ ] Repository secrets configured:
  - [ ] `RAILWAY_TOKEN` - Get from Railway dashboard
  - [ ] `CLOUDFLARE_API_TOKEN` - Generate in Cloudflare dashboard
  - [ ] `CLOUDFLARE_ACCOUNT_ID` - From Cloudflare account settings
- [ ] Variables configured (optional):
  - [ ] `VITE_API_URL` - Production API URL

### 3. Railway Backend Configuration
- [ ] Create new Railway project: `railway init`
- [ ] Link to GitHub repository
- [ ] Configure environment variables in Railway dashboard:
  ```
  ANTHROPIC_API_KEY=sk-ant-xxx          # For RAG functionality
  POSTHOG_API_KEY=phc_xxx               # For analytics (optional)
  CODE_ATLAS_ADMIN_API_KEY=xxx          # Admin API access
  CODE_ATLAS_REDIS_URL=redis://xxx      # FalkorDB connection
  CODE_ATLAS_ENV=production
  PORT=8000                              # Railway auto-injects
  ```
- [ ] Add FalkorDB service (or external Redis/FalkorDB)
- [ ] Verify railway.json and railway.toml present

### 4. Cloudflare Pages Configuration
- [ ] Create new Pages project: `wrangler pages project create code-atlas`
- [ ] Configure build settings:
  - Build command: `npm run build`
  - Build output directory: `dist`
  - Root directory: `frontend`
- [ ] Add environment variables:
  ```
  VITE_API_URL=https://code-atlas-api.railway.app
  ```
- [ ] Configure custom domain (optional)

---

## Deployment

### Automated Deployment (Recommended)

1. **Merge to main branch**
   ```bash
   git checkout main
   git merge develop
   git push origin main
   ```

2. **GitHub Actions will automatically:**
   - Run CI tests
   - Build Docker image
   - Deploy backend to Railway
   - Deploy frontend to Cloudflare Pages

3. **Monitor deployment:**
   - Check GitHub Actions: https://github.com/{your-repo}/actions
   - Railway dashboard: https://railway.app
   - Cloudflare Pages: https://dash.cloudflare.com

### Manual Deployment (Alternative)

**Backend:**
```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas
railway login
railway link
railway up --detach
```

**Frontend:**
```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend
npm run build
npx wrangler pages deploy dist --project-name code-atlas
```

---

## Post-Deployment Verification

### 1. Backend Health Checks
```bash
# Replace with your Railway URL
export API_URL="https://code-atlas-api.railway.app"

# Basic health check
curl $API_URL/health
# Expected: {"status":"healthy","timestamp":"...","service":"code-atlas-api"}

# Detailed status
curl $API_URL/status
# Expected: System metrics and configuration

# API documentation
open $API_URL/docs
```

### 2. Frontend Verification
```bash
# Replace with your Cloudflare Pages URL
export FRONTEND_URL="https://code-atlas.pages.dev"

# Check frontend loads
curl -I $FRONTEND_URL
# Expected: HTTP/2 200

# Open in browser
open $FRONTEND_URL
```

### 3. Integration Tests
- [ ] Navigate to frontend in browser
- [ ] Test session discovery page
- [ ] Test session processing (submit a test job)
- [ ] Test entity search
- [ ] Test graph visualization
- [ ] Test RAG query
- [ ] Test insights dashboards

### 4. API Endpoint Tests
```bash
# Test session discovery
curl -X POST $API_URL/api/v1/sessions/discover \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'

# Test graph stats
curl $API_URL/api/v1/graph/stats

# Test insights
curl $API_URL/api/v1/insights/reports
```

---

## Monitoring Setup

### 1. Railway Monitoring
- [ ] Enable Railway metrics in dashboard
- [ ] Set up alerts for:
  - CPU usage > 80%
  - Memory usage > 80%
  - Error rate > 5%
  - Response time > 1s

### 2. Cloudflare Analytics
- [ ] Enable Web Analytics in Pages dashboard
- [ ] Review visitor metrics
- [ ] Check error rates

### 3. Prometheus Metrics (Optional)
```bash
# Access metrics endpoint
curl $API_URL/metrics

# Expected: Prometheus format metrics
# code_atlas_requests_total
# code_atlas_request_duration_seconds
# code_atlas_jobs_total
```

### 4. Log Monitoring
```bash
# Railway logs
railway logs --tail

# Filter for errors
railway logs --tail | grep ERROR
```

---

## Rollback Procedure

### If Issues Occur

1. **Immediate rollback in Railway:**
   ```bash
   railway rollback
   ```

2. **Cloudflare Pages rollback:**
   - Go to Cloudflare Pages dashboard
   - Select previous deployment
   - Click "Rollback to this deployment"

3. **GitHub Actions:**
   - Revert commit in main branch
   - Push to trigger re-deployment

---

## Security Checklist

- [ ] API keys stored securely (not in code)
- [ ] HTTPS enabled (automatic with Railway/Cloudflare)
- [ ] CORS configured for production domain
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] Read-only Cypher query enforcement
- [ ] Non-root Docker user
- [ ] Dependency security scan passed

---

## Performance Baseline

After deployment, record baseline metrics:

- [ ] API response time (p50): _______ ms
- [ ] API response time (p95): _______ ms
- [ ] Graph query time: _______ ms
- [ ] Frontend page load: _______ s
- [ ] Memory usage: _______ MB
- [ ] CPU usage: _______ %

Target: <100ms p50, <200ms p95

---

## Documentation Updates

- [x] CLAUDE.md updated with MVP status
- [x] MVP completion report created
- [ ] Add production URL to README.md
- [ ] Update DEPLOYMENT.md with actual Railway/Cloudflare URLs
- [ ] Document any production-specific configuration

---

## User Communication

- [ ] Prepare announcement (blog post, social media)
- [ ] Create demo video
- [ ] Update website with Code Atlas link
- [ ] Email beta users (if applicable)

---

## Week 1 Post-Deployment

### Daily Checks
- [ ] Monitor error rates
- [ ] Review user feedback
- [ ] Check performance metrics
- [ ] Monitor LLM costs

### Weekly Review
- [ ] Analyze user behavior (PostHog)
- [ ] Review most common queries
- [ ] Identify performance bottlenecks
- [ ] Plan enhancements based on feedback

---

## Known Limitations (Communicated to Users)

1. **Graph visualization**: Best for <500 nodes
2. **LLM costs**: Users responsible for API costs
3. **Session size**: Large files (>50MB) may be slow
4. **Concurrent jobs**: Limited by Railway plan

---

## Support Channels

- [ ] GitHub Issues enabled
- [ ] Documentation link in footer
- [ ] Contact email configured
- [ ] Status page URL (optional)

---

## Success Metrics (Week 1)

Target metrics to track:

- Sessions processed: _______
- Entities created: _______
- Graph queries: _______
- RAG questions: _______
- Uptime: _______ %
- Error rate: _______ %

---

## Optional Enhancements (Post-MVP)

Priority for Week 2-4 based on feedback:

1. [ ] Frontend component tests
2. [ ] Database indexes for performance
3. [ ] Query caching (Redis)
4. [ ] Dark mode
5. [ ] Grafana dashboards
6. [ ] User authentication (if multi-user)

---

**Deployment Date:** __________
**Deployed By:** __________
**Production URLs:**
- Backend: __________
- Frontend: __________

---

**Status:** Ready for deployment ✅

All critical features complete. Optional enhancements can be added based on user feedback.
