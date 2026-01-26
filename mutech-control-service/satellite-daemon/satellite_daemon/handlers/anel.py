"""ANEL NET-PwrCtrl device handler.

ANEL devices use UDP for control:
- Send commands to port 9975
- Listen for state broadcasts on port 9977
"""

import asyncio
import logging
import socket
from typing import Dict, Optional

from .base import BaseHandler

logger = logging.getLogger(__name__)

DEFAULT_SEND_PORT = 9975
DEFAULT_RECV_PORT = 9977
DEFAULT_TIMEOUT = 5.0


class ANELHandler(BaseHandler):
    """Handler for ANEL NET-PwrCtrl power sockets."""

    async def get_state(self, device: Dict) -> Dict:
        """Get current power state from ANEL device."""
        host = device.get("resolved") or device.get("host")
        port_index = device.get("config", {}).get("port_index", 0)

        try:
            # ANEL broadcasts state periodically, but we can trigger a query
            response = await self._send_command(host, "wer da?")
            if not response:
                return {"success": False, "state": -1, "error": "No response from device"}

            # Parse response to get port state
            state = self._parse_state(response, port_index)
            return {
                "success": True,
                "state": state,
                "raw_response": response,
            }

        except Exception as e:
            logger.error(f"Error getting ANEL state: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def set_power(self, device: Dict, on: bool) -> Dict:
        """Set power state on ANEL device."""
        host = device.get("resolved") or device.get("host")
        config = device.get("config", {})
        port_index = config.get("port_index", 0)
        username = config.get("username", "admin")
        password = config.get("password", "anel")

        try:
            # ANEL command format: Sw_on<port><user><password> or Sw_off<port><user><password>
            action = "on" if on else "off"
            # Port numbering: 0-indexed in config, 1-indexed in protocol
            cmd = f"Sw_{action}{port_index + 1}{username}{password}"

            response = await self._send_command(host, cmd)

            # Verify state after command
            state_response = await self._send_command(host, "wer da?")
            state = self._parse_state(state_response or "", port_index) if state_response else (1 if on else 0)

            return {
                "success": True,
                "state": state,
                "raw_response": response or state_response,
            }

        except Exception as e:
            logger.error(f"Error setting ANEL power: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def _send_command(
        self, host: str, command: str, timeout: float = DEFAULT_TIMEOUT
    ) -> Optional[str]:
        """Send UDP command and wait for response."""
        loop = asyncio.get_event_loop()

        def blocking_send():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            try:
                sock.sendto(command.encode(), (host, DEFAULT_SEND_PORT))
                # Wait for response on same socket
                sock.bind(("", 0))
                try:
                    data, _ = sock.recvfrom(1024)
                    return data.decode(errors="replace")
                except socket.timeout:
                    # Try listening on broadcast port
                    return None
            finally:
                sock.close()

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, blocking_send),
                timeout=timeout + 1,
            )
        except asyncio.TimeoutError:
            return None

    def _parse_state(self, response: str, port_index: int) -> int:
        """Parse ANEL response to get port state.

        ANEL response format varies by firmware, but typically includes
        a string of 0s and 1s for port states.
        """
        if not response:
            return -1

        try:
            # Look for port state pattern in response
            # Common format: "NET-PwrCtrl:... 11001100 ..."
            # The 8 digits represent states of 8 ports
            parts = response.split()
            for part in parts:
                if len(part) == 8 and all(c in "01" for c in part):
                    if port_index < len(part):
                        return 1 if part[port_index] == "1" else 0

            # Fallback: try to find any 0/1 pattern
            for char in response:
                if char in "01":
                    return int(char)

        except Exception as e:
            logger.debug(f"Error parsing ANEL response: {e}")

        return -1
