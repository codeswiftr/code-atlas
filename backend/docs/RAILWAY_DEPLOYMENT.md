# Railway Deployment Guide for Code Atlas

## Overview

Code Atlas is configured for deployment on Railway using Docker containerization. This guide validates the deployment configuration and provides a deployment checklist.

## Configuration Files

### railway.json
- **Location**: `/railway.json` (project root)
- **Purpose**: Railway-specific deployment configuration
- **Status**: ✅ Validated

### railway.toml
- **Location**: `/railway.toml` (project root)
- **Purpose**: Alternative TOML-based Railway configuration
- **Status**: ✅ Validated
- **Note**: `railway.toml` takes precedence over `railway.json`

### Dockerfile
- **Location**: `/backend/Dockerfile`
- **Purpose**: Multi-stage Docker build for production
- **Status**: ✅ Validated

## Configuration Validation

### Build Configuration ✅

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"
```

**Validation:**
- ✅ Builder type: DOCKERFILE
- ✅ Dockerfile path: Correct relative path from project root
- ✅ Multi-stage build: Optimized for production (builder + runtime stages)
- ✅ Security: Non-root user (atlas:1000)
- ✅ Dependencies: Using `uv` for fast, reproducible builds

### Deploy Configuration ✅

```toml
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
startPeriod = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
startCommand = "sh -c 'echo Starting Code Atlas on port $PORT && uvicorn code_atlas.api.main:app --host 0.0.0.0 --port $PORT'"
```

**Validation:**

#### Health Check ✅
- **Path**: `/health`
- **Timeout**: 300 seconds (5 minutes) - Appropriate for startup
- **Start Period**: 60 seconds - Allows time for initialization
- **Implementation**: Verified in `code_atlas.api.main:FastAPIFactory.create_app()`
- **Test Coverage**: See `tests/e2e/test_smoke.py::TestSmokeHealth`

#### Start Command ✅
- **Command**: Uses `uvicorn` directly (production ASGI server)
- **Host**: `0.0.0.0` - Binds to all interfaces
- **Port**: `$PORT` - Railway-injected environment variable
- **Alternative**: `railway.json` uses `python -m code_atlas.cli serve` (also valid)

**Recommendation**: Use the `uvicorn` command in `railway.toml` for better performance and control.

#### Restart Policy ✅
- **Type**: `ON_FAILURE` - Appropriate for production
- **Max Retries**: 3 - Prevents infinite restart loops
- **Status**: Validated

### Resource Limits

**Current Status**: Not explicitly configured ❌

**Recommendation**: Add resource limits to prevent OOM and cost overruns.

```toml
[deploy.resources]
memory = 1024  # MB - adjust based on usage
cpu = 1000     # mCPU (1 vCPU)
```

**Action Required**: Monitor production usage and configure limits accordingly.

## Environment Variables

### Required Variables

These environment variables MUST be set in Railway:

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `PORT` | Application port (Railway-injected) | `8000` | Yes (Auto) |
| `FALKORDB_HOST` | FalkorDB host | `redis-12345.railway.app` | Yes |
| `FALKORDB_PORT` | FalkorDB port | `6379` | Yes |
| `CODE_ATLAS_API_KEY` | Admin API key for auth | `sk-xxx` | No* |
| `ANTHROPIC_API_KEY` | Claude API key (optional) | `sk-ant-xxx` | No |
| `OPENROUTER_API_KEY` | OpenRouter API key (optional) | `sk-or-xxx` | No |

*Required if `CODE_ATLAS_API_KEY_REQUIRED=true`

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CODE_ATLAS_LOG_LEVEL` | Logging level | `INFO` |
| `CODE_ATLAS_LOG_FORMAT` | Log format (json/text) | `json` |
| `CODE_ATLAS_ENABLE_METRICS` | Enable Prometheus metrics | `true` |
| `CODE_ATLAS_ENABLE_CORS` | Enable CORS | `true` |
| `CODE_ATLAS_MAX_SESSIONS` | Max sessions per run | `100` |

### Environment Variable Setup in Railway

```bash
# Core configuration
railway variables set FALKORDB_HOST=<your-falkordb-host>
railway variables set FALKORDB_PORT=6379

# Optional: API authentication
railway variables set CODE_ATLAS_API_KEY=<generate-secure-key>
railway variables set CODE_ATLAS_API_KEY_REQUIRED=true

# Optional: AI providers
railway variables set ANTHROPIC_API_KEY=<your-key>

# Production settings
railway variables set CODE_ATLAS_LOG_FORMAT=json
railway variables set CODE_ATLAS_LOG_LEVEL=INFO
```

## Database Configuration

### FalkorDB (Required)

Code Atlas requires a FalkorDB instance for graph storage.

**Railway Setup:**
1. Add FalkorDB to your project (use Redis with FalkorDB module)
2. Connect service to Code Atlas
3. Railway will auto-inject connection variables

**Verification:**
```bash
# Check FalkorDB connectivity
curl https://your-app.railway.app/health
```

### SQLite (Built-in)

Job tracking and API keys use SQLite (embedded).

**Storage:**
- `/app/data/jobs.db` (volume-backed recommended)
- `/app/data/api_keys.db` (volume-backed recommended)

**Railway Volume Setup:**
```bash
railway volume create code-atlas-data
railway volume mount code-atlas-data /app/data
```

## Deployment Checklist

### Pre-Deployment ✅

