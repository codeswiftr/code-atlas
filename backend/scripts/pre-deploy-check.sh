#!/usr/bin/env bash
# Pre-deployment validation script for Code Atlas
# ================================================
#
# This script performs comprehensive checks before deployment to ensure
# the application is production-ready.
#
# Usage:
#   ./scripts/pre-deploy-check.sh
#   ./scripts/pre-deploy-check.sh --env production
#   ./scripts/pre-deploy-check.sh --skip-tests
#
# Exit codes:
#   0: All checks passed, ready to deploy
#   1: One or more checks failed, DO NOT deploy

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# Configuration
ENV="${1:-development}"
SKIP_TESTS=false
SKIP_BUILD=false
STRICT_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --strict)
            STRICT_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
print_header() {
    echo -e "\n${BOLD}${BLUE}========================================${RESET}"
    echo -e "${BOLD}${BLUE}$1${RESET}"
    echo -e "${BOLD}${BLUE}========================================${RESET}\n"
}

print_check() {
    echo -e "${BLUE}[CHECK]${RESET} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${RESET} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${RESET} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[INFO]${RESET} $1"
}

# Track overall status
OVERALL_STATUS=0

# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================

print_header "Code Atlas Pre-Deployment Validation"
print_info "Environment: ${ENV}"
print_info "Strict mode: ${STRICT_MODE}"
print_info "Skip tests: ${SKIP_TESTS}"
print_info "Skip build: ${SKIP_BUILD}"

# =============================================================================
# 1. PYTHON ENVIRONMENT
# =============================================================================

print_header "1. Python Environment"

print_check "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        print_pass "Python $PYTHON_VERSION (>= 3.11)"
    else
        print_fail "Python $PYTHON_VERSION found, but 3.11+ required"
        OVERALL_STATUS=1
    fi
else
    print_fail "Python 3 not found"
    OVERALL_STATUS=1
fi

print_check "Checking uv package manager..."
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version | awk '{print $2}')
    print_pass "uv $UV_VERSION installed"
else
    print_fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    OVERALL_STATUS=1
fi

print_check "Checking virtual environment..."
if [ -d ".venv" ]; then
    print_pass "Virtual environment exists"
else
    print_warn "Virtual environment not found. Run: uv sync"
fi

# =============================================================================
# 2. DEPENDENCIES
# =============================================================================

print_header "2. Dependencies"

print_check "Checking dependencies are installed..."
if uv pip list &> /dev/null; then
    print_pass "Dependencies installed"
else
    print_fail "Dependencies not installed. Run: uv sync"
    OVERALL_STATUS=1
fi

print_check "Checking for security vulnerabilities..."
if command -v safety &> /dev/null; then
    if uv pip freeze | safety check --stdin &> /dev/null; then
        print_pass "No known security vulnerabilities"
    else
        print_warn "Security vulnerabilities detected. Review with: safety check"
    fi
else
    print_info "Safety not installed (optional). Install: uv add safety"
fi

# =============================================================================
# 3. ENVIRONMENT VARIABLES
# =============================================================================

print_header "3. Environment Variables"

print_check "Validating environment variables..."
if python3 scripts/validate-env.py --env "$ENV" ${STRICT_MODE:+--strict}; then
    print_pass "Environment variables validated"
else
    print_fail "Environment variable validation failed"
    OVERALL_STATUS=1
fi

# =============================================================================
# 4. CODE QUALITY
# =============================================================================

print_header "4. Code Quality"

print_check "Running ruff linter..."
if uv run ruff check src/ --quiet; then
    print_pass "Linting passed (ruff)"
else
    print_fail "Linting errors found. Run: ruff check src/"
    OVERALL_STATUS=1
fi

print_check "Checking code formatting..."
if uv run ruff format src/ --check --quiet; then
    print_pass "Code formatting correct"
else
    print_fail "Code formatting issues. Run: ruff format src/"
    OVERALL_STATUS=1
fi

print_check "Running type checker (mypy)..."
if command -v mypy &> /dev/null; then
    if uv run mypy src/ --no-error-summary 2>&1 | grep -q "Success"; then
        print_pass "Type checking passed (mypy)"
    else
        print_warn "Type checking warnings. Run: mypy src/"
    fi
else
    print_info "mypy not installed (optional). Install: uv add mypy"
fi

# =============================================================================
# 5. SECURITY CHECKS
# =============================================================================

print_header "5. Security Checks"

print_check "Running bandit security scanner..."
if command -v bandit &> /dev/null; then
    if uv run bandit -r src/ -ll -q; then
        print_pass "Security scan passed (bandit)"
    else
        print_warn "Security warnings found. Run: bandit -r src/"
    fi
else
    print_info "bandit not installed (optional). Install: uv add bandit"
fi

print_check "Checking for hardcoded secrets..."
if grep -r "sk-ant-" src/ 2>/dev/null | grep -v ".pyc" | grep -v "__pycache__"; then
    print_fail "Hardcoded API keys found in source code"
    OVERALL_STATUS=1
elif grep -r "ANTHROPIC_API_KEY.*=.*sk-" src/ 2>/dev/null | grep -v ".pyc"; then
    print_fail "Hardcoded API keys found in source code"
    OVERALL_STATUS=1
else
    print_pass "No hardcoded secrets detected"
fi

print_check "Checking for TODO/FIXME in critical paths..."
TODOS=$(grep -r "TODO\|FIXME" src/code_atlas/api src/code_atlas/auth 2>/dev/null | grep -v ".pyc" | wc -l || echo 0)
if [ "$TODOS" -gt 0 ]; then
    print_warn "Found $TODOS TODO/FIXME comments in critical paths"
