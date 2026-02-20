"""FastAPI server for metrics and health endpoints."""

from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from .config import AtlasSettings
from .logging_config import get_logger
from .metrics import init_metrics

logger = get_logger(__name__)


class MetricsServer:
    """FastAPI server for metrics and health endpoints."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.metrics = init_metrics(settings)
        self.app = FastAPI(
            title="Code Atlas Metrics",
            description="Monitoring and metrics for Code Atlas pipeline",
            version="1.0.0",
            lifespan=self.lifespan
        )
        self._setup_routes()
        self._server_task: asyncio.Task | None = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Manage application lifecycle."""
        logger.info("Metrics server starting up")

        # Start metrics collection
        if self.settings.enable_metrics:
            self.metrics.start_collection()

        yield

        logger.info("Metrics server shutting down")
        # Stop metrics collection
        if self.settings.enable_metrics:
            self.metrics.stop_collection()

    def _setup_routes(self) -> None:
        """Setup API routes."""

        @self.app.get(self.settings.metrics_path, response_class=PlainTextResponse)
        async def get_metrics():
            """Return Prometheus metrics."""
            if not self.settings.enable_metrics:
                raise HTTPException(status_code=503, detail="Metrics collection is disabled")

            try:
                return self.metrics.get_metrics_text()
            except Exception as exc:
                logger.error(
                    "Error generating metrics",
                    error=str(exc),
                    error_type=type(exc).__name__
                )
                raise HTTPException(status_code=500, detail="Failed to generate metrics") from exc

        @self.app.get(self.settings.health_path)
        async def health_check():
            """Simple health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "service": "code-atlas-metrics"
            }

        @self.app.get(self.settings.status_path)
        async def get_status():
            """Detailed status endpoint."""
            try:
                # Get system information
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                process = psutil.Process()

                status = {
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "service": "code-atlas-metrics",
                    "version": "1.0.0",
                    "metrics_enabled": self.settings.enable_metrics,
                    "system": {
                        "cpu_percent": psutil.cpu_percent(interval=1),
                        "memory": {
                            "total_bytes": memory.total,
                            "available_bytes": memory.available,
                            "used_bytes": memory.used,
                            "percent_used": memory.percent
                        },
                        "disk": {
                            "total_bytes": disk.total,
                            "used_bytes": disk.used,
                            "free_bytes": disk.free,
                            "percent_used": (disk.used / disk.total) * 100
                        },
                        "process": {
                            "pid": process.pid,
                            "memory_rss_bytes": process.memory_info().rss,
                            "cpu_percent": process.cpu_percent(),
                            "num_threads": process.num_threads(),
                            "create_time": datetime.fromtimestamp(
                                process.create_time(), tz=UTC
                            ).isoformat()
                        }
                    },
                    "config": {
                        "metrics_host": self.settings.metrics_host,
                        "metrics_port": self.settings.metrics_port,
                        "metrics_interval": self.settings.metrics_collection_interval,
                        "prometheus_namespace": self.settings.prometheus_namespace
                    }
                }

                return status

            except Exception as exc:
                logger.error(
                    "Error getting status",
                    error=str(exc),
                    error_type=type(exc).__name__
                )
                raise HTTPException(status_code=500, detail="Failed to get status") from exc

        @self.app.get("/")
        async def root():
            """Root endpoint with basic info."""
            return {
                "service": "Code Atlas Metrics Server",
                "version": "1.0.0",
                "endpoints": {
                    "metrics": self.settings.metrics_path,
                    "health": self.settings.health_path,
                    "status": self.settings.status_path
                }
            }

    async def start(self) -> None:
        """Start the metrics server."""
        if not self.settings.enable_metrics:
            logger.info("Metrics server disabled - not starting")
            return

        import uvicorn

        logger.info(
            "Starting metrics server",
            host=self.settings.metrics_host,
            port=self.settings.metrics_port
        )

        config = uvicorn.Config(
            app=self.app,
            host=self.settings.metrics_host,
            port=self.settings.metrics_port,
            log_level="info",
            access_log=True
        )

        server = uvicorn.Server(config)

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully")
            server.should_exit = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            await server.serve()
        except Exception as exc:
            logger.error(
                "Metrics server error",
                error=str(exc),
                error_type=type(exc).__name__
            )
            raise

    def run(self) -> None:
        """Run the metrics server synchronously."""
        if not self.settings.enable_metrics:
            logger.info("Metrics server disabled - not starting")
            return

        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Metrics server stopped by user")
        except Exception as exc:
            logger.error(
                "Metrics server failed",
                error=str(exc),
                error_type=type(exc).__name__
            )
            sys.exit(1)


async def run_metrics_server(settings: AtlasSettings) -> None:
    """Run metrics server as an async task."""
    server = MetricsServer(settings)
    await server.start()


def start_metrics_server(settings: AtlasSettings) -> None:
    """Start metrics server (blocking call)."""
    server = MetricsServer(settings)
    server.run()