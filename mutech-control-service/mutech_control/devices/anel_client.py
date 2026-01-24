"""ANEL client - communicates with ANEL runner service via REST.

The runner is a UDP-to-HTTP relay. It has no state, no credential storage.
Credentials are passed per-request from this client.
"""

import asyncio
import logging

import httpx

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager
from mutech_control.devices.credential_utils import resolve_credentials

logger = logging.getLogger(__name__)

# ANEL default credentials (fallback if no credential configured)
ANEL_DEFAULT_USERNAME = "admin"
ANEL_DEFAULT_PASSWORD = "anel"


class ANELClient(DeviceManager):
    """ANEL device client - calls ANEL runner service."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        self.runner_url = config.get("runner_url", "").rstrip("/")
        self.api_key = config.get("runner_api_key", "")
        self.http_client = httpx.AsyncClient(timeout=config.get("request_timeout", 5))

    async def get_state(self, device) -> DeviceResult:
        """Get ANEL device state via runner service.

        Note: No cooldown for queries - they are read-only and shouldn't
        block correction commands during enforcement.
        """
        start_time = asyncio.get_event_loop().time()
        port = device.port if device.port is not None else device.config.get("port", 0)

        try:
            # Resolve device IP (host may be hostname)
            import socket
            try:
                ip = socket.gethostbyname(device.host)
            except socket.gaierror:
                ip = device.host  # Use as-is if resolution fails

            url = f"{self.runner_url}/query"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {"ip": ip}

            logger.info(f"ANEL: Getting state for {device.host} ({ip}) port {port} via runner")

            response = await self.http_client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    # Extract port state from device response
                    device_data = data.get("device", {})
                    ports = device_data.get("ports", [])

                    state = -1
                    for p in ports:
                        if p.get("port") == port:
                            state = p.get("state", -1)
                            break

                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                    return DeviceResult(
                        success=True,
                        state=state,
                        duration_ms=duration_ms,
                        raw_response=device_data.get("raw"),
                    )
                else:
                    error = data.get("error", "Unknown error")
                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    return DeviceResult(
                        success=False, state=-1, error=error, duration_ms=duration_ms
                    )
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(success=False, state=-1, error=error, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error getting state for {device.host}:{port}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set ANEL device power via runner service."""
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
        port = device.port if device.port is not None else device.config.get("port", 0)

        # Resolve credentials
        creds = resolve_credentials(device, ANEL_DEFAULT_USERNAME, ANEL_DEFAULT_PASSWORD)

        try:
            # Resolve device IP (host may be hostname)
            import socket
            try:
                ip = socket.gethostbyname(device.host)
            except socket.gaierror:
                ip = device.host

            url = f"{self.runner_url}/switch"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "ip": ip,
                "port": port,
                "state": on,
                "username": creds.username,
                "password": creds.password,
            }

            command = "ON" if on else "OFF"
            logger.info(f"ANEL: Setting {device.host} ({ip}) port {port} to {command} via runner")

            response = await self.http_client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    state = data.get("actual_state", 1 if on else 0)
                    confirmed = data.get("confirmed", False)

                    if not confirmed:
                        logger.warning(
                            f"ANEL: State not confirmed for {device.host}:{port}, "
                            f"requested={on}, actual={state}"
                        )

                    # Record successful request
                    cooldown = self.config.get("cooldown_seconds", 5)
                    self.cooldown_manager.record_request(device.id, cooldown)

                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                    return DeviceResult(
                        success=True,
                        state=state,
                        duration_ms=duration_ms,
                        raw_response=data.get("device", {}).get("raw"),
                    )
                else:
                    error = data.get("error", "Unknown error")
                    duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    return DeviceResult(
                        success=False, state=device.state, error=error, duration_ms=duration_ms
                    )
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(
                    success=False, state=device.state, error=error, duration_ms=duration_ms
                )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error setting power for {device.host}:{port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to ANEL device via runner service."""
        try:
            # Resolve device IP
            import socket
            try:
                ip = socket.gethostbyname(device.host)
            except socket.gaierror:
                ip = device.host

            url = f"{self.runner_url}/query"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {"ip": ip, "timeout": 5.0}

            logger.info(f"ANEL: Testing connection to {device.host} ({ip}) via runner")

            response = await self.http_client.post(url, json=payload, headers=headers, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return ConnectionResult(success=True)
                else:
                    return ConnectionResult(success=False, error=data.get("error", "Query failed"))
            else:
                return ConnectionResult(
                    success=False, error=f"HTTP {response.status_code}: {response.text}"
                )

        except Exception as e:
            logger.error(f"ANEL: Connection test error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))

    async def get_device_info(self, device) -> dict:
        """Get ANEL device information via runner service."""
        try:
            # Resolve device IP
            import socket
            try:
                ip = socket.gethostbyname(device.host)
            except socket.gaierror:
                ip = device.host

            url = f"{self.runner_url}/query"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {"ip": ip}

            response = await self.http_client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("device", {})
                else:
                    return {"error": data.get("error", "Query failed")}
            else:
                return {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"ANEL: Failed to get device info for {device.host}: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
