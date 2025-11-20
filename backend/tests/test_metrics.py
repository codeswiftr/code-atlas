"""Tests for metrics collection system."""

from __future__ import annotations

import json
import time
from unittest.mock import Mock, patch

import pytest
from prometheus_client import CollectorRegistry, REGISTRY

from code_atlas.config import AtlasSettings
from code_atlas.metrics import AtlasMetrics, MetricsConfig, init_metrics


class TestMetricsConfig:
    """Test metrics configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MetricsConfig()
        assert config.enabled is False
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.metrics_path == "/metrics"
        assert config.health_path == "/health"
        assert config.status_path == "/status"
        assert config.collection_interval == 30
        assert config.namespace == "code_atlas"

    def test_config_from_settings(self) -> None:
        """Test creating config from AtlasSettings."""
        settings = AtlasSettings(
            enable_metrics=True,
            metrics_host="127.0.0.1",
            metrics_port=9090,
            metrics_path="/custom-metrics",
            prometheus_namespace="custom_atlas"
        )

        config = MetricsConfig(
            enabled=settings.enable_metrics,
            host=settings.metrics_host,
            port=settings.metrics_port,
            metrics_path=settings.metrics_path,
            namespace=settings.prometheus_namespace
        )

        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 9090
        assert config.metrics_path == "/custom-metrics"
        assert config.namespace == "custom_atlas"


class TestAtlasMetrics:
    """Test AtlasMetrics class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Clear any existing metrics
        REGISTRY._collector_to_names.clear()
        REGISTRY._names_to_collectors.clear()

        self.config = MetricsConfig(enabled=True, namespace="test_atlas")
        self.metrics = AtlasMetrics(config)

    def teardown_method(self) -> None:
        """Clean up test fixtures."""
        if self.metrics:
            self.metrics.stop_collection()

    def test_singleton_pattern(self) -> None:
        """Test that AtlasMetrics follows singleton pattern."""
        metrics1 = AtlasMetrics.get_instance(self.config)
        metrics2 = AtlasMetrics.get_instance()
        assert metrics1 is metrics2

    def test_metric_initialization(self) -> None:
        """Test that all Prometheus metrics are properly initialized."""
        # Check that counters exist
        assert hasattr(self.metrics, 'pipeline_sessions_total')
        assert hasattr(self.metrics, 'db_nodes_created')
        assert hasattr(self.metrics, 'extraction_requests_total')
        assert hasattr(self.metrics, 'cost_total_usd')
        assert hasattr(self.metrics, 'errors_total')

        # Check that gauges exist
        assert hasattr(self.metrics, 'system_memory_bytes')
        assert hasattr(self.metrics, 'app_sessions_active')

        # Check that histograms exist
        assert hasattr(self.metrics, 'pipeline_processing_time')
        assert hasattr(self.metrics, 'cost_per_session')

    def test_pipeline_metrics(self) -> None:
        """Test pipeline-related metrics."""
        # Test session processing
        self.metrics.record_session_processed("test_project", "success")
        self.metrics.record_session_processed("test_project", "failed")

        # Test message and token processing
        self.metrics.record_message_processed()
        self.metrics.record_tokens_processed(1000)

        # Test pipeline timing
        with self.metrics.time_pipeline_processing("test_project"):
            time.sleep(0.01)

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_pipeline_sessions_total" in output
        assert "test_atlas_pipeline_messages_total" in output
        assert "test_atlas_pipeline_tokens_total" in output
        assert "test_atlas_pipeline_processing_seconds" in output

    def test_database_metrics(self) -> None:
        """Test database-related metrics."""
        # Test node and relationship creation
        self.metrics.record_node_created("File")
        self.metrics.record_node_created("Concept")
        self.metrics.record_relationship_created("RELATED_TO")

        # Test query timing
        with self.metrics.time_db_query("select"):
            time.sleep(0.01)

        # Test active connections
        self.metrics.update_db_connections(5)

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_db_nodes_created_total" in output
        assert "test_atlas_db_relationships_created_total" in output
        assert "test_atlas_db_query_seconds" in output
        assert "test_atlas_db_connections_active" in output

    def test_extraction_metrics(self) -> None:
        """Test extraction-related metrics."""
        # Test extraction requests
        self.metrics.record_extraction_request("llm", "claude-3-sonnet")
        self.metrics.record_extraction_request("heuristic", "heuristic")

        # Test extraction timing
        with self.metrics.time_extraction("llm"):
            time.sleep(0.01)

        # Test entity and relationship extraction
        self.metrics.record_entity_extracted("file")
        self.metrics.record_entity_extracted("concept")
        self.metrics.record_relationship_extracted("MENTIONS")

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_extraction_requests_total" in output
        assert "test_atlas_extraction_seconds" in output
        assert "test_atlas_extraction_entities_created_total" in output
        assert "test_atlas_extraction_relationships_created_total" in output

    def test_cost_metrics(self) -> None:
        """Test cost-related metrics."""
        # Test cost recording
        self.metrics.record_cost(0.01, "claude-3-sonnet", "extraction")
        self.metrics.record_cost(0.005, "claude-3-sonnet", "api_call")

        # Test session cost histogram
        self.metrics.record_session_cost(0.015)
        self.metrics.record_session_cost(0.025)

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_cost_total_usd" in output
        assert "test_atlas_cost_per_session_usd" in output

    def test_error_metrics(self) -> None:
        """Test error-related metrics."""
        # Test error recording
        self.metrics.record_error("pipeline", "ValueError")
        self.metrics.record_error("database", "ConnectionError")
        self.metrics.record_error("extraction", "APIError")

        # Test error rate
        self.metrics.update_error_rate("pipeline", 0.1)
        self.metrics.update_error_rate("database", 0.05)

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_errors_total" in output
        assert "test_atlas_error_rate" in output

    def test_application_metrics(self) -> None:
        """Test application-level metrics."""
        # Test active sessions and queue size
        self.metrics.update_active_sessions(3)
        self.metrics.update_queue_size(10)

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_sessions_active" in output
        assert "test_atlas_sessions_queue_size" in output

    @patch('code_atlas.metrics.psutil')
    def test_system_metrics_collection(self, mock_psutil) -> None:
        """Test system metrics collection."""
        # Mock psutil values
        mock_memory = Mock()
        mock_memory.available = 1000000000
        mock_memory.used = 2000000000
        mock_memory.total = 4000000000
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_psutil.cpu_percent.return_value = 50.0

        mock_disk = Mock()
        mock_disk.used = 5000000000
        mock_disk.free = 5000000000
        mock_disk.total = 10000000000
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.disk_partitions.return_value = [
            Mock(mountpoint="/")
        ]

        # Collect metrics
        self.metrics._collect_system_metrics()

        # Verify metrics are recorded
        output = self.metrics.get_metrics_text()
        assert "test_atlas_system_memory_bytes" in output
        assert "test_atlas_system_cpu_percent" in output
        assert "test_atlas_system_disk_bytes" in output

    def test_metrics_disabled(self) -> None:
        """Test behavior when metrics are disabled."""
        disabled_config = MetricsConfig(enabled=False)
        disabled_metrics = AtlasMetrics(disabled_config)

        # All metric operations should be no-ops
        disabled_metrics.record_session_processed("test", "success")
        disabled_metrics.record_cost(0.01, "model", "operation")
        disabled_metrics.record_error("component", "ErrorType")

        # Should return empty string
        output = disabled_metrics.get_metrics_text()
        assert output == ""

    def test_start_stop_collection(self) -> None:
        """Test starting and stopping metrics collection."""
        # Test start collection
        self.metrics.start_collection()
        assert self.metrics._system_metrics_thread is not None
        assert self.metrics._system_metrics_thread.is_alive()

        # Test stop collection
        self.metrics.stop_collection()
        assert self.metrics._stop_event.is_set()

    @patch('code_atlas.metrics.start_http_server')
    def test_http_server_start(self, mock_start_server) -> None:
        """Test HTTP server startup."""
        self.metrics.start_collection()
        mock_start_server.assert_called_once_with(
            self.config.port,
            addr=self.config.host,
            registry=self.metrics.registry
        )

    def test_init_metrics_function(self) -> None:
        """Test the init_metrics helper function."""
        settings = AtlasSettings(
            enable_metrics=True,
            metrics_host="127.0.0.1",
            metrics_port=9090,
            prometheus_namespace="test_init"
        )

        metrics = init_metrics(settings)

        assert metrics is not None
        assert metrics.config.enabled is True
        assert metrics.config.host == "127.0.0.1"
        assert metrics.config.port == 9090
        assert metrics.config.namespace == "test_init"

    def test_context_managers(self) -> None:
        """Test timing context managers."""
        # Test pipeline timing context manager
        with self.metrics.time_pipeline_processing("test_project"):
            time.sleep(0.01)

        # Test database query timing context manager
        with self.metrics.time_db_query("test_query"):
            time.sleep(0.01)

        # Test extraction timing context manager
        with self.metrics.time_extraction("llm"):
            time.sleep(0.01)

        # Verify histogram metrics were updated
        output = self.metrics.get_metrics_text()
        assert "test_atlas_pipeline_processing_seconds" in output
        assert "test_atlas_db_query_seconds" in output
        assert "test_atlas_extraction_seconds" in output

    def test_metric_labels(self) -> None:
        """Test that metrics use correct labels."""
        # Test various metrics with different labels
        self.metrics.record_session_processed("project1", "success")
        self.metrics.record_session_processed("project2", "failed")
        self.metrics.record_node_created("File")
        self.metrics.record_node_created("Concept")
        self.metrics.record_error("pipeline", "ValueError")
        self.metrics.record_error("database", "ConnectionError")

        output = self.metrics.get_metrics_text()

        # Check that labels are present
        assert 'project="project1"' in output
        assert 'project="project2"' in output
        assert 'status="success"' in output
        assert 'status="failed"' in output
        assert 'node_type="File"' in output
        assert 'node_type="Concept"' in output
        assert 'component="pipeline"' in output
        assert 'component="database"' in output
        assert 'error_type="ValueError"' in output
        assert 'error_type="ConnectionError"' in output


