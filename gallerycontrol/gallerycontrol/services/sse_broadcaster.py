# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Server-Sent Events broadcaster for real-time poll status updates."""

import asyncio
import json
import logging
import time
from datetime import datetime

from gallerycontrol.utils.datetime_utils import utc_now
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
            "timestamp": utc_now().isoformat(),
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
            "timestamp": utc_now().isoformat(),
        })

    async def send_config_change(self, monitoring_config: dict):
        """Broadcast config change event."""
        logger.info(f"Broadcasting config change: {monitoring_config}")
        await self.broadcast({
            "type": "config_change",
            "monitoring": monitoring_config,
            "timestamp": utc_now().isoformat(),
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
            "timestamp": utc_now().isoformat(),
        })

    async def send_initial_state(self, monitoring_config: dict) -> str:
        """Generate initial connection event as SSE string."""
        event = {
            "type": "connected",
            "monitoring": monitoring_config,
            "timestamp": utc_now().isoformat(),
        }
        return f"data: {json.dumps(event)}\n\n"

    async def send_protection_status(
        self,
        artwork_id: str,
        status: dict,
    ):
        """Broadcast protection status update event.

        Sent when protection state changes (start, stop, budget update).
        """
        logger.debug(f"Broadcasting protection_status for artwork {artwork_id}")
        await self.broadcast({
            "type": "protection_status",
            "artwork_id": artwork_id,
            "status": status,
            "timestamp": utc_now().isoformat(),
        })

    async def send_protection_forced_off(
        self,
        artwork_id: str,
        reason: str,
    ):
        """Broadcast protection forced off event.

        Sent when an artwork is auto-stopped due to protection rules.
        """
        logger.warning(f"Broadcasting protection_forced_off for artwork {artwork_id}: {reason}")
        await self.broadcast({
            "type": "protection_forced_off",
            "artwork_id": artwork_id,
            "reason": reason,
            "timestamp": utc_now().isoformat(),
        })

    async def send_accepting_triggers_change(
        self,
        artwork_id: str,
        accepting: bool,
    ):
        """Broadcast accepting_triggers gate change event.

        Sent when artwork's accepting_triggers flag changes (ON/OFF via web/scheduler).
        """
        logger.info(f"Broadcasting accepting_triggers change for artwork {artwork_id}: {accepting}")
        await self.broadcast({
            "type": "accepting_triggers_change",
            "artwork_id": artwork_id,
            "accepting_triggers": accepting,
            "timestamp": utc_now().isoformat(),
        })

    async def send_satellite_pending_count(self, count: int):
        """Broadcast pending satellite count change.

        Sent when satellites are added/removed from pending queue.
        """
        await self.broadcast({
            "type": "satellite_pending_count",
            "count": count,
            "timestamp": utc_now().isoformat(),
        })

    async def send_satellite_status(
        self,
        satellite_id: str,
        name: str,
        is_connected: bool,
    ):
        """Broadcast satellite connection status change.

        Sent when a satellite connects or disconnects.
        """
        logger.info(
            f"Broadcasting satellite status: {name} ({'connected' if is_connected else 'disconnected'})"
        )
        await self.broadcast({
            "type": "satellite_status",
            "satellite_id": satellite_id,
            "name": name,
            "is_connected": is_connected,
            "timestamp": utc_now().isoformat(),
        })
