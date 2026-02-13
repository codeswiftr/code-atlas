# Code Atlas Production Deployment

**Deployed**: 2026-02-13  
**Platform**: Railway  
**Status**: 🔄 In Progress

## Environment Variables

Configured in Railway production environment:

| Variable | Status | Value |
|----------|--------|-------|
| DATABASE_URL | ✅ Configured | PostgreSQL (Railway) |
| FALKORDB_HOST | ✅ Configured | redis.railway.internal |
| FALKORDB_PORT | ✅ Configured | 6379 |
| CODE_ATLAS_ADMIN_API_KEY | ✅ Configured | [Redacted] |
| MAX_COST_PER_SESSION_USD | ✅ Configured | 0.02 |
| MAX_CUMULATIVE_COST_USD | ✅ Configured | 10.00 |
| USE_LLM | ✅ Configured | false |

## Infrastructure

### Railway Services
- **API Service**: `api` (linked)
- **PostgreSQL**: ✅ Available (`0edc5b10-7cd1-46c0-bb42-85252cad100d`)
- **Redis**: ✅ Available (`ab74d42e-63e2-4578-8051-fb52e4199740`)

### Project Details
- **Project**: friendly-heart
- **Environment**: production
- **Service ID**: 4d17e39e-a26d-4d37-ad8e-23ffb5cd79a8

## Deployment Method

Due to large monorepo size (parent .git directory), CLI upload failed with 413 Payload Too Large.

**Alternative Approach**: GitHub Actions CD Pipeline
- Workflow: `.github/workflows/cd.yml`
- Builds Docker image from `backend/Dockerfile`
- Pushes to GitHub Container Registry (ghcr.io)
- Railway configured to deploy from built image

## Docker Build

Multi-stage Dockerfile at `backend/Dockerfile`:
- Stage 1: Builder (Python 3.11-slim + uv)
- Stage 2: Runtime (minimal image with security hardening)
- Non-root user (`atlas`)
- Health check on `/health`

## Health Checks

Once deployed:
- `GET /health` - API health
- `GET /api/v1/health` - Service health

## Testing

Core API tests pass:
```bash
cd backend
uv run pytest tests/test_api.py -q
# ✅ All API tests passing
```

Known test exclusions:
- `test_metrics_endpoint_accessible` - Requires FalkorDB connection (503 in test env)
- CLI tests - Fixture compatibility issues

## Interview Simulator Integration

**Status**: ⏳ Pending deployment completion

Once API is live, update Interview Simulator frontend:
1. Set `CODE_ATLAS_API_URL` to production URL
2. Configure `CODE_ATLAS_API_KEY` for authentication
3. Deploy updated frontend

## Monitoring

- **Railway Dashboard**: https://railway.app/project/f5004db3-4fc4-4f59-8890-d06bc739bcec
- **Logs**: `railway logs --service api`
- **Service Status**: `railway service status`

## Rollback

To rollback to previous version:
```bash
railway service redeploy api
```

## Next Steps

1. ✅ GitHub Actions CD triggered
2. ⏳ Wait for Docker image build
3. ⏳ Railway deployment from image
4. ⏳ Verify health endpoints
5. ⏳ Interview Simulator integration
6. ⏳ Update documentation with live URL

## Notes

- **Issue**: Railway CLI upload fails due to parent monorepo .git directory (2.1GB)
- **Solution**: Using GitHub Actions CD pipeline for Docker-based deployment
- **Time spent**: ~45 minutes (assessment, troubleshooting, setup)
- **Pi's previous work**: No deliverables found, started fresh

## Deployment URL

**Pending**: Will be available after GitHub Actions completes

To check status:
```bash
cd codeswiftr-com/code-atlas
gh run list --workflow=cd.yml
railway service status --all
```
