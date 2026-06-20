# Code Atlas Makefile
# Quick commands for development, testing, and deployment

.PHONY: help setup install dev test test-fast lint format clean docker-up docker-down serve frontend backend all

# Default target
help:
	@echo "Code Atlas Development Commands"
	@echo "================================"
	@echo ""
	@echo "Setup & Install:"
	@echo "  make setup        - Complete first-time setup (install + docker + env)"
	@echo "  make install      - Install Python dependencies with uv"
	@echo "  make install-all  - Install both backend and frontend dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Start all services (FalkorDB + API + Frontend)"
	@echo "  make backend      - Start only the backend API server"
	@echo "  make frontend     - Start only the frontend dev server"
	@echo "  make docker-up    - Start Docker services (FalkorDB, Redis)"
	@echo "  make docker-down  - Stop Docker services"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all backend tests"
	@echo "  make test-backend - Run backend tests only"
	@echo "  make test-frontend- Run frontend tests only"
	@echo "  make test-fast    - Run fast backend confidence checks (<60s after install)"
	@echo "  make test-unit    - Run broad non-integration backend tests"
	@echo "  make test-int     - Run backend integration tests (requires Docker)"
	@echo "  make test-cov     - Run backend tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         - Run linter (ruff check)"
	@echo "  make format       - Format code (ruff format)"
	@echo "  make typecheck    - Run type checker (mypy)"
	@echo "  make check        - Run all checks (lint + typecheck)"
	@echo ""
	@echo "Utilities:"
	@echo "  make discover     - Discover Claude sessions"
	@echo "  make report       - Generate knowledge graph report"
	@echo "  make clean        - Remove build artifacts and caches"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make setup     - First time setup"
	@echo "  2. make dev       - Start development environment"
	@echo "  3. Visit http://localhost:5173 (frontend) or http://localhost:8000/docs (API)"

# ============================================================================
# Setup & Installation
# ============================================================================

setup: install docker-up env-check
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and add your API keys"
	@echo "  2. Run 'make dev' to start the development environment"
	@echo "  3. Visit http://localhost:5173 for the frontend"
	@echo "  4. Visit http://localhost:8000/docs for the API documentation"

install:
	@echo "📦 Installing backend dependencies..."
	cd backend && uv sync
	@echo "✅ Backend dependencies installed"

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ Frontend dependencies installed"

install-all: install install-frontend
	@echo "✅ All dependencies installed"

env-check:
	@if [ ! -f .env ]; then \
		echo "⚠️  No .env file found. Creating from .env.example..."; \
		cp .env.example .env; \
		echo "📝 Please edit .env and add your API keys"; \
	else \
		echo "✅ .env file exists"; \
	fi

# ============================================================================
# Development
# ============================================================================

docker-up:
	@echo "🐳 Starting Docker services..."
	cd backend && docker compose up -d
	@echo "✅ FalkorDB running on localhost:6379"
	@echo "✅ Redis running on localhost:6380"

docker-down:
	@echo "🐳 Stopping Docker services..."
	cd backend && docker compose down
	@echo "✅ Docker services stopped"

docker-logs:
	cd backend && docker compose logs -f

backend:
	@echo "🚀 Starting backend API server..."
	cd backend && uv run code-atlas serve --reload

frontend:
	@echo "🚀 Starting frontend dev server..."
	cd frontend && npm run dev

# Start all services in parallel (requires docker already running)
dev: docker-up
	@echo "🚀 Starting development environment..."
	@echo "   Frontend: http://localhost:5173"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "Press Ctrl+C to stop"
	@trap 'kill 0' SIGINT; \
	(cd backend && uv run code-atlas serve --reload) & \
	(cd frontend && npm run dev) & \
	wait

serve: backend

# ============================================================================
# Testing
# ============================================================================

test:
	@echo "🧪 Running all backend tests..."
	cd backend && uv run pytest tests/ -v

test-backend:
	@echo "🧪 Running backend tests..."
	cd backend && uv run pytest tests/ -v

test-frontend:
	@echo "🧪 Running frontend tests..."
	cd frontend && npm test -- --run --passWithNoTests

test-fast:
	@echo "🧪 Running fast backend confidence checks..."
	cd backend && uv run pytest \
		tests/test_config.py \
		tests/test_cost_guard.py \
		tests/test_session_parser.py \
		tests/test_insight_extractor.py \
		-q

test-unit:
	@echo "🧪 Running broad non-integration backend tests..."
	cd backend && uv run pytest tests/ -v -m "not integration"

test-int: docker-up
	@echo "🧪 Running integration tests..."
	cd backend && uv run pytest tests/ -v -m "integration"

test-cov:
	@echo "🧪 Running tests with coverage..."
	cd backend && uv run pytest tests/ --cov=code_atlas --cov-report=html --cov-report=term
	@echo "📊 Coverage report: backend/htmlcov/index.html"

# ============================================================================
# Code Quality
# ============================================================================

lint:
	@echo "🔍 Running linter..."
	cd backend && uv run ruff check src/ tests/

format:
	@echo "✨ Formatting code..."
	cd backend && uv run ruff format src/ tests/
	cd backend && uv run ruff check --fix src/ tests/

typecheck:
	@echo "🔍 Running type checker..."
	cd backend && uv run mypy src/

check: lint typecheck
	@echo "✅ All checks passed"

# ============================================================================
# CLI Commands
# ============================================================================

discover:
	@echo "🔍 Discovering Claude sessions..."
	cd backend && uv run code-atlas discover --limit 10

report:
	@echo "📊 Generating knowledge graph report..."
	cd backend && uv run code-atlas report --top-n 20

run-dry:
	@echo "🏃 Running pipeline (dry-run)..."
	cd backend && uv run code-atlas run --dry-run --limit 5

run-heuristics:
	@echo "🏃 Running pipeline with heuristics (no API cost)..."
	cd backend && uv run code-atlas run --no-dry-run --no-use-llm --limit 10

run-llm:
	@echo "🏃 Running pipeline with LLM extraction..."
	cd backend && uv run code-atlas run --no-dry-run --use-llm --limit 5

# ============================================================================
# Database Migrations
# ============================================================================

migrate:
	@echo "🔄 Running database migrations..."
	cd backend && uv run alembic upgrade head
	@echo "✅ Migrations complete"

migrate-create:
	@echo "📝 Creating new migration..."
	@read -p "Migration message: " msg; \
	cd backend && uv run alembic revision --autogenerate -m "$$msg"

migrate-history:
	@echo "📜 Migration history..."
	cd backend && uv run alembic history

migrate-current:
	@echo "📍 Current migration..."
	cd backend && uv run alembic current

migrate-downgrade:
	@echo "⬇️  Downgrading one migration..."
	cd backend && uv run alembic downgrade -1

# ============================================================================
# Cleanup
# ============================================================================

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

clean-docker: docker-down
	@echo "🧹 Removing Docker volumes..."
	cd backend && docker compose down -v
	@echo "✅ Docker cleanup complete"
