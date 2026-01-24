"""Server-Sent Events broadcaster for real-time poll status updates."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Broadcasts poll events to connected SSE clients."""

    def __init__(self):
        self._clients: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None

    async def start(self):
        """Start the heartbeat background task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("SSE Broadcaster started")

    async def stop(self):
        """Stop the heartbeat background task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("SSE Broadcaster stopped")

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to keep connections alive."""
        while True:
            await asyncio.sleep(30)  # Heartbeat every 30 seconds
            await self._send_heartbeat()

    async def _send_heartbeat(self):
        """Send heartbeat to all clients."""
        await self.broadcast({
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_count": len(self._clients),
        })

    @property
    def client_count(self) -> int:
        """Return number of connected clients."""
        return len(self._clients)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to SSE events.

        Returns async generator of SSE-formatted strings.
        """
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._clients.append(queue)
            logger.info(f"SSE client connected (total: {len(self._clients)})")

        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                if queue in self._clients:
                    self._clients.remove(queue)
                logger.info(f"SSE client disconnected (total: {len(self._clients)})")

    async def broadcast(self, event: dict):
        """Send event to all connected clients."""
        async with self._lock:
            if not self._clients:
                return
            for queue in self._clients:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("SSE client queue full, dropping event")

    async def send_poll_complete(
        self,
        device_id: str,
        success: bool,
        state: int,
        duration_ms: int,
        next_poll_at: datetime,
        poll_interval: int,
    ):
        """Broadcast poll completion event."""
        await self.broadcast({
            "type": "poll_complete",
            "device_id": device_id,
            "success": success,
            "state": state,
            "duration_ms": duration_ms,
            "next_poll_at": next_poll_at.isoformat(),
            "poll_interval": poll_interval,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def send_config_change(self, monitoring_config: dict):
        """Broadcast config change event."""
        logger.info(f"Broadcasting config change: {monitoring_config}")
        await self.broadcast({
            "type": "config_change",
            "monitoring": monitoring_config,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def send_verification_change(
        self,
        device_id: str,
        started: bool,
        poll_interval: int,
    ):
        """Broadcast verification mode change event."""
        event_type = "verification_start" if started else "verification_end"
        logger.debug(f"Broadcasting {event_type} for device {device_id}")
        await self.broadcast({
            "type": event_type,
            "device_id": device_id,
            "poll_interval": poll_interval,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def send_initial_state(self, monitoring_config: dict) -> str:
        """Generate initial connection event as SSE string."""
        event = {
            "type": "connected",
            "monitoring": monitoring_config,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return f"data: {json.dumps(event)}\n\n"
