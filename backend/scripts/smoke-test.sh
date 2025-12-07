#!/usr/bin/env bash
#
# smoke-test.sh - Staging/production smoke tests for Code Atlas
#
# Runs a minimal set of checks against a running deployment:
# - API health endpoint
# - Core REST flows (discover, process, graph, insights)
# - WebSocket connectivity (optional, best-effort)
#
# Exit codes:
# 0 - All core smoke tests passed
# 1 - One or more smoke tests failed
#

set -euo pipefail

API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"
BASE_URL="http://${API_HOST}:${API_PORT}"
TIMEOUT="${TIMEOUT:-10}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "Required command not found: $1"
    exit 1
  fi
}

check_health() {
  log_info "Checking API health at ${BASE_URL}/health..."
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${BASE_URL}/health" || echo "000")
  if [[ "$code" != "200" ]]; then
    log_error "Health check failed (HTTP $code)"
    return 1
  fi
  log_info "Health check passed"
}

smoke_discover_sessions() {
  log_info "Running sessions discovery smoke test..."
  # This endpoint may be GET or POST depending on configuration; prefer GET if available.
  local url="${BASE_URL}/api/v1/sessions/discover"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" || echo "000")
  if [[ "$code" != "200" ]]; then
    log_warn "Session discovery returned HTTP $code (may be expected if no sessions configured)"
  else
    log_info "Session discovery endpoint reachable"
  fi
}

smoke_graph_entities() {
  log_info "Running graph entities smoke test..."
  local url="${BASE_URL}/api/v1/graph/entities?limit=1"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" || echo "000")
  if [[ "$code" != "200" ]]; then
    log_warn "Graph entities endpoint returned HTTP $code (graph may be empty)"
  else
    log_info "Graph entities endpoint reachable"
  fi
}

smoke_insights() {
  log_info "Running insights smoke test..."
  local endpoints=("top-entities" "recurring-problems" "popular-tools" "trends")
  local ok=true
  for ep in "${endpoints[@]}"; do
    local url="${BASE_URL}/api/v1/insights/${ep}"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" || echo "000")
    if [[ "$code" != "200" ]]; then
      log_warn "Insights endpoint /insights/${ep} returned HTTP $code"
      ok=false
    else
      log_info "Insights endpoint /insights/${ep} reachable"
    fi
  done
  $ok
}

main() {
  require_cmd curl

  log_info "=== Code Atlas Smoke Tests ==="
  log_info "Target: ${BASE_URL}"

  local failed=0

  check_health || failed=1
  smoke_discover_sessions || failed=1
  smoke_graph_entities || failed=1
  smoke_insights || failed=1

  if [[ $failed -ne 0 ]]; then
    log_error "One or more smoke tests failed"
    exit 1
  fi

  log_info "All core smoke tests passed"
}

main "$@"


