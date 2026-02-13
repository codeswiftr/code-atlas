# Code Atlas Production Dockerfile
# ================================
# Multi-stage build for minimal, secure production image
#
# Build: docker build -t code-atlas:latest .
# Run:   docker run -p 8000:8000 code-atlas:latest

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy forge-shared first (monorepo dependency)
COPY forge-shared/ /app/forge-shared/

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/README.md* ./

# Copy application code
COPY backend/src/ ./src/

# Modify pyproject.toml to use local path for forge-shared
RUN sed -i 's|../../../forge-shared|./forge-shared|g' pyproject.toml

# Install dependencies (production only)
RUN uv pip install -e ./forge-shared && uv pip install -e .

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.11-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 atlas \
    && useradd --uid 1000 --gid atlas --shell /bin/bash --create-home atlas

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/src /app/src
COPY --from=builder /app/forge-shared /app/forge-shared
COPY --from=builder /app/pyproject.toml /app/

# Create data directory for SQLite databases
RUN mkdir -p /app/data && chown -R atlas:atlas /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CODE_ATLAS_HOST=0.0.0.0 \
    CODE_ATLAS_PORT=8000 \
    CODE_ATLAS_LOG_LEVEL=INFO \
    CODE_ATLAS_LOG_FORMAT=json \
    CODE_ATLAS_JOB_DB_PATH=/app/data/jobs.db \
    CODE_ATLAS_API_KEY_DB_PATH=/app/data/api_keys.db

# Switch to non-root user
USER atlas

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "code_atlas.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
