# Code Atlas — Production Deploy

**Task ref:** 79839a3a  
**Status:** CD pipeline ready; deploy on push to `main` when secrets are set.

## How deployment works

- **Backend (Railway):** `.github/workflows/cd.yml` builds Docker image, pushes to GHCR, then runs `railway up --detach`.
- **Frontend (Cloudflare Pages):** Same workflow builds frontend (`npm run build` in `frontend/`), then deploys `frontend/dist` via Wrangler.

## Required configuration

### GitHub repository secrets

| Secret | Used by | Description |
|--------|---------|-------------|
| `RAILWAY_TOKEN` | deploy-railway | Railway API token (from Railway dashboard → Account → Tokens) |
| `CLOUDFLARE_API_TOKEN` | deploy-cloudflare | Cloudflare API token with Pages edit (from Cloudflare dashboard → My Profile → API Tokens) |

### GitHub repository variables (or environment "production")

| Variable | Used by | Example |
|----------|---------|---------|
| `VITE_API_URL` | frontend build | `https://code-atlas-api.up.railway.app` |
| `CLOUDFLARE_ACCOUNT_ID` | wrangler-action | From Cloudflare dashboard → Workers & Pages → Overview |

## Triggering a deploy

1. **Automatic:** Push to `main` (when `backend/**` or `.github/workflows/cd.yml` change).
2. **Manual:** GitHub Actions → **CD** workflow → **Run workflow**.

## Post-deploy

- Backend: Railway service URL (e.g. `https://code-atlas-api.up.railway.app`). Run health check: `curl https://<backend-url>/health`.
- Frontend: Cloudflare Pages URL (e.g. `https://code-atlas.pages.dev`). Set backend `CORS_ORIGINS` to the frontend URL.

See `DEPLOY_NOW_QUICKSTART.md` and `DEPLOYMENT_RUNBOOK.md` for full setup (FalkorDB, env vars, smoke tests).
