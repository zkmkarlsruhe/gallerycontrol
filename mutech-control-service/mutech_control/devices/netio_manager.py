"""NETIO device manager for power outlet control."""

import asyncio
import logging

import httpx

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceProtocol,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


class NETIOManager(DeviceManager):
    """Manage NETIO power outlet devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        timeout = httpx.Timeout(config.get("request_timeout", 5))
        self.http_client = httpx.AsyncClient(timeout=timeout)

    async def get_state(self, device) -> DeviceResult:
        """Get NETIO outlet state."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(device.id):
            next_time = self.cooldown_manager.next_allowed_time(device.id)
            remaining = self.cooldown_manager.get_remaining_seconds(device.id)
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port or device.config.get("port", 1)
            username = device.config.get("username", "netio")
            password = device.config.get("password", "netio")

            async with asyncio.timeout(timeout):
                logger.info(f"NETIO: Getting state for {device.host}:{port}")

                # Send GET request to /netio.json
                url = f"http://{device.host}/netio.json"
                auth = httpx.BasicAuth(username, password)
                response = await self.http_client.get(url, auth=auth)

                if response.status_code != 200:
                    logger.error(f"NETIO: HTTP {response.status_code} from {device.host}")
                    return DeviceResult(
                        success=False,
                        state=-1,
                        error=f"HTTP {response.status_code}"
                    )

                # Parse JSON response
                data = response.json()
                outputs = data.get("Outputs", [])

                # Find the specific output port (1-based indexing)
                outlet_state = -1
                for output in outputs:
                    if output.get("ID") == port:
                        outlet_state = output.get("State", -1)
                        break

                if outlet_state == -1:
                    logger.warning(f"NETIO: Port {port} not found in response")

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(
                    success=True,
                    state=outlet_state,
                    duration_ms=duration_ms,
                    raw_response=response.text,
                )

        except asyncio.TimeoutError:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Timeout getting state for {device.host}:{port}")
            return DeviceResult(
                success=False, state=-1, error="Request timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error getting state for {device.host}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set NETIO outlet power state."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(device.id):
            next_time = self.cooldown_manager.next_allowed_time(device.id)
            remaining = self.cooldown_manager.get_remaining_seconds(device.id)
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port or device.config.get("port", 1)
            username = device.config.get("username", "netio")
            password = device.config.get("password", "netio")
            command_str = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"NETIO: Setting {device.host}:{port} to {command_str}")

                # Send POST request to control output
                # NETIO API accepts JSON body with Outputs array
                url = f"http://{device.host}/netio.json"
                auth = httpx.BasicAuth(username, password)

                payload = {
                    "Outputs": [
                        {
                            "ID": port,
                            "Action": 1 if on else 0  # 1=on, 0=off
                        }
                    ]
                }

                response = await self.http_client.post(url, json=payload, auth=auth)

                if response.status_code != 200:
                    logger.error(f"NETIO: HTTP {response.status_code} from {device.host}")
                    return DeviceResult(
                        success=False,
                        state=device.state,
                        error=f"HTTP {response.status_code}",
                    )

                # NETIO responds immediately
                new_state = 1 if on else 0

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(
                    success=True,
                    state=new_state,
                    duration_ms=duration_ms,
                    raw_response=response.text,
                )

        except asyncio.TimeoutError:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Timeout setting power for {device.host}:{port}")
            return DeviceResult(
                success=False,
                state=device.state,
                error="Request timeout",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error setting power for {device.host}:{port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to NETIO device."""
        try:
            timeout = self.config.get("request_timeout", 5)
            username = device.config.get("username", "netio")
            password = device.config.get("password", "netio")

            async with asyncio.timeout(timeout):
                logger.info(f"NETIO: Testing connection to {device.host}")

                # Send GET request with authentication
                url = f"http://{device.host}/netio.json"
                auth = httpx.BasicAuth(username, password)
                response = await self.http_client.get(url, auth=auth)

                if response.status_code == 200:
                    # Verify we can parse the JSON
                    data = response.json()
                    if "Outputs" in data:
                        return ConnectionResult(success=True)
                    else:
                        return ConnectionResult(
                            success=False, error="Invalid JSON response format"
                        )
                elif response.status_code == 401:
                    return ConnectionResult(success=False, error="Authentication failed")
                else:
                    return ConnectionResult(
                        success=False, error=f"HTTP {response.status_code}"
                    )

        except asyncio.TimeoutError:
            logger.error(f"NETIO: Connection timeout for {device.host}")
            return ConnectionResult(success=False, error="Connection timeout")

        except Exception as e:
            logger.error(f"NETIO: Connection error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
