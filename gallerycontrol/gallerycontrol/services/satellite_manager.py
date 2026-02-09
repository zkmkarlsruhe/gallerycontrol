# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Satellite manager - handles WebSocket connections and command routing for satellites."""

import asyncio
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import UUID, uuid4

from fastapi import WebSocket
from sqlalchemy import select, update

from gallerycontrol.database.models import Satellite
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SatelliteConnection:
    """Represents an active satellite WebSocket connection."""

    satellite_id: UUID
    websocket: WebSocket
    name: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PendingSatellite:
    """Represents a satellite awaiting approval."""

    api_key_hash: str
    websocket: WebSocket
    hostname: Optional[str]
    version: Optional[str]
    connected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PendingCommand:
    """Represents a command awaiting response from satellite."""

    cmd_id: str
    device_id: str
    command: str
    future: asyncio.Future
    sent_at: datetime = field(default_factory=datetime.utcnow)


class SatelliteManager:
    """Manages satellite WebSocket connections and command routing."""

    def __init__(self, db_manager, sse_broadcaster=None):
        self.db_manager = db_manager
        self._sse_broadcaster = sse_broadcaster

        # Active satellite connections (satellite_id -> connection)
        self._connections: Dict[UUID, SatelliteConnection] = {}

        # Pending satellites awaiting approval (api_key_hash -> pending info)
        self._pending_satellites: Dict[str, PendingSatellite] = {}

        # Commands awaiting response (cmd_id -> pending command)
        self._pending_commands: Dict[str, PendingCommand] = {}

        # Lock for connection management
        self._lock = asyncio.Lock()

        # Callback for pending satellite notifications
        self._on_pending_callback: Optional[Callable] = None

    def set_sse_broadcaster(self, sse_broadcaster) -> None:
        """Set SSE broadcaster for real-time updates."""
        self._sse_broadcaster = sse_broadcaster

    def set_on_pending_callback(self, callback: Callable) -> None:
        """Set callback for when a new satellite is pending approval."""
        self._on_pending_callback = callback

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key."""
        return secrets.token_urlsafe(32)

    async def handle_onboard(
        self,
        websocket: WebSocket,
        api_key: str,
        hostname: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Handle a new satellite onboarding request.

        Returns satellite info if already approved, None if pending approval.
        """
        api_key_hash = self.hash_api_key(api_key)

        # Check if satellite already exists in database
        async with self.db_manager.session() as session:
            stmt = select(Satellite).where(Satellite.api_key_hash == api_key_hash)
            result = await session.execute(stmt)
            satellite = result.scalar_one_or_none()

            if satellite:
                if satellite.status == "approved":
                    # Already approved - return satellite info
                    return {
                        "satellite_id": str(satellite.id),
                        "name": satellite.name,
                        "status": "approved",
                    }
                elif satellite.status == "pending":
                    # Already pending - update pending info
                    async with self._lock:
                        self._pending_satellites[api_key_hash] = PendingSatellite(
                            api_key_hash=api_key_hash,
                            websocket=websocket,
                            hostname=hostname,
                            version=version,
                        )
                    return None
                else:
                    # Offline/rejected - treat as new pending
                    pass

        # New satellite - add to pending
        async with self._lock:
            self._pending_satellites[api_key_hash] = PendingSatellite(
                api_key_hash=api_key_hash,
                websocket=websocket,
                hostname=hostname,
                version=version,
            )

        logger.info(
            "New satellite pending approval",
            api_key_hash=api_key_hash[:16] + "...",
            hostname=hostname,
            version=version,
        )

        # Notify via callback if set
        if self._on_pending_callback:
            try:
                await self._on_pending_callback(api_key_hash, hostname, version)
            except Exception as e:
                logger.error("Error in pending callback", error=str(e))

        # Broadcast pending count via SSE
        if self._sse_broadcaster:
            try:
                await self._sse_broadcaster.send_satellite_pending_count(
                    len(self._pending_satellites)
                )
            except Exception as e:
                logger.error("Error broadcasting pending count", error=str(e))

        return None

    async def approve_satellite(
        self, api_key_hash: str, name: str
    ) -> Optional[dict]:
        """
        Approve a pending satellite.

        Creates database record and notifies the satellite.
        Returns satellite info on success, None if not found.
        """
        async with self._lock:
            pending = self._pending_satellites.get(api_key_hash)
            if not pending:
                # Check if in database as pending
                async with self.db_manager.session() as session:
                    stmt = select(Satellite).where(
                        Satellite.api_key_hash == api_key_hash,
                        Satellite.status == "pending",
                    )
                    result = await session.execute(stmt)
                    satellite = result.scalar_one_or_none()
                    if satellite:
                        # Update to approved
                        satellite.name = name
                        satellite.status = "approved"
                        satellite.approved_at = datetime.utcnow()
                        return {
                            "satellite_id": str(satellite.id),
                            "name": satellite.name,
                        }
                return None

        # Create database record
        satellite_id = uuid4()
        async with self.db_manager.session() as session:
            satellite = Satellite(
                id=satellite_id,
                name=name,
                api_key_hash=api_key_hash,
                status="approved",
                hostname=pending.hostname,
                version=pending.version,
                approved_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
            )
            session.add(satellite)

        logger.info(
            "Satellite approved",
            satellite_id=str(satellite_id)[:8],
            name=name,
        )

        # Notify the waiting satellite
        try:
            await pending.websocket.send_json({
                "type": "approved",
                "satellite_id": str(satellite_id),
                "name": name,
            })
        except Exception as e:
            logger.error("Error notifying satellite of approval", error=str(e))

        # Remove from pending
        async with self._lock:
            self._pending_satellites.pop(api_key_hash, None)

        # Broadcast updated pending count
        if self._sse_broadcaster:
            try:
                await self._sse_broadcaster.send_satellite_pending_count(
                    len(self._pending_satellites)
                )
            except Exception as e:
                logger.error("Error broadcasting pending count", error=str(e))

        return {
            "satellite_id": str(satellite_id),
            "name": name,
        }

    async def reject_satellite(self, api_key_hash: str) -> bool:
        """
        Reject a pending satellite.

        Removes from pending and notifies the satellite.
        Returns True if found and rejected, False otherwise.
        """
        async with self._lock:
            pending = self._pending_satellites.pop(api_key_hash, None)

        if not pending:
            return False

        logger.info(
            "Satellite rejected",
            api_key_hash=api_key_hash[:16] + "...",
        )

        # Notify the waiting satellite
        try:
            await pending.websocket.send_json({
                "type": "rejected",
                "message": "Registration request rejected",
            })
            await pending.websocket.close(code=4001, reason="Rejected")
        except Exception as e:
            logger.error("Error notifying satellite of rejection", error=str(e))

        # Broadcast updated pending count
        if self._sse_broadcaster:
            try:
                await self._sse_broadcaster.send_satellite_pending_count(
                    len(self._pending_satellites)
                )
            except Exception as e:
                logger.error("Error broadcasting pending count", error=str(e))

        return True

    async def connect(
        self, websocket: WebSocket, api_key: str
    ) -> Optional[SatelliteConnection]:
        """
        Handle an approved satellite connecting to the main WebSocket.

        Returns connection info on success, None if not authorized.
        """
        api_key_hash = self.hash_api_key(api_key)

        # Verify satellite is approved
        async with self.db_manager.session() as session:
            stmt = select(Satellite).where(
                Satellite.api_key_hash == api_key_hash,
                Satellite.status == "approved",
            )
            result = await session.execute(stmt)
            satellite = result.scalar_one_or_none()

            if not satellite:
                logger.warning(
                    "Unauthorized satellite connection attempt",
                    api_key_hash=api_key_hash[:16] + "...",
                )
                return None

            # Update last_seen
            satellite.last_seen_at = datetime.utcnow()

        # Create connection
        connection = SatelliteConnection(
            satellite_id=satellite.id,
            websocket=websocket,
            name=satellite.name,
        )

        async with self._lock:
            # Close any existing connection for this satellite
            existing = self._connections.get(satellite.id)
            if existing:
                try:
                    await existing.websocket.close(
                        code=4002, reason="Replaced by new connection"
                    )
                except Exception:
                    pass

            self._connections[satellite.id] = connection

        logger.info(
            "Satellite connected",
            satellite_id=str(satellite.id)[:8],
            name=satellite.name,
        )

        # Broadcast connection status via SSE
        if self._sse_broadcaster:
            try:
                await self._sse_broadcaster.send_satellite_status(
                    str(satellite.id), satellite.name, True
                )
            except Exception as e:
                logger.error("Error broadcasting satellite status", error=str(e))

        return connection

    async def disconnect(self, satellite_id: UUID) -> None:
        """Handle satellite disconnection."""
        async with self._lock:
            connection = self._connections.pop(satellite_id, None)

        if connection:
            logger.info(
                "Satellite disconnected",
                satellite_id=str(satellite_id)[:8],
                name=connection.name,
            )

            # Update database status
            async with self.db_manager.session() as session:
                stmt = (
                    update(Satellite)
                    .where(Satellite.id == satellite_id)
                    .values(last_seen_at=datetime.utcnow())
                )
                await session.execute(stmt)

            # Cancel any pending commands for this satellite
            async with self._lock:
                for cmd_id, pending in list(self._pending_commands.items()):
                    # We'd need to track satellite_id in pending commands
                    # For now, we'll leave this as a potential enhancement
                    pass

            # Broadcast disconnection via SSE
            if self._sse_broadcaster:
                try:
                    await self._sse_broadcaster.send_satellite_status(
                        str(satellite_id), connection.name, False
                    )
                except Exception as e:
                    logger.error("Error broadcasting satellite status", error=str(e))

    def is_connected(self, satellite_id: UUID) -> bool:
        """Check if a satellite is currently connected."""
        return satellite_id in self._connections

    def get_connection(self, satellite_id: UUID) -> Optional[SatelliteConnection]:
        """Get a satellite's connection if connected."""
        return self._connections.get(satellite_id)

    async def send_command(
        self,
        satellite_id: UUID,
        device_config: dict,
        command: str,
        timeout: float = 30.0,
    ) -> dict:
        """
        Send a command to a satellite and wait for response.

        Args:
            satellite_id: Target satellite UUID
            device_config: Device configuration dict
            command: Command to execute (on/off/state)
            timeout: Response timeout in seconds

        Returns:
            Result dict with success, state, error fields
        """
        connection = self._connections.get(satellite_id)
        if not connection:
            return {
                "success": False,
                "error": "Satellite not connected",
                "state": -1,
            }

        # Generate command ID
        cmd_id = secrets.token_hex(8)

        # Create pending command
        future: asyncio.Future = asyncio.Future()
        pending = PendingCommand(
            cmd_id=cmd_id,
            device_id=device_config.get("id", "unknown"),
            command=command,
            future=future,
        )

        async with self._lock:
            self._pending_commands[cmd_id] = pending

        try:
            # Send command
            await connection.websocket.send_json({
                "type": "command",
                "cmd_id": cmd_id,
                "device_type": device_config.get("device_type"),
                "device": device_config,
                "command": command,
            })

            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "Satellite command timeout",
                satellite_id=str(satellite_id)[:8],
                cmd_id=cmd_id,
                command=command,
            )
            return {
                "success": False,
                "error": "Command timeout",
                "state": -1,
            }

        except Exception as e:
            logger.error(
                "Error sending satellite command",
                satellite_id=str(satellite_id)[:8],
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
                "state": -1,
            }

        finally:
            async with self._lock:
                self._pending_commands.pop(cmd_id, None)

    async def handle_result(self, cmd_id: str, result: dict) -> None:
        """Handle a command result from a satellite."""
        async with self._lock:
            pending = self._pending_commands.get(cmd_id)

        if pending and not pending.future.done():
            pending.future.set_result(result)
        else:
            logger.warning(
                "Received result for unknown or completed command",
                cmd_id=cmd_id,
            )

    async def handle_heartbeat(self, satellite_id: UUID) -> None:
        """Handle a heartbeat from a satellite."""
        connection = self._connections.get(satellite_id)
        if connection:
            connection.last_heartbeat = datetime.utcnow()

            # Update database last_seen
            async with self.db_manager.session() as session:
                stmt = (
                    update(Satellite)
                    .where(Satellite.id == satellite_id)
                    .values(last_seen_at=datetime.utcnow())
                )
                await session.execute(stmt)

    def get_pending_satellites(self) -> list:
        """Get list of pending satellites."""
        return [
            {
                "api_key_hash": p.api_key_hash,
                "hostname": p.hostname,
                "version": p.version,
                "connected_at": p.connected_at.isoformat(),
            }
            for p in self._pending_satellites.values()
        ]

    def get_connected_satellites(self) -> list:
        """Get list of connected satellites."""
        return [
            {
                "satellite_id": str(c.satellite_id),
                "name": c.name,
                "connected_at": c.connected_at.isoformat(),
                "last_heartbeat": c.last_heartbeat.isoformat(),
            }
            for c in self._connections.values()
        ]

    async def get_all_satellites(self) -> list:
        """Get all satellites from database with connection status."""
        async with self.db_manager.session() as session:
            stmt = select(Satellite).order_by(Satellite.name)
            result = await session.execute(stmt)
            satellites = result.scalars().all()

            return [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "status": s.status,
                    "hostname": s.hostname,
                    "version": s.version,
                    "is_connected": s.id in self._connections,
                    "approved_at": s.approved_at.isoformat() if s.approved_at else None,
                    "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
                    "created_at": s.created_at.isoformat(),
                }
                for s in satellites
            ]

    async def revoke_satellite(self, satellite_id: UUID) -> bool:
        """Revoke an approved satellite."""
        # Disconnect if connected
        connection = self._connections.get(satellite_id)
        if connection:
            try:
                await connection.websocket.close(code=4003, reason="Revoked")
            except Exception:
                pass
            async with self._lock:
                self._connections.pop(satellite_id, None)

        # Delete from database
        async with self.db_manager.session() as session:
            stmt = select(Satellite).where(Satellite.id == satellite_id)
            result = await session.execute(stmt)
            satellite = result.scalar_one_or_none()

            if not satellite:
                return False

            await session.delete(satellite)

        logger.info(
            "Satellite revoked",
            satellite_id=str(satellite_id)[:8],
        )

        return True
