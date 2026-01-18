"""ANEL device manager for power outlet control via UDP."""

import asyncio
import logging
import re
import socket

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceProtocol,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


class ANELManager(DeviceManager):
    """Manage ANEL power outlet devices via UDP protocol."""

    # ANEL UDP ports
    SEND_PORT = 9975  # Commands sent to this port
    RECEIVE_PORT = 9977  # Device broadcasts on this port

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        # Small delay between UDP commands to prevent packet loss
        self._command_delay = 0.1  # 100ms between commands

    async def _send_udp_command(self, host: str, command: str, timeout: float = 5.0) -> str:
        """
        Send UDP command to ANEL device and receive response.

        Args:
            host: Device IP address
            command: Command string (e.g., "wer da?", "Sw_on1adminpassword")
            timeout: Response timeout in seconds

        Returns:
            Response string from device
        """
        loop = asyncio.get_event_loop()

        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        try:
            # Send command
            message = command.encode('utf-8')
            await loop.run_in_executor(
                None, sock.sendto, message, (host, self.SEND_PORT)
            )

            # Receive response
            data, addr = await loop.run_in_executor(None, sock.recvfrom, 1024)
            response = data.decode('utf-8').strip()

            return response

        finally:
            sock.close()

    def _parse_status_response(self, response: str, port: int) -> int:
        """
        Parse ANEL status response to extract port state.

        Response format:
        NET-PwrCtrl:<name>:<ip>:<mask>:<gateway>:<mac>:<port_states>:<port_names>:<locked>:<http>:<temp>

        Note: MAC address contains colons, so we use regex to find the port states string.

        Args:
            response: Full status response string
            port: Port number (0-based)

        Returns:
            Port state: 0=off, 1=on, -1=error
        """
        try:
            # MAC address is XX:XX:XX:XX:XX:XX followed by port states (8 digits)
            # Use regex to find the 8-digit port states string
            match = re.search(r':([01]{8}):', response)
            if not match:
                logger.warning(f"ANEL: Could not find port states in response: {response}")
                return -1

            port_states_str = match.group(1)

            if port < 0 or port >= len(port_states_str):
                logger.warning(f"ANEL: Port {port} out of range")
                return -1

            state = int(port_states_str[port])
            return state

        except (IndexError, ValueError) as e:
            logger.error(f"ANEL: Error parsing status response: {e}")
            return -1

    async def get_state(self, device) -> DeviceResult:
        """Get ANEL outlet state."""
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
            port = device.port or device.config.get("port", 0)

            async with asyncio.timeout(timeout):
                logger.info(f"ANEL: Getting state for {device.host}:{port}")

                # Send status query command
                response = await self._send_udp_command(device.host, "wer da?", timeout)

                # Parse response to get port state
                state = self._parse_status_response(response, port)

                if state == -1:
                    logger.warning(f"ANEL: Could not parse state from response")

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
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
            logger.error(f"ANEL: Timeout getting state for {device.host}:{port}")
            return DeviceResult(
                success=False, state=-1, error="Request timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error getting state for {device.host}:{port}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set ANEL outlet power state."""
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
            port = device.port or device.config.get("port", 0)
            username = device.config.get("username", "admin")
            password = device.config.get("password", "anel")
            command_str = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"ANEL: Setting {device.host}:{port} to {command_str}")

                # Build command: Sw_on<port+1><username><password> or Sw_off<port+1><username><password>
                # Port is 1-based in protocol (0-based internally)
                port_num = port + 1

                if on:
                    command = f"Sw_on{port_num}{username}{password}"
                else:
                    command = f"Sw_off{port_num}{username}{password}"

                # Send command
                response = await self._send_udp_command(device.host, command, timeout)

                # Check response
                if "OK" in response:
                    new_state = 1 if on else 0
                else:
                    logger.warning(f"ANEL: Unexpected response: {response}")
                    new_state = -1

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 5)
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
            logger.error(f"ANEL: Timeout setting power for {device.host}:{port}")
            return DeviceResult(
                success=False,
                state=device.state,
                error="Request timeout",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"ANEL: Error setting power for {device.host}:{port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to ANEL device."""
        try:
            timeout = self.config.get("request_timeout", 5)

            async with asyncio.timeout(timeout):
                logger.info(f"ANEL: Testing connection to {device.host}")

                # Send status query as connection test
                response = await self._send_udp_command(device.host, "wer da?", timeout)

                # Check if response is valid ANEL format
                if response.startswith("NET-PwrCtrl:"):
                    return ConnectionResult(success=True)
                else:
                    return ConnectionResult(
                        success=False, error=f"Unexpected response: {response}"
                    )

        except asyncio.TimeoutError:
            logger.error(f"ANEL: Connection timeout for {device.host}")
            return ConnectionResult(success=False, error="Connection timeout")

        except Exception as e:
            logger.error(f"ANEL: Connection error for {device.host}: {e}")
            return ConnectionResult(success=False, error=str(e))
