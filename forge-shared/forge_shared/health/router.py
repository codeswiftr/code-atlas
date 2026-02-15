"""
Health check router for FastAPI applications.

Provides standardized health endpoints with configurable checks.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel


class HealthStatus(str, Enum):
    """Health status values."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CheckResult(BaseModel):
    """Result of a single health check."""
    
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Standard health check response."""
    
    status: HealthStatus
    name: str
    version: str
    timestamp: str
    checks: dict[str, CheckResult] = {}


class HealthCheck:
    """
    Health check configuration.
    
    Attributes:
        name: Name of the check (e.g., "database", "redis")
        check_fn: Async function that performs the check and returns (ok, latency_ms, message)
    """
    
    def __init__(
        self,
        name: str,
        check_fn: Callable[[], tuple[bool, Optional[float], Optional[str]]],
    ):
        """
        Initialize health check.
        
        Args:
            name: Check name
            check_fn: Async or sync function returning (ok, latency_ms, message)
        """
        self.name = name
        self.check_fn = check_fn


def create_health_router(
    name: str,
    version: str = "0.1.0",
    checks: Optional[list[HealthCheck]] = None,
    include_live: bool = True,
    include_ready: bool = True,
) -> APIRouter:
    """
    Create a health check router with standardized endpoints.
    
    Args:
        name: Service name
        version: Service version
        checks: List of HealthCheck objects for detailed checks
        include_live: Include /health/live endpoint (Kubernetes liveness)
        include_ready: Include /health/ready endpoint (Kubernetes readiness)
    
    Returns:
        FastAPI router with health endpoints
    
    Example:
        ```python
        from forge_shared.health import create_health_router, HealthCheck
        
        async def check_database():
            # Returns (ok, latency_ms, message)
            return True, 5.0, None
        
        router = create_health_router(
            name="my-service",
            version="1.0.0",
            checks=[HealthCheck("database", check_database)]
        )
        app.include_router(router, prefix="/api")
        ```
    """
    router = APIRouter(tags=["Health"])
    checks = checks or []
    
    async def _run_checks() -> tuple[HealthStatus, dict[str, CheckResult]]:
        """Run all health checks and return status."""
        results: dict[str, CheckResult] = {}
        all_ok = True
        
        for check in checks:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(check.check_fn):
                    ok, latency_ms, message = await check.check_fn()
                else:
                    ok, latency_ms, message = check.check_fn()
                
                results[check.name] = CheckResult(
                    status="ok" if ok else "error",
                    latency_ms=latency_ms,
                    message=message,
                )
                if not ok:
                    all_ok = False
            except Exception as e:
                results[check.name] = CheckResult(
                    status="error",
                    message=str(e),
                )
                all_ok = False
        
        status = HealthStatus.HEALTHY if all_ok else HealthStatus.UNHEALTHY
        return status, results
    
    @router.get("/health", response_model=HealthResponse)
    async def health_check(response: Response) -> HealthResponse:
        """
        Comprehensive health check endpoint.
        
        Returns service status, version, and individual check results.
        """
        status, check_results = await _run_checks()
        
        if status != HealthStatus.HEALTHY:
            response.status_code = 503
        
        return HealthResponse(
            status=status,
            name=name,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            checks=check_results,
        )
    
    if include_live:
        @router.get("/health/live")
        async def liveness_check() -> dict[str, str]:
            """
            Kubernetes liveness probe.
            
            Always returns healthy if the service is running.
            """
            return {"status": "ok"}
    
    if include_ready:
        @router.get("/health/ready")
        async def readiness_check(response: Response) -> dict[str, str]:
            """
            Kubernetes readiness probe.
            
            Checks if the service is ready to accept traffic.
            """
            status, _ = await _run_checks()
            
            if status != HealthStatus.HEALTHY:
                response.status_code = 503
                return {"status": "not_ready"}
            
            return {"status": "ready"}
    
    return router
