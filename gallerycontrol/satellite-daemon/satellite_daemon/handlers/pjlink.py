# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""PJLink projector handler.

PJLink uses TCP on port 4352 with optional MD5 authentication.
"""

import asyncio
import hashlib
import logging
from typing import Dict, Optional, Tuple

from .base import BaseHandler

logger = logging.getLogger(__name__)

DEFAULT_PORT = 4352
DEFAULT_TIMEOUT = 10.0


class PJLinkHandler(BaseHandler):
    """Handler for PJLink projectors."""

    async def get_state(self, device: Dict) -> Dict:
        """Get current power state from PJLink projector."""
        host = device.get("resolved") or device.get("host")
        port = device.get("port") or DEFAULT_PORT
        config = device.get("config", {})
        password = config.get("password")

        try:
            response = await self._send_command(host, port, "%1POWR ?", password)
            if response is None:
                return {"success": False, "state": -1, "error": "No response"}

            # Parse PJLink response: %1POWR=<state>
            # States: 0=off, 1=on, 2=cooling, 3=warming
            if "=" in response:
                state_str = response.split("=")[1].strip()
                try:
                    state = int(state_str)
                    return {
                        "success": True,
                        "state": state,
                        "raw_response": response,
                    }
                except ValueError:
                    pass

            return {"success": False, "state": -1, "error": f"Invalid response: {response}"}

        except Exception as e:
            logger.error(f"Error getting PJLink state: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def set_power(self, device: Dict, on: bool) -> Dict:
        """Set power state on PJLink projector."""
        host = device.get("resolved") or device.get("host")
        port = device.get("port") or DEFAULT_PORT
        config = device.get("config", {})
        password = config.get("password")

        cmd = "%1POWR 1" if on else "%1POWR 0"

        try:
            response = await self._send_command(host, port, cmd, password)
            if response is None:
                return {"success": False, "state": -1, "error": "No response"}

            # Check for OK response
            if "OK" in response:
                # Query state after command
                state_response = await self._send_command(host, port, "%1POWR ?", password)
                state = self._parse_state(state_response) if state_response else (1 if on else 0)
                return {
                    "success": True,
                    "state": state,
                    "raw_response": response,
                }

            # Check for error response
            if "ERR" in response:
                return {"success": False, "state": -1, "error": f"PJLink error: {response}"}

            return {"success": False, "state": -1, "error": f"Unexpected response: {response}"}

        except Exception as e:
            logger.error(f"Error setting PJLink power: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def _send_command(
        self,
        host: str,
        port: int,
        command: str,
        password: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Optional[str]:
        """Send PJLink command and return response."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )

            try:
                # Read greeting
                greeting = await asyncio.wait_for(reader.readline(), timeout=timeout)
                greeting_str = greeting.decode().strip()

                # Check if authentication is required
                if greeting_str.startswith("PJLINK 1"):
                    # Authentication required
                    if not password:
                        return None

                    # Extract random number for MD5
                    parts = greeting_str.split()
                    if len(parts) >= 3:
                        random_num = parts[2]
                        # Create auth hash: MD5(random + password)
                        auth_hash = hashlib.md5(
                            (random_num + password).encode()
                        ).hexdigest()
                        # Prepend hash to command
                        command = auth_hash + command

                elif greeting_str.startswith("PJLINK 0"):
                    # No authentication required
                    pass
                else:
                    logger.warning(f"Unexpected PJLink greeting: {greeting_str}")

                # Send command
                writer.write((command + "\r").encode())
                await writer.drain()

                # Read response
                response = await asyncio.wait_for(reader.readline(), timeout=timeout)
                return response.decode().strip()

            finally:
                writer.close()
                await writer.wait_closed()

        except asyncio.TimeoutError:
            logger.warning(f"PJLink timeout connecting to {host}:{port}")
            return None
        except Exception as e:
            logger.error(f"PJLink connection error: {e}")
            return None

    def _parse_state(self, response: str) -> int:
        """Parse PJLink state response."""
        if "=" in response:
            state_str = response.split("=")[1].strip()
            try:
                return int(state_str)
            except ValueError:
                pass
        return -1
