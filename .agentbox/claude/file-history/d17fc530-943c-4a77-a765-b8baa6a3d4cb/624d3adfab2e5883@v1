"""PJLink device manager for projector control."""

import asyncio
import logging
from typing import Dict

from mutech_control.devices.base import ConnectionResult, DeviceManager, DeviceResult
from mutech_control.orchestrator.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


class PJLinkManager(DeviceManager):
    """Manage PJLink projector devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        self._connections: Dict[str, object] = {}  # IP -> projector connection pool

    async def get_state(self, device) -> DeviceResult:
        """Get projector power state."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(str(device.id)):
            next_time = self.cooldown_manager.next_allowed(str(device.id))
            remaining = self.cooldown_manager.get_remaining_cooldown(str(device.id))
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 10)

            async with asyncio.timeout(timeout):
                # TODO: Implement pypjlink integration
                # For now, simulate PJLink response
                logger.info(f"PJLink: Getting state for {device.host}")

                # Placeholder - in real implementation:
                # from pypjlink import Projector
                # projector = Projector.from_address(device.host, device.config.get('password'))
                # power_state = await projector.get_power()
                # state = self._map_pjlink_state(power_state)

                # Simulate response
                await asyncio.sleep(0.1)  # Simulate network delay
                state = device.state  # Keep current state for now

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 30)
                self.cooldown_manager.record_request(str(device.id), cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(success=True, state=state, duration_ms=duration_ms)

        except asyncio.TimeoutError:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"PJLink: Timeout getting state for {device.host}")
            return DeviceResult(
                success=False, state=-1, error="Request timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"PJLink: Error getting state for {device.host}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set projector power state."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(str(device.id)):
            next_time = self.cooldown_manager.next_allowed(str(device.id))
            remaining = self.cooldown_manager.get_remaining_cooldown(str(device.id))
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 10)
            command = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"PJLink: Setting {device.host} to {command}")

                # TODO: Implement pypjlink integration
                # projector = Projector.from_address(device.host, device.config.get('password'))
                # await projector.set_power(on)

                # Simulate response
                await asyncio.sleep(0.2)  # Projectors are slower
                new_state = 1 if on else 0

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 30)
                self.cooldown_manager.record_request(str(device.id), cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(success=True, state=new_state, duration_ms=duration_ms)

        except asyncio.TimeoutError:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"PJLink: Timeout setting power for {device.host}")
            return DeviceResult(
                success=False,
                state=device.state,
                error="Request timeout",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"PJLink: Error setting power for {device.host}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to projector."""
        try:
            timeout = self.config.get("request_timeout", 10)

            async with asyncio.timeout(timeout):
                logger.info(f"PJLink: Testing connection to {device.host}")

                # TODO: Implement pypjlink connection test
                # projector = Projector.from_address(device.host, device.config.get('password'))
                # await projector.authenticate()

                await asyncio.sleep(0.1)

                return ConnectionResult(success=True)

        except asyncio.TimeoutError:
            logger.error(f"PJLink: Connection timeout for {device.host}")
            return ConnectionResult(success=False, error="Connection timeout")

        except Exception as e:
            logger.error(f"PJLink: Connection error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))

    def _map_pjlink_state(self, pjlink_state: str) -> int:
        """Map PJLink power state to our state codes."""
        # PJLink states: '0' = off, '1' = on, '2' = cooling, '3' = warming
        mapping = {"0": 0, "1": 1, "2": 2, "3": 3}
        return mapping.get(str(pjlink_state), -1)
