"""NETIO device manager for power outlet control."""

import asyncio
import logging

import httpx

from mutech_control.devices.base import ConnectionResult, DeviceManager, DeviceResult
from mutech_control.orchestrator.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


class NETIOManager(DeviceManager):
    """Manage NETIO power outlet devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        self.http_client = httpx.AsyncClient(timeout=config.get("request_timeout", 5))

    async def get_state(self, device) -> DeviceResult:
        """Get NETIO outlet state."""
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
            logger.info(f"NETIO: Getting state for {device.host}:{device.port}")

            # TODO: Implement Netio library integration
            # from Netio import Netio
            # n = Netio(f'http://{device.host}/netio.json',
            #           auth_rw=(device.config.get('user'), device.config.get('password')))
            # state = n.get_output(device.port)

            # Simulate response
            await asyncio.sleep(0.05)  # NETIO is fast
            state = device.state

            # Record successful request
            cooldown = self.config.get("cooldown_seconds", 5)
            self.cooldown_manager.record_request(str(device.id), cooldown)

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            return DeviceResult(success=True, state=state, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error getting state for {device.host}:{device.port}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set NETIO outlet power state."""
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
            command = "on" if on else "off"
            logger.info(f"NETIO: Setting {device.host}:{device.port} to {command}")

            # TODO: Implement Netio library integration
            # n = Netio(f'http://{device.host}/netio.json',
            #           auth_rw=(device.config.get('user'), device.config.get('password')))
            # n.set_output(device.port, 1 if on else 0)

            # Simulate response
            await asyncio.sleep(0.1)
            new_state = 1 if on else 0

            # Record successful request
            cooldown = self.config.get("cooldown_seconds", 5)
            self.cooldown_manager.record_request(str(device.id), cooldown)

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            return DeviceResult(success=True, state=new_state, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error setting power for {device.host}:{device.port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to NETIO device."""
        try:
            logger.info(f"NETIO: Testing connection to {device.host}")

            # Simple HTTP GET to device
            url = f"http://{device.host}/netio.json"
            response = await self.http_client.get(url, timeout=5.0)

            if response.status_code == 200:
                return ConnectionResult(success=True)
            else:
                return ConnectionResult(
                    success=False, error=f"HTTP {response.status_code}: {response.text}"
                )

        except Exception as e:
            logger.error(f"NETIO: Connection error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
