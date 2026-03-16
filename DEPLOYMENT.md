# Code Atlas Deployment Guide

**Platform:** Railway (backend) + Cloudflare Pages (frontend)
**Updated:** 2026-03-16

---

## Architecture

```
Cloudflare Pages (frontend)
        |
        | HTTPS
        v
Railway Service (backend API — FastAPI + uvicorn)
        |
        +---> Railway PostgreSQL (job store via SQLite or PG)
        +---> Railway Redis / FalkorDB (graph database)
```

---

## Backend: Railway

### How It Works

Railway builds a Docker image from `backend/Dockerfile` and runs the container.
Configuration is in `railway.toml` (root of this project). Railway injects `$PORT` at runtime.

Start command:
```
uvicorn code_atlas.api.main:app --host 0.0.0.0 --port $PORT
```

Health check: `GET /health` (timeout 300s, start period 60s)

### Required Environment Variables

Set these in the Railway dashboard under your service's Variables tab.

| Variable | Required | Description |
|---|---|---|
| `CODE_ATLAS_ENV` | Yes | `production` |
| `CODE_ATLAS_ADMIN_API_KEY` | Yes | Secure random string (admin access) |
| `CODE_ATLAS_REDIS_URL` | Yes | `redis://${{Redis.REDIS_URL}}` or `redis://host:6379` |
| `CODE_ATLAS_CORS_ORIGINS` | Yes | `https://your-app.pages.dev` (comma-separated) |
| `ANTHROPIC_API_KEY` | No | LLM extraction (falls back to heuristics if absent) |
| `OPENROUTER_API_KEY` | No | Alternative LLM provider |
| `CODE_ATLAS_API_KEY_REQUIRED` | No | `true` to enforce API key on all endpoints |
| `CODE_ATLAS_MAX_COST_PER_SESSION` | No | Default `0.02` USD |
| `CODE_ATLAS_MAX_CUMULATIVE_COST` | No | Default `10.00` USD |
| `CODE_ATLAS_ENABLE_METRICS` | No | `true` to expose `/metrics` (Prometheus) |

Railway-provided variables (auto-injected, no action needed):
- `PORT` — Railway assigns this dynamically
- `RAILWAY_ENVIRONMENT` — set to `production` automatically

### Deploy Steps

1. Install Railway CLI: `brew install railway` (or `npm install -g @railway/cli`)
2. Login: `railway login`
3. Link to project: `railway link` (select existing project or create new)
4. Add Redis service in Railway dashboard (FalkorDB-compatible Redis)
5. Set environment variables (see table above)
6. Deploy via GitHub push (recommended) or `railway up --detach`

For the monorepo setup (Railway cannot upload the full .git), use GitHub Actions:

```bash
# Trigger via push to main:
git push origin main

# Or trigger manually:
gh workflow run cd.yml
```

### Database Migrations

Alembic is configured in `backend/alembic.ini`. Migrations run against SQLite by default
(job store at `./data/jobs.db`). To run migrations in the Railway shell:

```bash
railway run --service api -- sh -c "cd backend && alembic upgrade head"
```

The migration environment (`backend/alembic/env.py`) reads `CODE_ATLAS_JOB_DB_PATH` to
determine the database path. Set this variable in Railway if you want a non-default path.

### Health Check

```bash
curl https://your-backend.railway.app/health
# {"status": "healthy", ...}
```

---

## Frontend: Cloudflare Pages

### Build Settings (Cloudflare Dashboard)

| Setting | Value |
|---|---|
| Framework | Vite |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `frontend` |

### Environment Variables (Cloudflare Pages)

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://your-backend.railway.app` |
| `VITE_API_KEY` | Optional — client-side API key for authenticated requests |

### Deploy Steps

1. Push `frontend/` changes to GitHub (Cloudflare auto-deploys on push)
2. Or connect the repo in Cloudflare Pages dashboard and configure build settings above
3. Set the environment variables in Pages > Settings > Environment Variables

### Custom Domain

In Cloudflare Pages > Custom domains, add your domain (e.g. `atlas.codeswiftr.com`).
DNS is managed automatically if the domain is on the same Cloudflare account.

---

## Environment Detection

The backend uses `CODE_ATLAS_ENV` to switch behavior:

| `CODE_ATLAS_ENV` | Debug | HSTS | API Key Required |
|---|---|---|---|
| `development` (default) | on | off | off |
| `staging` | off | on | off |
| `production` | off | on | configurable |

All settings are defined in `backend/src/code_atlas/config.py` (`AtlasSettings`).

---

## Rollback

Railway keeps previous deployments. To rollback:

```bash
railway service redeploy api   # reverts to previous successful deploy
```

Or pin a specific Docker image tag in the Railway dashboard.

---

## Monitoring

- **Logs:** `railway logs --service api --tail`
- **Dashboard:** https://railway.app/project/f5004db3-4fc4-4f59-8890-d06bc739bcec
- **Metrics:** `GET /metrics` (Prometheus format, requires `CODE_ATLAS_ENABLE_METRICS=true`)
- **Health:** `GET /health`
- **Status:** `GET /status` (detailed system info)
