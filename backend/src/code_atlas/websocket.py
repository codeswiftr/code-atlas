"""WebSocket support for real-time job updates."""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from .job_store import get_job_store
from .logging_config import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.job_store = get_job_store()

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        """Accept WebSocket connection for specific job."""
        await websocket.accept()
        self.active_connections[job_id] = websocket
        logger.info("WebSocket connected", job_id=job_id)

        # Send initial job status
        await self.send_job_status(job_id)

    def disconnect(self, job_id: str) -> None:
        """Remove WebSocket connection."""
        if job_id in self.active_connections:
            del self.active_connections[job_id]
            logger.info("WebSocket disconnected", job_id=job_id)

    async def send_job_status(self, job_id: str) -> None:
        """Send current job status to connected client."""
        if job_id not in self.active_connections:
            return

        websocket = self.active_connections[job_id]
        job = self.job_store.get(job_id)

        if job:
            try:
                await websocket.send_json({"type": "status", "job": job.dict()})
            except Exception as exc:
                logger.error(
                    "Failed to send job status",
                    job_id=job_id,
                    error=str(exc),
                )
                self.disconnect(job_id)

    async def broadcast_job_update(self, job_id: str, job_data: dict) -> None:
        """Broadcast job update to connected client."""
        if job_id not in self.active_connections:
            return

        websocket = self.active_connections[job_id]

        try:
            await websocket.send_json({"type": "update", "job": job_data})
        except Exception as exc:
            logger.error(
                "Failed to broadcast job update",
                job_id=job_id,
                error=str(exc),
            )
            self.disconnect(job_id)

    async def send_error(self, job_id: str, error: str) -> None:
        """Send error message to connected client."""
        if job_id not in self.active_connections:
            return

        websocket = self.active_connections[job_id]

        try:
            await websocket.send_json({"type": "error", "error": error})
        except Exception as exc:
            logger.error(
                "Failed to send error message",
                job_id=job_id,
                error=str(exc),
            )
            self.disconnect(job_id)


# Global connection manager
connection_manager = ConnectionManager()


async def websocket_job_updates(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job status updates.

    Args:
        websocket: WebSocket connection
        job_id: Job ID to track
    """
    await connection_manager.connect(websocket, job_id)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping, etc.)
                message = await websocket.receive_text()
                data = json.loads(message) if message else {}

                # Handle client messages
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "subscribe":
                    # Client is subscribing to job updates (already handled by connect)
                    pass
                else:
                    logger.warning("Unknown WebSocket message type", message_type=data.get("type"))

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected", job_id=job_id)
                break
            except Exception as exc:
                logger.error(
                    "WebSocket error",
                    job_id=job_id,
                    error=str(exc),
                )
                break

    except Exception as exc:
        logger.error(
            "WebSocket connection error",
            job_id=job_id,
            error=str(exc),
        )
    finally:
        connection_manager.disconnect(job_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return connection_manager