else
    print_pass "No TODO/FIXME in critical paths"
fi

# =============================================================================
# 6. TESTS
# =============================================================================

if [ "$SKIP_TESTS" = false ]; then
    print_header "6. Tests"

    print_check "Running unit tests..."
    if .venv/bin/python -m pytest tests/ -v --maxfail=1 -x; then
        print_pass "All tests passed"
    else
        print_fail "Tests failed"
        OVERALL_STATUS=1
    fi

    print_check "Running smoke tests..."
    if .venv/bin/python -m pytest tests/e2e/test_smoke.py -v; then
        print_pass "Smoke tests passed"
    else
        print_fail "Smoke tests failed"
        OVERALL_STATUS=1
    fi

    print_check "Checking test coverage..."
    if command -v coverage &> /dev/null; then
        COVERAGE=$(.venv/bin/python -m pytest tests/ --cov=src/code_atlas --cov-report=term-missing | grep TOTAL | awk '{print $4}' | sed 's/%//')
        if [ -n "$COVERAGE" ] && [ "$COVERAGE" -ge 70 ]; then
            print_pass "Test coverage: ${COVERAGE}% (>= 70%)"
        else
            print_warn "Test coverage: ${COVERAGE}% (target: 70%)"
        fi
    else
        print_info "Coverage not available. Install: uv add pytest-cov"
    fi
else
    print_info "Tests skipped (--skip-tests flag)"
fi

# =============================================================================
# 7. BUILD VALIDATION
# =============================================================================

if [ "$SKIP_BUILD" = false ]; then
    print_header "7. Build Validation"

    print_check "Testing Docker build (backend)..."
    if [ -f "Dockerfile" ]; then
        if docker build -t code-atlas:test -f Dockerfile . --quiet > /dev/null 2>&1; then
            print_pass "Docker build successful"
        else
            print_fail "Docker build failed. Run: docker build -f Dockerfile ."
            OVERALL_STATUS=1
        fi
    else
        print_warn "Dockerfile not found"
    fi
else
    print_info "Build validation skipped (--skip-build flag)"
fi

# =============================================================================
# 8. DATABASE MIGRATIONS
# =============================================================================

print_header "8. Database Migrations"

print_check "Checking for pending migrations..."
if [ -d "alembic/versions" ]; then
    MIGRATION_COUNT=$(ls -1 alembic/versions/*.py 2>/dev/null | wc -l || echo 0)
    if [ "$MIGRATION_COUNT" -gt 0 ]; then
        print_pass "Found $MIGRATION_COUNT database migrations"
    else
        print_info "No database migrations found"
    fi
else
    print_info "Alembic not configured (SQLite only)"
fi

# =============================================================================
# 9. CONFIGURATION FILES
# =============================================================================

print_header "9. Configuration Files"

print_check "Checking Railway configuration..."
if [ -f "../railway.toml" ] || [ -f "../railway.json" ]; then
    print_pass "Railway configuration exists"
else
    print_warn "Railway configuration not found"
fi

print_check "Checking Dockerfile..."
if [ -f "Dockerfile" ]; then
    print_pass "Dockerfile exists"
else
    print_fail "Dockerfile not found"
    OVERALL_STATUS=1
fi

print_check "Checking .env.example..."
if [ -f ".env.example" ]; then
    print_pass ".env.example exists"
else
    print_warn ".env.example not found (recommended for documentation)"
fi

# =============================================================================
# 10. DEPLOYMENT-SPECIFIC CHECKS
# =============================================================================

print_header "10. Deployment-Specific Checks"

if [ "$ENV" = "production" ]; then
    print_check "Checking production settings..."

    if [ -z "$CODE_ATLAS_ADMIN_API_KEY" ]; then
        print_fail "CODE_ATLAS_ADMIN_API_KEY not set (required for production)"
        OVERALL_STATUS=1
    else
        print_pass "Admin API key configured"
    fi

    if [ -z "$FALKORDB_HOST" ]; then
        print_fail "FALKORDB_HOST not set (required)"
        OVERALL_STATUS=1
    else
        print_pass "FalkorDB host configured"
    fi

    if [ "$CODE_ATLAS_DEBUG" = "true" ]; then
        print_warn "DEBUG mode enabled in production (should be false)"
    else
        print_pass "DEBUG mode disabled"
    fi

    if [ "$CODE_ATLAS_LOG_FORMAT" != "json" ]; then
        print_warn "Log format should be 'json' in production"
    else
        print_pass "JSON logging configured"
    fi
fi

# =============================================================================
# SUMMARY
# =============================================================================

print_header "Validation Summary"

echo -e "${GREEN}Passed:${RESET}   $PASSED"
echo -e "${YELLOW}Warnings:${RESET} $WARNINGS"
echo -e "${RED}Failed:${RESET}   $FAILED"

if [ $OVERALL_STATUS -eq 0 ]; then
    if [ $WARNINGS -gt 0 ] && [ "$STRICT_MODE" = true ]; then
        echo -e "\n${YELLOW}${BOLD}WARNINGS IN STRICT MODE${RESET}"
        echo -e "${YELLOW}Deployment not recommended with warnings in strict mode${RESET}"
        exit 1
    else
        echo -e "\n${GREEN}${BOLD}✓ ALL CHECKS PASSED${RESET}"
        echo -e "${GREEN}Ready to deploy to ${ENV}${RESET}"
        exit 0
    fi
else
    echo -e "\n${RED}${BOLD}✗ DEPLOYMENT BLOCKED${RESET}"
    echo -e "${RED}Fix errors before deploying to ${ENV}${RESET}"
    exit 1
fi
