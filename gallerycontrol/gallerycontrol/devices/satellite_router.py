# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Satellite router - routes device commands through satellite relays."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID

from gallerycontrol.database.models import Device
from gallerycontrol.utils.logging import get_logger

if TYPE_CHECKING:
    from gallerycontrol.services.satellite_manager import SatelliteManager

logger = get_logger(__name__)


@dataclass
class DeviceResult:
    """Result of a device operation."""

    success: bool
    state: int  # -1=error, 0=off, 1=on, 2=cooling, 3=warming
    error: Optional[str] = None
    raw_response: Optional[str] = None
    duration_ms: Optional[int] = None


class SatelliteRouter:
    """Routes device commands through satellite relays when configured."""

    def __init__(self, satellite_manager: "SatelliteManager", device_managers: Dict):
        self._satellite_manager = satellite_manager
        self._device_managers = device_managers

    def should_route_via_satellite(self, device: Device) -> Optional[UUID]:
        """
        Check if a device should be routed via satellite.

        Returns the satellite_id if routing should happen, None otherwise.

        Routing happens when:
        1. device.use_satellite is True
        2. device.artwork.exhibition has a satellite_id set
        3. The satellite is currently connected
        """
        if not device.use_satellite:
            return None

        # Get exhibition from artwork
        artwork = getattr(device, "artwork", None)
        if not artwork:
            logger.debug(
                "Device has use_satellite but no artwork",
                device_id=str(device.id)[:8],
            )
            return None

        exhibition = getattr(artwork, "exhibition", None)
        if not exhibition:
            logger.debug(
                "Device has use_satellite but artwork has no exhibition",
                device_id=str(device.id)[:8],
            )
            return None

        satellite_id = exhibition.satellite_id
        if not satellite_id:
            logger.debug(
                "Device has use_satellite but exhibition has no satellite",
                device_id=str(device.id)[:8],
            )
            return None

        # Check if satellite is connected
        if not self._satellite_manager.is_connected(satellite_id):
            logger.warning(
                "Device satellite is not connected",
                device_id=str(device.id)[:8],
                satellite_id=str(satellite_id)[:8],
            )
            # Still return the satellite_id - we'll handle the error in routing
            return satellite_id

        return satellite_id

    def _build_device_config(self, device: Device) -> dict:
        """Build device configuration for satellite command."""
        config = {
            "id": str(device.id),
            "device_type": device.device_type,
            "name": device.name,
            "host": device.host,
            "port": device.port,
            "config": device.config or {},
        }

        # Include resolved address if available
        if device.resolved:
            config["resolved"] = device.resolved

        return config

    async def route_command(
        self, device: Device, command: str, satellite_id: UUID
    ) -> DeviceResult:
        """
        Route a command through a satellite.

        Args:
            device: The target device
            command: Command to execute ("on", "off", "state")
            satellite_id: Satellite to route through

        Returns:
            DeviceResult with operation outcome
        """
        start_time = datetime.utcnow()

        device_config = self._build_device_config(device)

        logger.debug(
            "Routing command via satellite",
            device_id=str(device.id)[:8],
            device_name=device.name,
            satellite_id=str(satellite_id)[:8],
            command=command,
        )

        result = await self._satellite_manager.send_command(
            satellite_id=satellite_id,
            device_config=device_config,
            command=command,
            timeout=30.0,
        )

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(
            "Satellite command completed",
            device_id=str(device.id)[:8],
            device_name=device.name,
            satellite_id=str(satellite_id)[:8],
            command=command,
            success=result.get("success", False),
            duration_ms=duration_ms,
        )

        return DeviceResult(
            success=result.get("success", False),
            state=result.get("state", -1),
            error=result.get("error"),
            raw_response=result.get("raw_response"),
            duration_ms=duration_ms,
        )

    async def set_power(self, device: Device, on: bool) -> DeviceResult:
        """
        Set device power state, routing via satellite if configured.

        If the device should be routed via satellite, sends through satellite.
        Otherwise, uses the direct device manager.
        """
        satellite_id = self.should_route_via_satellite(device)

        if satellite_id:
            command = "on" if on else "off"
            return await self.route_command(device, command, satellite_id)
        else:
            # Use direct device manager
            manager = self._device_managers.get(device.device_type)
            if not manager:
                return DeviceResult(
                    success=False,
                    state=-1,
                    error=f"No manager for device type: {device.device_type}",
                )
            return await manager.set_power(device, on)

    async def get_state(self, device: Device) -> DeviceResult:
        """
        Get device state, routing via satellite if configured.

        If the device should be routed via satellite, sends through satellite.
        Otherwise, uses the direct device manager.
        """
        satellite_id = self.should_route_via_satellite(device)

        if satellite_id:
            return await self.route_command(device, "state", satellite_id)
        else:
            # Use direct device manager
            manager = self._device_managers.get(device.device_type)
            if not manager:
                return DeviceResult(
                    success=False,
                    state=-1,
                    error=f"No manager for device type: {device.device_type}",
                )
            return await manager.get_state(device)
