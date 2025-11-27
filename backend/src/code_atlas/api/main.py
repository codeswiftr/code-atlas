"""Main FastAPI application for Code Atlas API."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import psutil

from ..config import AtlasSettings
from ..logging_config import get_logger
from ..metrics import init_metrics
from .middleware import RateLimitMiddleware
from .v1 import admin_router, graph_router, sessions_router

logger = get_logger(__name__)


class CodeAtlasAPI:
    """Unified Code Atlas API server with metrics and REST endpoints."""

    def __init__(self, settings: AtlasSettings | None = None) -> None:
        self.settings = settings or AtlasSettings()
        self.metrics = init_metrics(self.settings) if self.settings.enable_metrics else None
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Manage application lifecycle."""
            logger.info(
                "Code Atlas API starting",
                host=self.settings.metrics_host,
                port=self.settings.metrics_port,
            )

            # Start metrics collection
            if self.metrics and self.settings.enable_metrics:
                self.metrics.start_collection()

            yield

            logger.info("Code Atlas API shutting down")
            # Stop metrics collection
            if self.metrics and self.settings.enable_metrics:
                self.metrics.stop_collection()

        app = FastAPI(
            title="Code Atlas API",
            description="""
# Code Atlas API

Transform Claude Code sessions into a searchable knowledge graph.

## Features

- **Session Discovery**: Find and list Claude Code session files
- **Session Processing**: Extract insights and populate knowledge graph
- **Graph Queries**: Search entities, relationships, and execute Cypher queries
- **Visualization**: Get graph data formatted for D3.js/Cytoscape.js

## Authentication

All API endpoints require an API key passed in the `X-API-Key` header.

```
X-API-Key: your-api-key-here
```

## Rate Limits

- 100 requests per minute for standard keys
- 1000 requests per minute for admin keys
            """,
            version="1.0.0",
            lifespan=lifespan,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
            openapi_tags=[
                {
                    "name": "Sessions",
                    "description": "Session discovery and processing operations",
                },
                {
                    "name": "Knowledge Graph",
                    "description": "Query and visualize the knowledge graph",
                },
                {
                    "name": "Admin",
                    "description": "API key management and system administration",
                },
                {
                    "name": "Monitoring",
                    "description": "Health checks and metrics",
                },
            ],
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.cors_origins if hasattr(self.settings, 'cors_origins') else ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add rate limiting middleware
        rate_limit = getattr(self.settings, 'rate_limit_per_minute', 100)
        admin_rate_limit = getattr(self.settings, 'admin_rate_limit_per_minute', 1000)
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=rate_limit,
            admin_requests_per_minute=admin_rate_limit,
        )

        # Add request logging middleware
        @app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = datetime.now(tz=timezone.utc)
            response = await call_next(request)
            duration = (datetime.now(tz=timezone.utc) - start_time).total_seconds()

            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration,
            )

            return response

        # Include API routers
        app.include_router(sessions_router, prefix="/api/v1")
        app.include_router(graph_router, prefix="/api/v1")
        app.include_router(admin_router, prefix="/api/v1")

        # Add monitoring routes
        self._setup_monitoring_routes(app)

        # Add root route
        @app.get("/", tags=["Root"])
        async def root():
            """Root endpoint with API information."""
            return {
                "service": "Code Atlas API",
                "version": "1.0.0",
                "description": "Transform Claude Code sessions into a searchable knowledge graph",
                "documentation": "/docs",
                "endpoints": {
                    "api": "/api/v1",
                    "metrics": self.settings.metrics_path,
                    "health": self.settings.health_path,
                    "status": self.settings.status_path,
                },
            }

        return app

    def _setup_monitoring_routes(self, app: FastAPI) -> None:
        """Setup monitoring and health check routes."""

        @app.get(self.settings.metrics_path, response_class=PlainTextResponse, tags=["Monitoring"])
        async def get_metrics():
            """Return Prometheus metrics."""
            if not self.settings.enable_metrics or not self.metrics:
                return PlainTextResponse(
                    content="Metrics collection is disabled",
                    status_code=503,
                )

            try:
                return self.metrics.get_metrics_text()
            except Exception as exc:
                logger.error("Error generating metrics", error=str(exc))
                return PlainTextResponse(
                    content=f"Failed to generate metrics: {exc}",
                    status_code=500,
                )

        @app.get(self.settings.health_path, tags=["Monitoring"])
        async def health_check():
            """Simple health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "service": "code-atlas-api",
            }

        @app.get(self.settings.status_path, tags=["Monitoring"])
        async def get_status():
            """Detailed status endpoint."""
            try:
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                process = psutil.Process()

                return {
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "service": "code-atlas-api",
                    "version": "1.0.0",
                    "metrics_enabled": self.settings.enable_metrics,
                    "system": {
                        "cpu_percent": psutil.cpu_percent(interval=1),
                        "memory": {
                            "total_bytes": memory.total,
                            "available_bytes": memory.available,
                            "used_bytes": memory.used,
                            "percent_used": memory.percent,
                        },
                        "disk": {
                            "total_bytes": disk.total,
                            "used_bytes": disk.used,
                            "free_bytes": disk.free,
                            "percent_used": (disk.used / disk.total) * 100,
                        },
                        "process": {
                            "pid": process.pid,
                            "memory_rss_bytes": process.memory_info().rss,
                            "cpu_percent": process.cpu_percent(),
                            "num_threads": process.num_threads(),
                        },
                    },
                    "config": {
                        "api_host": self.settings.metrics_host,
                        "api_port": self.settings.metrics_port,
                        "session_root": str(self.settings.session_root),
                    },
                }

            except Exception as exc:
                logger.error("Error getting status", error=str(exc))
                return JSONResponse(
                    content={"error": f"Failed to get status: {exc}"},
                    status_code=500,
                )


def create_app(settings: AtlasSettings | None = None) -> FastAPI:
    """Create a FastAPI application instance."""
    api = CodeAtlasAPI(settings)
    return api.app


# Create default app instance for uvicorn
app = create_app()