class TestMetricsIntegration:
    """Integration tests for metrics with other components."""

    def test_metrics_with_pipeline_runner(self) -> None:
        """Test metrics integration with PipelineRunner."""
        from code_atlas.pipeline import PipelineRunner
        from code_atlas.session_discovery import SessionDiscovery
        from code_atlas.insight_extractor import InsightExtractor
        from code_atlas.graph_populator import GraphPopulator

        # Set up settings with metrics enabled
        settings = AtlasSettings(enable_metrics=True)

        # Create components
        discovery = Mock(spec=SessionDiscovery)
        extractor = InsightExtractor(use_llm=False)  # Use heuristic to avoid API calls
        populator = GraphPopulator(dry_run=True)

        # Mock session discovery
        mock_session = Mock()
        mock_session.session_id = "test_session"
        mock_session.project = "test_project"
        mock_session.size_bytes = 1024
        mock_session.modified_at = Mock()

        discovery.discover.return_value = [mock_session]

        # Create runner with metrics
        runner = PipelineRunner(
            discovery, extractor, populator, settings=settings
        )

        # Verify metrics were initialized
        assert runner.metrics is not None
        assert runner.metrics.config.enabled is True

    def test_metrics_with_graph_populator(self) -> None:
        """Test metrics integration with GraphPopulator."""
        from code_atlas.graph_populator import GraphPopulator
        from code_atlas.insight_extractor import Entity, ExtractionResult
        from code_atlas.models import ParsedSession

        # Create metrics instance
        metrics = AtlasMetrics(MetricsConfig(enabled=True))

        # Create populator with metrics
        populator = GraphPopulator(dry_run=True, metrics=metrics)

        # Create test data
        mock_session = Mock(spec=ParsedSession)
        mock_session.metadata.session_id = "test_session"
        mock_session.metadata.project = "test_project"
        mock_session.metadata.size_bytes = 1024
        mock_session.metadata.modified_at = Mock()

        extraction = ExtractionResult(
            entities=[
                Entity(type="file", name="test.py"),
                Entity(type="concept", name="algorithms")
            ],
            relationships=[
                Mock(type="RELATED_TO", source="test.py", target="algorithms")
            ],
            insights=["Test insight"]
        )

        # Run upsert (should record metrics)
        populator.upsert(mock_session, extraction)

        # Verify metrics were recorded
        output = metrics.get_metrics_text()
        assert "test_atlas_db_nodes_created_total" in output
        assert "test_atlas_db_relationships_created_total" in output

    def test_metrics_with_insight_extractor(self) -> None:
        """Test metrics integration with InsightExtractor."""
        from code_atlas.insight_extractor import InsightExtractor
        from code_atlas.models import ParsedSession

        # Create metrics instance
        metrics = AtlasMetrics(MetricsConfig(enabled=True))

        # Create extractor with metrics
        extractor = InsightExtractor(use_llm=False)
        extractor.metrics = metrics

        # Create test session
        mock_session = Mock(spec=ParsedSession)
        mock_session.metadata.session_id = "test_session"
        mock_session.messages = []
        mock_session.referenced_files = ["test.py"]
        mock_session.total_tokens = 1000

        # Run extraction (should record metrics)
        result = extractor.extract(mock_session)

        # Verify metrics were recorded
        output = metrics.get_metrics_text()
        assert "test_atlas_extraction_requests_total" in output
        assert "test_atlas_extraction_seconds" in output
        assert "test_atlas_extraction_entities_created_total" in output