#!/usr/bin/env bash
# Deploy readiness check for Code Atlas
# Usage: ./scripts/check-deploy.sh

MISSING=0

check_required() {
  local var="$1"
  if [ -z "${!var}" ]; then
    echo "  FAIL $var — missing"
    MISSING=$((MISSING + 1))
  else
    echo "  PASS $var"
  fi
}

check_optional() {
  local var="$1"
  if [ -z "${!var}" ]; then
    echo "  - $var — not set"
  else
    echo "  - $var — set"
  fi
}

echo "REQUIRED:"
# Admin API key for managing auth keys in production
check_required CODE_ATLAS_ADMIN_API_KEY
# Graph database connection (FalkorDB uses Redis protocol)
# Accept either CODE_ATLAS_REDIS_URL or bare REDIS_URL
if [ -z "${CODE_ATLAS_REDIS_URL}" ] && [ -z "${REDIS_URL}" ]; then
  echo "  FAIL CODE_ATLAS_REDIS_URL (or REDIS_URL) — missing"
  MISSING=$((MISSING + 1))
else
  echo "  PASS CODE_ATLAS_REDIS_URL / REDIS_URL"
fi
# SQLite job/key database paths default to data/ but directory must be writable
# Accept either an explicit DATABASE_URL or confirmation the data/ path is available
if [ -z "${DATABASE_URL}" ]; then
  if [ -d "data" ] || [ -n "${CODE_ATLAS_JOB_DB_PATH}" ]; then
    echo "  PASS DATABASE_URL / SQLite path (using CODE_ATLAS_JOB_DB_PATH or data/)"
  else
    echo "  FAIL DATABASE_URL or SQLite data/ directory — missing"
    MISSING=$((MISSING + 1))
  fi
else
  echo "  PASS DATABASE_URL"
fi

echo ""
echo "OPTIONAL:"
check_optional ANTHROPIC_API_KEY
check_optional OPENROUTER_API_KEY
check_optional STRIPE_SECRET_KEY
check_optional STRIPE_WEBHOOK_SECRET
check_optional SENTRY_DSN

echo ""
if [ "$MISSING" -gt 0 ]; then
  echo "RESULT: $MISSING required variable(s) missing. Cannot deploy."
  exit 1
else
  echo "RESULT: All required variables set. Ready to deploy."
fi
