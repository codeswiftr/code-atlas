#!/usr/bin/env bash
#
# health-check.sh - Production health check script for Code Atlas
#
# Checks:
# - FastAPI backend health endpoint
# - FalkorDB connection
# - SQLite database accessibility
#
# Exit codes:
# 0 - All systems healthy
# 1 - One or more systems unhealthy
#

set -euo pipefail

# Configuration
API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
TIMEOUT="${TIMEOUT:-5}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# JSON output flag
JSON_OUTPUT="${JSON_OUTPUT:-false}"

# Health status tracking (Bash 3.x compatible)
api_status="unknown"
falkordb_status="unknown"
sqlite_status="unknown"

exit_code=0

# Function to output status
output_status() {
    local component="$1"
    local status="$2"
    local message="$3"

    # Update status variables (Bash 3.x compatible)
    case "$component" in
        api) api_status="$status" ;;
        falkordb) falkordb_status="$status" ;;
        sqlite) sqlite_status="$status" ;;
    esac

    if [[ "$JSON_OUTPUT" == "true" ]]; then
        return
    fi

    if [[ "$status" == "healthy" ]]; then
        echo -e "${GREEN}✓${NC} $component: $message"
    elif [[ "$status" == "unhealthy" ]]; then
        echo -e "${RED}✗${NC} $component: $message"
    else
        echo -e "${YELLOW}?${NC} $component: $message"
    fi
}

# Check API health endpoint
check_api_health() {
    local url="http://${API_HOST}:${API_PORT}/health"

    if command -v curl &> /dev/null; then
        local response
        local http_code

        response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null || true)
        http_code=$(echo "$response" | tail -n1)

        if [[ "$http_code" == "200" ]]; then
            output_status "api" "healthy" "API responding on port $API_PORT"
            return 0
        else
            output_status "api" "unhealthy" "API returned HTTP $http_code"
            return 1
        fi
    else
        output_status "api" "unknown" "curl not available"
        return 1
    fi
}

# Check FalkorDB connection
check_falkordb_health() {
    if command -v redis-cli &> /dev/null; then
        local ping_response

        ping_response=$(timeout "$TIMEOUT" redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null || echo "FAILED")

        if [[ "$ping_response" == "PONG" ]]; then
            output_status "falkordb" "healthy" "FalkorDB responding on port $REDIS_PORT"
            return 0
        else
            output_status "falkordb" "unhealthy" "FalkorDB not responding"
            return 1
        fi
    else
        output_status "falkordb" "unknown" "redis-cli not available"
        return 1
    fi
}

# Check SQLite databases
check_sqlite_health() {
    local db_dir="$PROJECT_ROOT/data"
    local all_healthy=true

    if [[ ! -d "$db_dir" ]]; then
        output_status "sqlite" "unhealthy" "Data directory not found: $db_dir"
        return 1
    fi

    # Check each critical database
    for db_file in jobs.db api_keys.db; do
        local db_path="$db_dir/$db_file"

        if [[ ! -f "$db_path" ]]; then
            output_status "sqlite" "unhealthy" "Database not found: $db_file"
            all_healthy=false
            continue
        fi

        if command -v sqlite3 &> /dev/null; then
            # Try a simple query to verify database is not corrupted
            if timeout "$TIMEOUT" sqlite3 "$db_path" "PRAGMA integrity_check;" &> /dev/null; then
                : # Database is healthy
            else
                output_status "sqlite" "unhealthy" "Database corrupted: $db_file"
                all_healthy=false
            fi
        fi
    done

    if [[ "$all_healthy" == "true" ]]; then
        output_status "sqlite" "healthy" "All databases accessible"
        return 0
    else
        return 1
    fi
}

# Output JSON format
output_json() {
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local overall_status="healthy"
    if [[ "$api_status" != "healthy" ]] || [[ "$falkordb_status" != "healthy" ]] || [[ "$sqlite_status" != "healthy" ]]; then
        overall_status="unhealthy"
    fi

    cat <<EOF
{
  "timestamp": "$timestamp",
  "status": "$overall_status",
  "components": {
    "api": {
      "status": "$api_status",
      "endpoint": "http://${API_HOST}:${API_PORT}/health"
    },
    "falkordb": {
      "status": "$falkordb_status",
      "host": "$REDIS_HOST",
      "port": $REDIS_PORT
    },
    "sqlite": {
      "status": "$sqlite_status",
      "path": "$PROJECT_ROOT/data"
    }
  }
}
EOF
}

# Main execution
main() {
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        echo "Code Atlas Health Check"
        echo "======================"
        echo ""
    fi

    # Run health checks
    check_api_health || exit_code=1
    check_falkordb_health || exit_code=1
    check_sqlite_health || exit_code=1

    # Output results
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        output_json
    else
        echo ""
        if [[ $exit_code -eq 0 ]]; then
            echo -e "${GREEN}Overall Status: HEALTHY${NC}"
        else
            echo -e "${RED}Overall Status: UNHEALTHY${NC}"
        fi
    fi

    exit $exit_code
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help)
            cat <<EOF
Usage: health-check.sh [OPTIONS]

Production health check script for Code Atlas.

OPTIONS:
    --json              Output results in JSON format
    --timeout SECONDS   Timeout for health checks (default: 5)
    --help              Show this help message

ENVIRONMENT VARIABLES:
    API_HOST           API hostname (default: localhost)
    API_PORT           API port (default: 8000)
    REDIS_HOST         FalkorDB hostname (default: localhost)
    REDIS_PORT         FalkorDB port (default: 6379)
    TIMEOUT            Health check timeout in seconds (default: 5)
    JSON_OUTPUT        Output in JSON format (default: false)

EXIT CODES:
    0                  All systems healthy
    1                  One or more systems unhealthy

EXAMPLES:
    # Basic health check
    ./health-check.sh

    # JSON output for monitoring
    ./health-check.sh --json

    # Custom timeout
    ./health-check.sh --timeout 10

    # Check remote instance
    API_HOST=production.example.com ./health-check.sh
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

main
