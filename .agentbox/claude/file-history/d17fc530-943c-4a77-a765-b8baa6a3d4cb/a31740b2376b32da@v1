"""ANEL client - communicates with ANEL runner service via REST."""

import asyncio
import logging

import httpx

from mutech_control.devices.base import ConnectionResult, DeviceManager, DeviceResult
from mutech_control.orchestrator.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


class ANELClient(DeviceManager):
    """ANEL device client - calls ANEL runner service."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        self.runner_url = config.get("runner_url")
        self.api_key = config.get("runner_api_key")
        self.http_client = httpx.AsyncClient(timeout=config.get("request_timeout", 5))

    async def get_state(self, device) -> DeviceResult:
        """Get ANEL device state via runner service."""
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
            url = f"{self.runner_url}/devices/{device.host}/state"
            params = {"port": device.port}
            headers = {"Authorization": f"Bearer {self.api_key}"}

            logger.info(f"ANEL: Getting state for {device.host}:{device.port} via runner")

            response = await self.http_client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                state = data.get("state", -1)

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
                self.cooldown_manager.record_request(str(device.id), cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(success=True, state=state, duration_ms=duration_ms)
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(success=False, state=-1, error=error, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error getting state for {device.host}:{device.port}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set ANEL device power via runner service."""
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
            endpoint = "on" if on else "off"
            url = f"{self.runner_url}/devices/{device.host}/{endpoint}"
            params = {"port": device.port}
            headers = {"Authorization": f"Bearer {self.api_key}"}

            command = "on" if on else "off"
            logger.info(f"ANEL: Setting {device.host}:{device.port} to {command} via runner")

            response = await self.http_client.post(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                state = data.get("state", -1)

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
                self.cooldown_manager.record_request(str(device.id), cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(success=True, state=state, duration_ms=duration_ms)
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(
                    success=False, state=device.state, error=error, duration_ms=duration_ms
                )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error setting power for {device.host}:{device.port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to ANEL runner service."""
        try:
            url = f"{self.runner_url}/devices/{device.host}/info"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            logger.info(f"ANEL: Testing connection to runner for {device.host}")

            response = await self.http_client.get(url, headers=headers, timeout=5.0)

            if response.status_code == 200:
                return ConnectionResult(success=True)
            else:
                return ConnectionResult(
                    success=False, error=f"HTTP {response.status_code}: {response.text}"
                )

        except Exception as e:
            logger.error(f"ANEL: Connection test error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
