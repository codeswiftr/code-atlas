"""Prometheus metrics collection for Code Atlas monitoring."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

import psutil
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
)

from .config import AtlasSettings
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    metrics_path: str = "/metrics"
    health_path: str = "/health"
    status_path: str = "/status"
    collection_interval: int = 30
    namespace: str = "code_atlas"


class AtlasMetrics:
    """Centralized metrics collection for Code Atlas."""

    _instance: ClassVar[AtlasMetrics | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, config: MetricsConfig) -> None:
        self.config = config
        self.registry = CollectorRegistry()
        self._system_metrics_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Initialize Prometheus metrics
        self._init_metrics()

        # Track additional state
        self.start_time = datetime.now(tz=UTC)
        self.session_counts: dict[str, int] = {}
        self.error_counts: dict[str, int] = {}

    @classmethod
    def get_instance(cls, config: MetricsConfig | None = None) -> AtlasMetrics:
        """Get singleton instance of metrics collector."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if config is None:
                        config = MetricsConfig()
                    cls._instance = cls(config)
        return cls._instance

    def _init_metrics(self) -> None:
        """Initialize all Prometheus metrics."""
        ns = self.config.namespace

        # Pipeline metrics
        self.pipeline_sessions_total = Counter(
            f"{ns}_pipeline_sessions_total",
            "Total number of sessions processed",
            ["project", "status"],
            registry=self.registry
        )

        self.pipeline_processing_time = Histogram(
            f"{ns}_pipeline_processing_seconds",
            "Time spent processing sessions",
            ["project"],
            registry=self.registry
        )

        self.pipeline_messages_processed = Counter(
            f"{ns}_pipeline_messages_total",
            "Total number of messages processed",
            registry=self.registry
        )

        self.pipeline_tokens_processed = Counter(
            f"{ns}_pipeline_tokens_total",
            "Total number of tokens processed",
            registry=self.registry
        )

        # Database metrics
        self.db_nodes_created = Counter(
            f"{ns}_db_nodes_created_total",
            "Total number of nodes created in database",
            ["node_type"],
            registry=self.registry
        )

        self.db_relationships_created = Counter(
            f"{ns}_db_relationships_created_total",
            "Total number of relationships created in database",
            ["relationship_type"],
            registry=self.registry
        )

        self.db_query_duration = Histogram(
            f"{ns}_db_query_seconds",
            "Database query execution time",
            ["operation"],
            registry=self.registry
        )

        self.db_connections_active = Gauge(
            f"{ns}_db_connections_active",
            "Number of active database connections",
            registry=self.registry
        )

        # Extraction metrics
        self.extraction_requests_total = Counter(
            f"{ns}_extraction_requests_total",
            "Total number of extraction requests",
            ["method", "model"],
            registry=self.registry
        )

        self.extraction_duration = Histogram(
            f"{ns}_extraction_seconds",
            "Time spent on insight extraction",
            ["method"],
            registry=self.registry
        )

        self.extraction_entities_created = Counter(
            f"{ns}_extraction_entities_created_total",
            "Total number of entities extracted",
            ["entity_type"],
            registry=self.registry
        )

        self.extraction_relationships_created = Counter(
            f"{ns}_extraction_relationships_created_total",
            "Total number of relationships extracted",
            ["relationship_type"],
            registry=self.registry
        )

        # Cost metrics
        self.cost_total_usd = Counter(
            f"{ns}_cost_total_usd",
            "Total cost incurred in USD",
            ["model", "operation"],
            registry=self.registry
        )

        self.cost_per_session = Histogram(
            f"{ns}_cost_per_session_usd",
            "Cost per session in USD",
            registry=self.registry
        )

        # Error metrics
        self.errors_total = Counter(
            f"{ns}_errors_total",
            "Total number of errors",
            ["component", "error_type"],
            registry=self.registry
        )

        self.error_rate = Gauge(
            f"{ns}_error_rate",
            "Current error rate (errors per minute)",
            ["component"],
            registry=self.registry
        )

        # Business metrics - User activity
        self.api_keys_active = Gauge(
            f"{ns}_api_keys_active",
            "Number of active API keys",
            registry=self.registry
        )

        self.api_requests_by_key = Counter(
            f"{ns}_api_requests_by_key_total",
            "Total API requests per API key",
            ["key_id", "endpoint"],
            registry=self.registry
        )

        self.unique_users_daily = Gauge(
            f"{ns}_unique_users_daily",
            "Number of unique API keys used in last 24 hours",
            registry=self.registry
        )

        # Business metrics - Graph growth
        self.graph_entities_daily = Counter(
            f"{ns}_graph_entities_daily_total",
            "Number of entities created per day",
            ["entity_type"],
            registry=self.registry
        )

        self.graph_relationships_daily = Counter(
            f"{ns}_graph_relationships_daily_total",
            "Number of relationships created per day",
            ["relationship_type"],
            registry=self.registry
        )

        self.graph_growth_rate = Gauge(
            f"{ns}_graph_growth_rate",
            "Entities created per hour",
            registry=self.registry
        )

        # Business metrics - Cost efficiency
        self.cost_efficiency_entities_per_dollar = Gauge(
            f"{ns}_cost_efficiency_entities_per_dollar",
            "Number of entities created per dollar spent",
            registry=self.registry
        )

        self.cost_efficiency_sessions_per_dollar = Gauge(
            f"{ns}_cost_efficiency_sessions_per_dollar",
            "Number of sessions processed per dollar spent",
            registry=self.registry
        )

        # Business metrics - Feature usage
        self.endpoint_usage_total = Counter(
            f"{ns}_endpoint_usage_total",
            "Total requests per API endpoint",
            ["endpoint", "method"],
            registry=self.registry
        )

        self.query_types_total = Counter(
            f"{ns}_query_types_total",
            "Total queries by type",
            ["query_type"],
            registry=self.registry
        )

        self.rag_queries_total = Counter(
            f"{ns}_rag_queries_total",
            "Total RAG queries executed",
            registry=self.registry
        )

        self.hybrid_searches_total = Counter(
            f"{ns}_hybrid_searches_total",
            "Total hybrid searches executed",
            registry=self.registry
        )

        # System metrics
        self.system_memory_bytes = Gauge(
            f"{ns}_system_memory_bytes",
            "System memory usage in bytes",
            ["type"],
            registry=self.registry
        )

        self.system_cpu_percent = Gauge(
            f"{ns}_system_cpu_percent",
            "System CPU usage percentage",
            registry=self.registry
        )

        self.system_disk_bytes = Gauge(
            f"{ns}_system_disk_bytes",
            "System disk usage in bytes",
            ["type", "mount_point"],
            registry=self.registry
        )

        self.process_uptime_seconds = Gauge(
            f"{ns}_process_uptime_seconds",
            "Process uptime in seconds",
            registry=self.registry
        )

        # Application metrics
        self.app_sessions_active = Gauge(
            f"{ns}_sessions_active",
            "Number of currently active sessions",
            registry=self.registry
        )

        self.app_sessions_queue_size = Gauge(
            f"{ns}_sessions_queue_size",
            "Number of sessions waiting to be processed",
            registry=self.registry
        )

    def start_collection(self) -> None:
        """Start metrics collection and HTTP server."""
        if not self.config.enabled:
            logger.info("Metrics collection disabled")
            return

        try:
            # Start HTTP server for Prometheus scraping
            start_http_server(
                self.config.port,
                addr=self.config.host,
                registry=self.registry
            )
            logger.info(
                "Metrics HTTP server started",
                host=self.config.host,
                port=self.config.port,
                metrics_path=self.config.metrics_path
            )

            # Start system metrics collection thread
            self._system_metrics_thread = threading.Thread(
                target=self._collect_system_metrics,
                daemon=True,
                name="system-metrics"
            )
            self._system_metrics_thread.start()
            logger.info("System metrics collection started")

        except Exception as exc:
            logger.error(
                "Failed to start metrics collection",
                error=str(exc),
                error_type=type(exc).__name__
            )

    def stop_collection(self) -> None:
        """Stop metrics collection."""
        self._stop_event.set()
        if self._system_metrics_thread:
            self._system_metrics_thread.join(timeout=5.0)
        logger.info("Metrics collection stopped")

    def _collect_system_metrics(self) -> None:
        """Collect system metrics periodically."""
        while not self._stop_event.is_set():
            try:
                # Memory metrics
                memory = psutil.virtual_memory()
                self.system_memory_bytes.labels(type="available").set(memory.available)
                self.system_memory_bytes.labels(type="used").set(memory.used)
                self.system_memory_bytes.labels(type="total").set(memory.total)

                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                self.system_cpu_percent.set(cpu_percent)

                # Disk metrics
                for partition in psutil.disk_partitions():
                    try:
                        disk = psutil.disk_usage(partition.mountpoint)
                        self.system_disk_bytes.labels(
                            type="used",
                            mount_point=partition.mountpoint
                        ).set(disk.used)
                        self.system_disk_bytes.labels(
                            type="free",
                            mount_point=partition.mountpoint
                        ).set(disk.free)
                        self.system_disk_bytes.labels(
                            type="total",
                            mount_point=partition.mountpoint
                        ).set(disk.total)
                    except (OSError, PermissionError):
                        # Skip inaccessible partitions
                        continue

                # Process uptime
                uptime = (datetime.now(tz=UTC) - self.start_time).total_seconds()
                self.process_uptime_seconds.set(uptime)

            except Exception as exc:
                logger.warning(
                    "Error collecting system metrics",
                    error=str(exc),
                    error_type=type(exc).__name__
                )

            # Wait for next collection or stop event
            self._stop_event.wait(self.config.collection_interval)

    def get_metrics_text(self) -> str:
        """Get Prometheus metrics as text."""
        if not self.config.enabled:
            return ""
        return generate_latest(self.registry).decode("utf-8")

    # Pipeline metrics methods
    def record_session_processed(self, project: str, status: str = "success") -> None:
        """Record a processed session."""
        if self.config.enabled:
            self.pipeline_sessions_total.labels(project=project, status=status).inc()

    @contextmanager
    def time_pipeline_processing(self, project: str):
        """Context manager for timing pipeline processing."""
        if self.config.enabled:
            with self.pipeline_processing_time.labels(project=project).time():
                yield
        else:
            yield

    def record_message_processed(self) -> None:
        """Record a processed message."""
        if self.config.enabled:
            self.pipeline_messages_processed.inc()

    def record_tokens_processed(self, count: int) -> None:
        """Record processed tokens."""
        if self.config.enabled:
            self.pipeline_tokens_processed.inc(count)

    # Database metrics methods
    def record_node_created(self, node_type: str) -> None:
        """Record a database node creation."""
        if self.config.enabled:
            self.db_nodes_created.labels(node_type=node_type).inc()

    def record_relationship_created(self, relationship_type: str) -> None:
        """Record a database relationship creation."""
        if self.config.enabled:
            self.db_relationships_created.labels(relationship_type=relationship_type).inc()

    @contextmanager
    def time_db_query(self, operation: str):
        """Context manager for timing database queries."""
        if self.config.enabled:
            with self.db_query_duration.labels(operation=operation).time():
                yield
        else:
            yield

    # Extraction metrics methods
    def record_extraction_request(self, method: str, model: str | None = None) -> None:
        """Record an extraction request."""
        if self.config.enabled:
            self.extraction_requests_total.labels(
                method=method,
                model=model or "unknown"
            ).inc()

    @contextmanager
    def time_extraction(self, method: str):
        """Context manager for timing extraction."""
        if self.config.enabled:
            with self.extraction_duration.labels(method=method).time():
                yield
        else:
            yield

    def record_entity_extracted(self, entity_type: str) -> None:
        """Record an extracted entity."""
        if self.config.enabled:
            self.extraction_entities_created.labels(entity_type=entity_type).inc()

    def record_relationship_extracted(self, relationship_type: str) -> None:
        """Record an extracted relationship."""
        if self.config.enabled:
            self.extraction_relationships_created.labels(relationship_type=relationship_type).inc()

    # Cost metrics methods
    def record_cost(self, amount_usd: float, model: str, operation: str) -> None:
        """Record incurred cost."""
        if self.config.enabled:
            self.cost_total_usd.labels(model=model, operation=operation).inc(amount_usd)

    def record_session_cost(self, cost_usd: float) -> None:
        """Record cost per session."""
        if self.config.enabled:
            self.cost_per_session.observe(cost_usd)

    # Error metrics methods
    def record_error(self, component: str, error_type: str) -> None:
        """Record an error occurrence."""
        if self.config.enabled:
            self.errors_total.labels(component=component, error_type=error_type).inc()

            # Update error counts for rate calculation
            key = f"{component}:{error_type}"
            self.error_counts[key] = self.error_counts.get(key, 0) + 1

    def update_error_rate(self, component: str, rate: float) -> None:
        """Update error rate for a component."""
        if self.config.enabled:
            self.error_rate.labels(component=component).set(rate)

    # Application metrics methods
    def update_active_sessions(self, count: int) -> None:
        """Update number of active sessions."""
        if self.config.enabled:
            self.app_sessions_active.set(count)

    def update_queue_size(self, size: int) -> None:
        """Update session queue size."""
        if self.config.enabled:
            self.app_sessions_queue_size.set(size)

    def update_db_connections(self, count: int) -> None:
        """Update active database connections."""
        if self.config.enabled:
            self.db_connections_active.set(count)


def init_metrics(settings: AtlasSettings) -> AtlasMetrics:
    """Initialize metrics from settings."""
    config = MetricsConfig(
        enabled=settings.enable_metrics,
        host=settings.metrics_host,
        port=settings.metrics_port,
        metrics_path=settings.metrics_path,
        health_path=settings.health_path,
        status_path=settings.status_path,
        collection_interval=settings.metrics_collection_interval,
        namespace=settings.prometheus_namespace
    )

    metrics = AtlasMetrics.get_instance(config)

    if settings.enable_metrics:
        metrics.start_collection()

    return metrics