# Backend Deployment Notes

See `../DEPLOYMENT.md` at the project root for the full Railway + Cloudflare deployment guide.

## Quick Reference

- **Start command:** `uvicorn code_atlas.api.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `GET /health`
- **Migrations:** `alembic upgrade head` (run from this `backend/` directory)
- **Config module:** `src/code_atlas/config.py` (`AtlasSettings` — reads `CODE_ATLAS_*` env vars)
