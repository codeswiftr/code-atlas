"""
Health check module for FastAPI applications.

Provides a standardized health router with configurable health checks.

Example:
    ```python
    from fastapi import FastAPI
    from forge_shared.health import create_health_router

    app = FastAPI()
    app.include_router(
        create_health_router(
            name="my-service",
            version="1.0.0",
            checks=["database", "redis"]
        ),
        prefix="/api"
    )
    ```
"""

from forge_shared.health.router import create_health_router, HealthCheck, HealthStatus

__all__ = ["create_health_router", "HealthCheck", "HealthStatus"]
