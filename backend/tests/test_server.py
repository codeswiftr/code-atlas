"""Tests for metrics server functionality."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from code_atlas.config import AtlasSettings
from code_atlas.metrics import AtlasMetrics
from code_atlas.server import MetricsServer


@pytest.fixture(autouse=True)
def reset_metrics_singleton():
    """Reset AtlasMetrics singleton before and after each test."""
    AtlasMetrics._instance = None
    yield
    AtlasMetrics._instance = None


class TestMetricsServer:
    """Test MetricsServer class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.settings = AtlasSettings(
            enable_metrics=True,
            metrics_host="127.0.0.1",
            metrics_port=8080,
            metrics_path="/metrics",
            health_path="/health",
            status_path="/status",
            prometheus_namespace="test_server"
        )
        self.server = MetricsServer(self.settings)
        self.client = TestClient(self.server.app)

    def teardown_method(self) -> None:
        """Clean up test fixtures."""
        if hasattr(self.server, 'metrics') and self.server.metrics:
            self.server.metrics.stop_collection()

    def test_server_initialization(self) -> None:
        """Test server initialization."""
        assert self.server.settings == self.settings
        assert self.server.metrics is not None
        assert self.server.app is not None

    def test_root_endpoint(self) -> None:
        """Test root endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "Code Atlas Metrics Server"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
        assert data["endpoints"]["metrics"] == "/metrics"
        assert data["endpoints"]["health"] == "/health"
        assert data["endpoints"]["status"] == "/status"

    @patch('code_atlas.metrics.AtlasMetrics.get_metrics_text')
    def test_metrics_endpoint_enabled(self, mock_get_metrics) -> None:
        """Test metrics endpoint when enabled."""
        mock_get_metrics.return_value = "# HELP test_metric A test metric\ntest_metric 42"

        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "test_metric 42" in response.text
        mock_get_metrics.assert_called_once()

    def test_metrics_endpoint_disabled(self) -> None:
        """Test metrics endpoint when disabled."""
        disabled_settings = AtlasSettings(enable_metrics=False)
        disabled_server = MetricsServer(disabled_settings)
        disabled_client = TestClient(disabled_server.app)

        response = disabled_client.get("/metrics")
        assert response.status_code == 503
        assert "Metrics collection is disabled" in response.json()["detail"]

    @patch('code_atlas.metrics.AtlasMetrics.get_metrics_text')
    def test_metrics_endpoint_error(self, mock_get_metrics) -> None:
        """Test metrics endpoint error handling."""
        mock_get_metrics.side_effect = Exception("Metrics generation failed")

        response = self.client.get("/metrics")
        assert response.status_code == 500
        assert "Failed to generate metrics" in response.json()["detail"]

    def test_health_endpoint(self) -> None:
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "code-atlas-metrics"

    @patch('code_atlas.server.psutil')
    def test_status_endpoint(self, mock_psutil) -> None:
        """Test detailed status endpoint."""
        # Mock psutil values
        mock_memory = Mock()
        mock_memory.total = 4000000000
        mock_memory.available = 2000000000
        mock_memory.used = 2000000000
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_psutil.cpu_percent.return_value = 25.0

        mock_disk = Mock()
        mock_disk.total = 10000000000
        mock_disk.used = 5000000000
        mock_disk.free = 5000000000
        mock_psutil.disk_usage.return_value = mock_disk

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.memory_info.return_value.rss = 100000000
        mock_process.cpu_percent.return_value = 10.0
        mock_process.num_threads.return_value = 5
        mock_process.create_time.return_value = 1640995200.0  # Fixed timestamp
        mock_psutil.Process.return_value = mock_process

        response = self.client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "code-atlas-metrics"
        assert data["version"] == "1.0.0"
        assert data["metrics_enabled"] is True
        assert "system" in data
        assert "config" in data

        # Check system information
        system = data["system"]
        assert system["cpu_percent"] == 25.0
        assert system["memory"]["total_bytes"] == 4000000000
        assert system["memory"]["available_bytes"] == 2000000000
        assert system["memory"]["used_bytes"] == 2000000000
        assert system["memory"]["percent_used"] == 50.0
        assert system["disk"]["total_bytes"] == 10000000000
        assert system["process"]["pid"] == 12345
        assert system["process"]["memory_rss_bytes"] == 100000000
        assert system["process"]["cpu_percent"] == 10.0
        assert system["process"]["num_threads"] == 5

        # Check config information
        config = data["config"]
        assert config["metrics_host"] == "127.0.0.1"
        assert config["metrics_port"] == 8080
        assert config["metrics_interval"] == 30
        assert config["prometheus_namespace"] == "test_server"

    @patch('code_atlas.server.psutil')
    def test_status_endpoint_error(self, mock_psutil) -> None:
        """Test status endpoint error handling."""
        mock_psutil.virtual_memory.side_effect = Exception("System info failed")

        response = self.client.get("/status")
        assert response.status_code == 500
        assert "Failed to get status" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch('uvicorn.Server')
    @patch('uvicorn.Config')
    async def test_start_method(self, mock_config_class, mock_server_class) -> None:
        """Test async start method."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_server = Mock()
        mock_server.serve = AsyncMock()  # serve() is an async method
        mock_server_class.return_value = mock_server

        # Test start method
        await self.server.start()

        # Verify uvicorn configuration
        mock_config_class.assert_called_once_with(
            app=self.server.app,
            host=self.settings.metrics_host,
            port=self.settings.metrics_port,
            log_level="info",
            access_log=True
        )

        # Verify server was created and started
        mock_server_class.assert_called_once_with(mock_config)
        mock_server.serve.assert_called_once()

    def test_run_method(self) -> None:
        """Test synchronous run method."""
        with patch('code_atlas.server.asyncio.run') as mock_run:
            self.server.run()
            mock_run.assert_called_once()
            # Verify the argument is a coroutine from start()
            args, _ = mock_run.call_args
            assert asyncio.iscoroutine(args[0])

    @pytest.mark.asyncio
    @patch('uvicorn.Server')
    @patch('uvicorn.Config')
    async def test_start_disabled_metrics(self, mock_config_class, mock_server_class) -> None:
        """Test start method when metrics are disabled."""
        disabled_settings = AtlasSettings(enable_metrics=False)
        disabled_server = MetricsServer(disabled_settings)

        # Should not start server when disabled
        await disabled_server.start()

        # uvicorn should not be called
        mock_config_class.assert_not_called()
        mock_server_class.assert_not_called()

    @pytest.mark.asyncio
    @patch('code_atlas.server.signal.signal')
    @patch('uvicorn.Server')
    @patch('uvicorn.Config')
    async def test_signal_handlers(
        self, mock_config_class, mock_server_class, mock_signal_func
    ) -> None:
        """Test signal handler setup."""
        import signal as signal_module

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_server = Mock()
        mock_server.serve = AsyncMock()  # serve() is an async method
        mock_server_class.return_value = mock_server

        await self.server.start()

        # Verify signal handlers were set up (using actual signal constants)
        call_args = [call[0][0] for call in mock_signal_func.call_args_list]
        assert signal_module.SIGTERM in call_args
        assert signal_module.SIGINT in call_args

    @pytest.mark.asyncio
    @patch('uvicorn.Server')
    @patch('uvicorn.Config')
    async def test_server_shutdown_on_signal(self, mock_config_class, mock_server_class) -> None:
        """Test graceful shutdown on signal."""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_server = Mock()
        mock_server.serve = AsyncMock()  # serve() is an async method
        mock_server_class.return_value = mock_server

        # Mock signal handler
        def mock_signal_handler(signum, frame):
            mock_server.should_exit = True

        with patch('code_atlas.server.signal.signal', side_effect=lambda sig, handler: None):
            await self.server.start()

    @pytest.mark.asyncio
    async def test_async_client(self) -> None:
        """Test async client for server endpoints."""
        transport = ASGITransport(app=self.server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            # Test root endpoint
            response = await async_client.get("/")
            assert response.status_code == 200

            data = response.json()
            assert data["service"] == "Code Atlas Metrics Server"

            # Test health endpoint
            response = await async_client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"

    @patch('code_atlas.metrics.AtlasMetrics.get_metrics_text')
    def test_metrics_endpoint_prometheus_format(self, mock_get_metrics) -> None:
        """Test that metrics endpoint returns proper Prometheus format."""
        prometheus_output = """
# HELP test_server_pipeline_sessions_total Total number of sessions processed
# TYPE test_server_pipeline_sessions_total counter
test_server_pipeline_sessions_total{project="test",status="success"} 5.0
# HELP test_server_system_memory_bytes System memory usage in bytes
# TYPE test_server_system_memory_bytes gauge
test_server_system_memory_bytes{type="available"} 2000000000.0
        """.strip()

        mock_get_metrics.return_value = prometheus_output

        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

        # Check for proper Prometheus format
        text = response.text
        assert "# HELP" in text
        assert "# TYPE" in text
        assert "test_server_pipeline_sessions_total" in text
        assert "test_server_system_memory_bytes" in text
        assert '{project="test",status="success"}' in text

    def test_custom_paths(self) -> None:
        """Test server with custom endpoint paths."""
        custom_settings = AtlasSettings(
            enable_metrics=True,
            metrics_path="/custom-metrics",
            health_path="/custom-health",
            status_path="/custom-status"
        )

        custom_server = MetricsServer(custom_settings)
        custom_client = TestClient(custom_server.app)

        # Test custom paths work
        response = custom_client.get("/")
        data = response.json()
        assert data["endpoints"]["metrics"] == "/custom-metrics"
        assert data["endpoints"]["health"] == "/custom-health"
        assert data["endpoints"]["status"] == "/custom-status"

        # Test that custom paths are accessible
        with patch('code_atlas.metrics.AtlasMetrics.get_metrics_text') as mock_metrics:
            mock_metrics.return_value = "# HELP test Test metric\ntest 1"

            response = custom_client.get("/custom-metrics")
            assert response.status_code == 200

        response = custom_client.get("/custom-health")
        assert response.status_code == 200

        response = custom_client.get("/custom-status")
        assert response.status_code == 200

        # Test default paths don't work
        response = custom_client.get("/metrics")
        assert response.status_code == 404

        response = custom_client.get("/health")
        assert response.status_code == 404

        response = custom_client.get("/status")
        assert response.status_code == 404


class TestServerIntegration:
    """Integration tests for server functionality."""

    def test_server_with_real_metrics(self) -> None:
        """Test server with actual metrics collection."""
        settings = AtlasSettings(
            enable_metrics=True,
            metrics_port=8081,  # Use different port to avoid conflicts
            prometheus_namespace="integration_test"
        )

        server = MetricsServer(settings)
        client = TestClient(server.app)

        # Record some metrics
        server.metrics.record_session_processed("test_project", "success")
        server.metrics.record_cost(0.01, "claude-3-sonnet", "extraction")
        server.metrics.record_error("pipeline", "ValueError")

        # Test metrics endpoint
        response = client.get("/metrics")
        assert response.status_code == 200

        text = response.text
        assert "integration_test_pipeline_sessions_total" in text
        assert "integration_test_cost_total_usd" in text
        assert "integration_test_errors_total" in text

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200

        # Test status endpoint
        response = client.get("/status")
        assert response.status_code == 200

        data = response.json()
        assert data["metrics_enabled"] is True
        assert data["config"]["prometheus_namespace"] == "integration_test"

        server.metrics.stop_collection()

    @pytest.mark.asyncio
    async def test_lifecycle_management(self) -> None:
        """Test application lifecycle management."""
        settings = AtlasSettings(enable_metrics=True)
        server = MetricsServer(settings)

        # Test that metrics collection starts/stops during lifespan
        with patch.object(server.metrics, 'start_collection') as mock_start:
            with patch.object(server.metrics, 'stop_collection') as mock_stop:
                # Simulate lifespan events
                async with server.app.router.lifespan_context(server.app):
                    # start_collection should be called on startup
                    mock_start.assert_called_once()

                # stop_collection should be called on shutdown
                mock_stop.assert_called_once()


class TestServerErrorHandling:
    """Test server error handling scenarios."""

    def test_missing_psutil_dependency(self) -> None:
        """Test behavior when psutil is not available."""
        settings = AtlasSettings(enable_metrics=True)
        server = MetricsServer(settings)
        client = TestClient(server.app)

        with patch.dict('sys.modules', {'psutil': None}):
            # This should still work, but status endpoint might fail
            response = client.get("/health")
            assert response.status_code == 200

            response = client.get("/")
            assert response.status_code == 200

    def test_metrics_generation_failure(self) -> None:
        """Test handling of metrics generation failures."""
        settings = AtlasSettings(enable_metrics=True)
        server = MetricsServer(settings)
        client = TestClient(server.app)

        # Mock metrics generation to fail
        with patch.object(server.metrics, 'get_metrics_text', side_effect=Exception("Failed")):
            response = client.get("/metrics")
            assert response.status_code == 500
            assert "Failed to generate metrics" in response.json()["detail"]

    def test_concurrent_requests(self) -> None:
        """Test handling of concurrent requests."""
        import threading

        settings = AtlasSettings(enable_metrics=True)
        server = MetricsServer(settings)
        client = TestClient(server.app)

        # Record some metrics first
        server.metrics.record_session_processed("test", "success")

        results = []
        errors = []

        def make_request():
            try:
                response = client.get("/metrics")
                results.append(response.status_code)
            except Exception as e:
                errors.append(e)

        # Make multiple concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests succeeded
        assert len(errors) == 0
        assert len(results) == 10
        assert all(status == 200 for status in results)

        server.metrics.stop_collection()