"""Unit tests for WebSocket real-time job updates."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from code_atlas.job_store import ProcessingJob
from code_atlas.websocket import (
    ConnectionManager,
    get_connection_manager,
    websocket_job_updates,
)


@pytest.fixture
def mock_job_store():
    """Create a mock job store."""
    job_store = MagicMock()
    return job_store


@pytest.fixture
def connection_manager(mock_job_store):
    """Create a ConnectionManager instance with mocked dependencies."""
    with patch("code_atlas.websocket.get_job_store", return_value=mock_job_store):
        manager = ConnectionManager()
        return manager


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(
        self, connection_manager, mock_websocket, mock_job_store
    ):
        """Test that connect accepts the WebSocket connection."""
        job_id = "test-job-123"
        mock_job_store.get.return_value = None

        await connection_manager.connect(mock_websocket, job_id)

        mock_websocket.accept.assert_called_once()
        assert job_id in connection_manager.active_connections
        assert connection_manager.active_connections[job_id] == mock_websocket

    @pytest.mark.asyncio
    async def test_connect_sends_initial_status(
        self, connection_manager, mock_websocket, mock_job_store
    ):
        """Test that connect sends initial job status."""
        job_id = "test-job-123"
        mock_job = MagicMock(spec=ProcessingJob)
        mock_job.dict.return_value = {
            "id": job_id,
            "status": "running",
            "progress": 0.5,
        }
        mock_job_store.get.return_value = mock_job

        await connection_manager.connect(mock_websocket, job_id)

        mock_websocket.send_json.assert_called_once_with(
            {
                "type": "status",
                "job": mock_job.dict.return_value,
            }
        )

    def test_disconnect_removes_connection(self, connection_manager, mock_websocket):
        """Test that disconnect removes the WebSocket connection."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        connection_manager.disconnect(job_id)

        assert job_id not in connection_manager.active_connections

    def test_disconnect_handles_missing_connection(self, connection_manager):
        """Test that disconnect handles non-existent connections gracefully."""
        job_id = "nonexistent-job"

        # Should not raise an exception
        connection_manager.disconnect(job_id)

        assert job_id not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_send_job_status_sends_to_connected_client(
        self, connection_manager, mock_websocket, mock_job_store
    ):
        """Test sending job status to connected client."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        mock_job = MagicMock(spec=ProcessingJob)
        mock_job.dict.return_value = {
            "id": job_id,
            "status": "completed",
            "progress": 1.0,
        }
        mock_job_store.get.return_value = mock_job

        await connection_manager.send_job_status(job_id)

        mock_websocket.send_json.assert_called_once_with(
            {
                "type": "status",
                "job": mock_job.dict.return_value,
            }
        )

    @pytest.mark.asyncio
    async def test_send_job_status_ignores_disconnected_client(
        self, connection_manager, mock_job_store
    ):
        """Test that send_job_status ignores disconnected clients."""
        job_id = "disconnected-job"
        mock_job_store.get.return_value = None

        # Should not raise an exception
        await connection_manager.send_job_status(job_id)

        # No job store call should be made
        mock_job_store.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_job_status_handles_send_error(
        self, connection_manager, mock_websocket, mock_job_store
    ):
        """Test that send_job_status handles send errors gracefully."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        mock_job = MagicMock(spec=ProcessingJob)
        mock_job.dict.return_value = {"id": job_id}
        mock_job_store.get.return_value = mock_job

        # Simulate send error
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        await connection_manager.send_job_status(job_id)

        # Connection should be removed after error
        assert job_id not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_job_update_sends_to_connected_client(
        self, connection_manager, mock_websocket
    ):
        """Test broadcasting job updates to connected client."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        job_data = {
            "id": job_id,
            "status": "running",
            "progress": 0.75,
            "message": "Processing files...",
        }

        await connection_manager.broadcast_job_update(job_id, job_data)

        mock_websocket.send_json.assert_called_once_with(
            {
                "type": "update",
                "job": job_data,
            }
        )

    @pytest.mark.asyncio
    async def test_broadcast_job_update_handles_send_error(
        self, connection_manager, mock_websocket
    ):
        """Test that broadcast_job_update handles send errors."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        # Simulate send error
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        await connection_manager.broadcast_job_update(job_id, {"id": job_id})

        # Connection should be removed after error
        assert job_id not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_send_error_sends_to_connected_client(self, connection_manager, mock_websocket):
        """Test sending error messages to connected client."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        error_msg = "Failed to process session"

        await connection_manager.send_error(job_id, error_msg)

        mock_websocket.send_json.assert_called_once_with(
            {
                "type": "error",
                "error": error_msg,
            }
        )

    @pytest.mark.asyncio
    async def test_send_error_handles_send_failure(self, connection_manager, mock_websocket):
        """Test that send_error handles send failures gracefully."""
        job_id = "test-job-123"
        connection_manager.active_connections[job_id] = mock_websocket

        # Simulate send error
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        await connection_manager.send_error(job_id, "Test error")

        # Connection should be removed after error
        assert job_id not in connection_manager.active_connections


class TestWebSocketEndpoint:
    """Tests for websocket_job_updates endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_connects_and_handles_ping(self, mock_websocket):
        """Test WebSocket connection and ping/pong handling."""
        job_id = "test-job-123"

        # Setup message sequence: ping, then disconnect
        mock_websocket.receive_text.side_effect = [
            '{"type": "ping"}',
            WebSocketDisconnect(),
        ]

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Verify connection lifecycle
            mock_manager.connect.assert_called_once_with(mock_websocket, job_id)
            mock_manager.disconnect.assert_called_once_with(job_id)

            # Verify pong response
            mock_websocket.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_websocket_handles_subscribe_message(self, mock_websocket):
        """Test WebSocket handles subscribe messages."""
        job_id = "test-job-123"

        # Setup message sequence: subscribe, then disconnect
        mock_websocket.receive_text.side_effect = [
            '{"type": "subscribe"}',
            WebSocketDisconnect(),
        ]

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Connection should be established and closed
            mock_manager.connect.assert_called_once()
            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_handles_unknown_message_type(self, mock_websocket):
        """Test WebSocket handles unknown message types."""
        job_id = "test-job-123"

        # Setup message sequence: unknown type, then disconnect
        mock_websocket.receive_text.side_effect = [
            '{"type": "unknown"}',
            WebSocketDisconnect(),
        ]

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Should handle gracefully
            mock_manager.connect.assert_called_once()
            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_handles_invalid_json(self, mock_websocket):
        """Test WebSocket handles invalid JSON messages."""
        job_id = "test-job-123"

        # Setup message sequence: invalid JSON, then disconnect
        mock_websocket.receive_text.side_effect = [
            "invalid json",
            WebSocketDisconnect(),
        ]

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Should disconnect after error
            mock_manager.disconnect.assert_called_once_with(job_id)

    @pytest.mark.asyncio
    async def test_websocket_handles_connection_error(self, mock_websocket):
        """Test WebSocket handles connection errors."""
        job_id = "test-job-123"

        # Setup to raise error during message receive
        mock_websocket.receive_text.side_effect = Exception("Network error")

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Should connect then disconnect after error
            mock_manager.connect.assert_called_once_with(mock_websocket, job_id)
            mock_manager.disconnect.assert_called_once_with(job_id)

    @pytest.mark.asyncio
    async def test_websocket_disconnects_on_client_disconnect(self, mock_websocket):
        """Test WebSocket disconnects when client disconnects."""
        job_id = "test-job-123"

        # Simulate immediate disconnect
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        with patch("code_atlas.websocket.connection_manager") as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()

            await websocket_job_updates(mock_websocket, job_id)

            # Should disconnect gracefully
            mock_manager.disconnect.assert_called_once_with(job_id)


class TestGetConnectionManager:
    """Tests for get_connection_manager function."""

    def test_get_connection_manager_returns_singleton(self):
        """Test that get_connection_manager returns the global instance."""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2
        assert isinstance(manager1, ConnectionManager)
