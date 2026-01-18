"""PJLink device manager for projector control."""

import asyncio
import hashlib
import socket
from typing import Dict

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceProtocol,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager
from mutech_control.devices.shell_manager import get_credential
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


def _get_device_password(device) -> str | None:
    """Get password for device from credential cache."""
    credential_name = device.config.get("credential_name")
    if not credential_name:
        return None
    cred = get_credential(credential_name)
    return cred.get("password") if cred else None


class PJLinkManager(DeviceManager):
    """Manage PJLink projector devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        self._connections: Dict[str, object] = {}  # IP -> projector connection pool

    async def _send_command(self, host: str, port: int, command: str, password: str | None = None) -> str:
        """
        Send PJLink command and get response.

        Args:
            host: Projector IP address
            port: PJLink port (default 4352)
            command: PJLink command (e.g., "POWR ?")
            password: Optional password for authentication

        Returns:
            Response string from projector
        """
        loop = asyncio.get_event_loop()

        # Create socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            # Connect
            await loop.run_in_executor(None, sock.connect, (host, port))

            # Receive greeting (contains auth challenge if password required)
            greeting = await loop.run_in_executor(None, sock.recv, 1024)
            greeting = greeting.decode('utf-8').strip()

            # Build command with authentication if needed
            if password and "PJLINK 1" in greeting:
                # Extract challenge from greeting: "PJLINK 1 <challenge>"
                parts = greeting.split()
                if len(parts) >= 3:
                    challenge = parts[2]
                    # MD5 hash of challenge + password
                    auth_hash = hashlib.md5((challenge + password).encode()).hexdigest()
                    full_command = f"{auth_hash}%1{command}\r"
                else:
                    full_command = f"%1{command}\r"
            else:
                full_command = f"%1{command}\r"

            # Send command
            await loop.run_in_executor(None, sock.sendall, full_command.encode('utf-8'))

            # Receive response
            response = await loop.run_in_executor(None, sock.recv, 1024)
            return response.decode('utf-8').strip()

        finally:
            sock.close()

    async def get_state(self, device) -> DeviceResult:
        """Get projector power state."""
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
            timeout = self.config.get("request_timeout", 10)
            port = device.config.get("port", 4352)
            password = _get_device_password(device)

            async with asyncio.timeout(timeout):
                logger.info("Getting device state",
                           device=device.name if hasattr(device, 'name') else 'unknown',
                           host=device.host,
                           type="pjlink")

                # Send power query command
                response = await self._send_command(device.host, port, "POWR ?", password)

                # Parse response: "%1POWR=<state>"
                if "POWR=" in response:
                    state_str = response.split("=")[1]
                    state = self._map_pjlink_state(state_str)
                    logger.debug("State query successful",
                                host=device.host,
                                state=state,
                                response=response[:50])
                else:
                    logger.warning("Unexpected response from device",
                                  host=device.host,
                                  response=response[:100])
                    state = -1

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 30)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(
                    success=True,
                    state=state,
                    duration_ms=duration_ms,
                    raw_response=response,
                )

        except asyncio.TimeoutError:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error("Device state request timeout",
                        device=device.name if hasattr(device, 'name') else 'unknown',
                        host=device.host,
                        type="pjlink",
                        duration_ms=duration_ms)
            return DeviceResult(
                success=False, state=-1, error="Request timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error("Device state request failed",
                        device=device.name if hasattr(device, 'name') else 'unknown',
                        host=device.host,
                        type="pjlink",
                        error=str(e),
                        duration_ms=duration_ms)
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set projector power state."""
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
            timeout = self.config.get("request_timeout", 10)
            port = device.config.get("port", 4352)
            password = _get_device_password(device)
            command_str = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"Setting device power {command_str}",
                           device=device.name if hasattr(device, 'name') else 'unknown',
                           host=device.host,
                           type="pjlink",
                           command=command_str)

                # Send power command: "POWR 1" for on, "POWR 0" for off
                pjlink_cmd = "POWR 1" if on else "POWR 0"
                response = await self._send_command(device.host, port, pjlink_cmd, password)

                # Response should be "%1POWR=OK"
                if "OK" in response:
                    # Projectors go to warming/cooling states
                    new_state = 3 if on else 2  # 3=warming, 2=cooling
                    logger.debug("Power command successful",
                                host=device.host,
                                new_state=new_state)
                else:
                    logger.warning("Unexpected response to power command",
                                  host=device.host,
                                  response=response[:100])
                    new_state = device.state

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 30)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(
                    success=True,
                    state=new_state,
                    duration_ms=duration_ms,
                    raw_response=response,
                )

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
            port = device.config.get("port", 4352)
            password = _get_device_password(device)

            async with asyncio.timeout(timeout):
                logger.info(f"PJLink: Testing connection to {device.host}")

                # Try to get power state as a connection test
                response = await self._send_command(device.host, port, "POWR ?", password)

                if "POWR=" in response or "OK" in response:
                    return ConnectionResult(success=True)
                else:
                    return ConnectionResult(success=False, error=f"Unexpected response: {response}")

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
