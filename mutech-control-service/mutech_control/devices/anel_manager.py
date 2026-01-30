"""ANEL device manager for power outlet control via UDP."""

import asyncio
import logging
import random
import re
import socket

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceProtocol,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager
from mutech_control.devices.credential_utils import resolve_credentials
from mutech_control.devices.port_utils import db_to_device_id

logger = logging.getLogger(__name__)


# ANEL default credentials
ANEL_DEFAULT_USERNAME = "admin"
ANEL_DEFAULT_PASSWORD = "anel"


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
        """Get ANEL outlet state. No cooldown - queries are read-only."""
        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port if device.port is not None else device.config.get("port", 0)

            async with asyncio.timeout(timeout):
                logger.info(f"ANEL: Getting state for {device.host}:{port}")

                # Send status query command
                response = await self._send_udp_command(device.host, "wer da?", timeout)

                # Parse response to get port state
                state = self._parse_status_response(response, port)

                if state == -1:
                    logger.warning(f"ANEL: Could not parse state from response")

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
        if cooldown_result := self.cooldown_manager.check_cooldown(device.id, device.state):
            return cooldown_result

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port if device.port is not None else device.config.get("port", 0)
            creds = resolve_credentials(device, ANEL_DEFAULT_USERNAME, ANEL_DEFAULT_PASSWORD)
            username, password = creds.username, creds.password
            command_str = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"ANEL: Setting {device.host}:{port} to {command_str}")

                # Build command: Sw_on<port+1><username><password> or Sw_off<port+1><username><password>
                # Port is 1-based in protocol (0-based in database)
                port_num = db_to_device_id(port)

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

                # Record minimal random cooldown (0-1s) to prevent accidental double-clicks
                cooldown = random.uniform(0, 1)
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

    async def get_device_info(self, device) -> dict:
        """
        Query device information from ANEL power strip.

        Response format:
        NET-PwrCtrl:<name>:<ip>:<mask>:<gateway>:<mac>:<port_states>:<port_names>:<locked>:<http>:<temp>

        Returns dict with:
            - name: Device name
            - ip: IP address
            - mac: MAC address
            - temperature: Current temperature (if available)
            - ports: List of port info
        """
        info = {}

        try:
            timeout = self.config.get("request_timeout", 5)
            response = await self._send_udp_command(device.host, "wer da?", timeout)

            if not response.startswith("NET-PwrCtrl:"):
                return {"error": f"Invalid response: {response[:50]}"}

            # Parse the response - MAC address contains colons so we need careful parsing
            # Find MAC address pattern (6 pairs of hex digits with colons)
            import re
            mac_match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', response)
            
            if mac_match:
                info["mac"] = mac_match.group(1)
                
                # Split before and after MAC
                before_mac = response[:mac_match.start()].rstrip(':')
                after_mac = response[mac_match.end():].lstrip(':')
                
                # Parse before MAC: NET-PwrCtrl:<name>:<ip>:<mask>:<gateway>
                before_parts = before_mac.split(':')
                if len(before_parts) >= 5:
                    info["device_type"] = before_parts[0]  # NET-PwrCtrl
                    info["name"] = before_parts[1]
                    info["ip"] = before_parts[2]
                    info["netmask"] = before_parts[3]
                    info["gateway"] = before_parts[4]
                
                # Parse after MAC: <port_states>:<port_names>:<locked>:<http>:<temp>
                after_parts = after_mac.split(':')
                if after_parts:
                    # First part is port states (8 characters of 0/1)
                    port_states = after_parts[0] if after_parts else ""
                    info["port_states"] = port_states
                    
                    # Port names (comma-separated)
                    if len(after_parts) > 1:
                        port_names = after_parts[1].split(',') if after_parts[1] else []
                        info["ports"] = [
                            {"port": i, "name": port_names[i] if i < len(port_names) else f"Port {i+1}", 
                             "state": int(port_states[i]) if i < len(port_states) else -1}
                            for i in range(len(port_states))
                        ]
                    
                    # Temperature (usually last part)
                    if len(after_parts) > 4:
                        temp_str = after_parts[4]
                        try:
                            # Temperature might be in format "23.5" or similar
                            info["temperature"] = float(temp_str.replace(',', '.'))
                        except ValueError:
                            info["temperature_raw"] = temp_str

            logger.info(f"ANEL: Retrieved device info for {device.host}",
                       extra={"info": info})

            return info

        except Exception as e:
            logger.error(f"ANEL: Failed to get device info for {device.host}: {e}")
            return {"error": str(e)}
