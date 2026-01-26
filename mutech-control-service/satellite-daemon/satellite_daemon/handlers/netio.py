"""NETIO PowerPDU device handler.

NETIO devices use HTTP JSON API with Basic Auth.
"""

import base64
import logging
from typing import Dict

import httpx

from .base import BaseHandler

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


class NETIOHandler(BaseHandler):
    """Handler for NETIO PowerPDU devices."""

    async def get_state(self, device: Dict) -> Dict:
        """Get current power state from NETIO device."""
        host = device.get("resolved") or device.get("host")
        port = device.get("port") or 80
        config = device.get("config", {})
        output_index = config.get("output_index", 0)
        username = config.get("username", "netio")
        password = config.get("password", "netio")

        url = f"http://{host}:{port}/netio.json"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    url,
                    auth=(username, password),
                )

                if response.status_code == 401:
                    return {"success": False, "state": -1, "error": "Authentication failed"}

                response.raise_for_status()
                data = response.json()

                # NETIO JSON format: {"Outputs": [{"ID": 1, "State": 1}, ...]}
                outputs = data.get("Outputs", [])
                if output_index < len(outputs):
                    state = outputs[output_index].get("State", 0)
                    return {
                        "success": True,
                        "state": 1 if state else 0,
                        "raw_response": str(data),
                    }
                else:
                    return {
                        "success": False,
                        "state": -1,
                        "error": f"Output index {output_index} out of range",
                    }

        except httpx.TimeoutException:
            return {"success": False, "state": -1, "error": "Connection timeout"}
        except Exception as e:
            logger.error(f"Error getting NETIO state: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def set_power(self, device: Dict, on: bool) -> Dict:
        """Set power state on NETIO device."""
        host = device.get("resolved") or device.get("host")
        port = device.get("port") or 80
        config = device.get("config", {})
        output_index = config.get("output_index", 0)
        username = config.get("username", "netio")
        password = config.get("password", "netio")

        # NETIO uses 1-indexed outputs in API
        output_id = output_index + 1
        url = f"http://{host}:{port}/netio.json"

        # NETIO action values: 0=off, 1=on, 2=short off, 3=short on, 4=toggle, 5=no change, 6=ignore
        action = 1 if on else 0

        payload = {
            "Outputs": [
                {"ID": output_id, "Action": action}
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(username, password),
                )

                if response.status_code == 401:
                    return {"success": False, "state": -1, "error": "Authentication failed"}

                response.raise_for_status()
                data = response.json()

                # Verify state from response
                outputs = data.get("Outputs", [])
                if output_index < len(outputs):
                    state = outputs[output_index].get("State", 0)
                else:
                    state = 1 if on else 0

                return {
                    "success": True,
                    "state": 1 if state else 0,
                    "raw_response": str(data),
                }

        except httpx.TimeoutException:
            return {"success": False, "state": -1, "error": "Connection timeout"}
        except Exception as e:
            logger.error(f"Error setting NETIO power: {e}")
            return {"success": False, "state": -1, "error": str(e)}