- [ ] **Tests Pass**: Run `pytest` and ensure all tests pass
- [ ] **Linting**: Run `ruff check .` and `ruff format .`
- [ ] **Type Checking**: Run `mypy src/`
- [ ] **Security Scan**: Run `bandit -r src/`
- [ ] **Smoke Tests**: Run `pytest tests/e2e/test_smoke.py`
- [ ] **Build Test**: Run `docker build -t code-atlas:test -f backend/Dockerfile .`

### Railway Project Setup ✅

- [ ] **Create Railway Project**: `railway init`
- [ ] **Link Repository**: Connect GitHub repository
- [ ] **Add FalkorDB Service**: Add Redis with FalkorDB module
- [ ] **Configure Variables**: Set all required environment variables
- [ ] **Setup Volumes** (Optional): Mount persistent storage for SQLite DBs
- [ ] **Configure Custom Domain** (Optional): Add production domain

### Post-Deployment ✅

- [ ] **Health Check**: Verify `/health` returns 200
- [ ] **API Docs**: Access `/docs` and verify OpenAPI documentation
- [ ] **FalkorDB Connection**: Test graph query endpoints
- [ ] **Authentication**: Test API key authentication (if enabled)
- [ ] **Metrics**: Access `/metrics` (if enabled)
- [ ] **Logs**: Check Railway logs for startup errors
- [ ] **Performance**: Verify response times meet SLAs (<200ms p95)

## Deployment Commands

### Via Railway CLI

```bash
# Deploy current branch
railway up

# Deploy specific service
railway up --service code-atlas-backend

# View logs
railway logs --tail 100

# Run one-off commands
railway run python -m code_atlas.cli --help
```

### Via GitHub Integration

1. Push to `main` branch
2. Railway automatically builds and deploys
3. Monitor deployment in Railway dashboard

## Health Check Endpoint

**Endpoint**: `GET /health`

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "0.1.0",
  "database": "connected"
}
```

**Status Codes:**
- `200`: Service healthy
- `503`: Service unhealthy (database connection failed, etc.)

**Railway Configuration:**
- **Path**: `/health` (configured)
- **Timeout**: 300s
- **Interval**: 30s (Railway default)

## Monitoring

### Logs

**Access Logs:**
```bash
# Stream logs
railway logs --tail

# Filter logs
railway logs | grep ERROR
```

**Log Format**: JSON (structured logging for production)

### Metrics

**Prometheus Metrics Endpoint**: `/metrics`

**Key Metrics:**
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `graph_query_duration_seconds` - Graph query performance
- `pipeline_runs_total` - Pipeline executions

### Alerts

Configure Railway alerts for:
- Health check failures
- High memory usage (>80%)
- High CPU usage (>80%)
- Error rate spikes

## Troubleshooting

### Deployment Fails to Start

**Check:**
1. Railway logs: `railway logs`
2. Environment variables: `railway variables`
3. FalkorDB connectivity: Check service status
4. Dockerfile syntax: `docker build -f backend/Dockerfile .`

**Common Issues:**
- Missing `PORT` variable (Railway should auto-inject)
- FalkorDB connection refused (check service linking)
- OOM (increase memory limits)

### Health Check Fails

**Debug:**
```bash
# Check health endpoint locally
railway run curl http://localhost:8000/health

# Check FalkorDB connectivity
railway run python -c "import redis; redis.Redis(host='falkordb-host').ping()"
```

### Slow Response Times

**Actions:**
1. Check resource usage in Railway dashboard
2. Review slow query logs
3. Add database indexes (see `docs/database-indexing.md`)
4. Increase resource limits

## Security Considerations

### API Authentication ✅

- **Enabled**: Set `CODE_ATLAS_API_KEY_REQUIRED=true`
- **Key Storage**: Use Railway secrets (encrypted)
- **Key Rotation**: Rotate keys every 90 days

### Network Security ✅

- **HTTPS**: Railway provides automatic HTTPS
- **CORS**: Configured in `code_atlas.api.middleware`
- **Rate Limiting**: Implemented (configurable)

### Container Security ✅

- **Non-root User**: Runs as `atlas:1000`
- **Minimal Base**: Python 3.11-slim
- **No Dev Dependencies**: Production-only packages
- **Security Scanning**: Run `docker scan code-atlas:latest`

## Cost Optimization

### Resource Efficiency

**Current Setup:**
- Multi-stage build reduces image size
- Production-only dependencies
- Efficient startup (uv package manager)

**Recommendations:**
1. Monitor memory usage and right-size limits
2. Use Railway usage-based pricing efficiently
3. Implement caching for frequently accessed data
4. Scale down non-production environments when idle

## Rollback Procedure

### Quick Rollback

```bash
# List deployments
railway deployments

# Rollback to specific deployment
railway deployments rollback <deployment-id>
```

### Manual Rollback

1. Revert to previous git commit
2. Push to trigger new deployment
3. Verify health checks pass

## Support Resources

- **Railway Docs**: https://docs.railway.app
- **Code Atlas Docs**: `/backend/docs/`
- **Health Monitoring**: `/health`, `/metrics`
- **API Documentation**: `/docs`, `/redoc`

## Changelog

- **2024-01-01**: Initial Railway deployment configuration
- **2024-01-15**: Added health check validation
- **2024-02-01**: Updated to use uvicorn start command

---

**Last Validated**: 2026-02-08
**Status**: ✅ Production Ready
**Deployment Confidence**: High
