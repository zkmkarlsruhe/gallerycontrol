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
from mutech_control.devices.credential_utils import resolve_credentials
from mutech_control.devices.port_utils import db_to_device_id

logger = logging.getLogger(__name__)


# NETIO default credentials
NETIO_DEFAULT_USERNAME = "netio"
NETIO_DEFAULT_PASSWORD = "netio"


class NETIOManager(DeviceManager):
    """Manage NETIO power outlet devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        timeout = httpx.Timeout(config.get("request_timeout", 5))
        self.http_client = httpx.AsyncClient(timeout=timeout)

    async def get_state(self, device) -> DeviceResult:
        """Get NETIO outlet state."""
        if cooldown_result := self.cooldown_manager.check_cooldown(device.id, device.state):
            return cooldown_result

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port if device.port is not None else device.config.get("port", 0)
            # Convert 0-based port (database) to 1-based ID (NETIO API)
            netio_id = db_to_device_id(port)
            creds = resolve_credentials(device, NETIO_DEFAULT_USERNAME, NETIO_DEFAULT_PASSWORD)
            username, password = creds.username, creds.password

            async with asyncio.timeout(timeout):
                logger.info(f"NETIO: Getting state for {device.host} outlet {port} (ID={netio_id})")

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

                # Find the specific output by ID (1-based)
                outlet_state = -1
                for output in outputs:
                    if output.get("ID") == netio_id:
                        outlet_state = output.get("State", -1)
                        break

                if outlet_state == -1:
                    logger.warning(f"NETIO: ID {netio_id} not found in response")

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
            logger.error(f"NETIO: Timeout getting state for {device.host} outlet {port}")
            return DeviceResult(
                success=False, state=-1, error="Request timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error getting state for {device.host}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Set NETIO outlet power state."""
        if cooldown_result := self.cooldown_manager.check_cooldown(device.id, device.state):
            return cooldown_result

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 5)
            port = device.port if device.port is not None else device.config.get("port", 0)
            # Convert 0-based port (database) to 1-based ID (NETIO API)
            netio_id = db_to_device_id(port)
            creds = resolve_credentials(device, NETIO_DEFAULT_USERNAME, NETIO_DEFAULT_PASSWORD)
            username, password = creds.username, creds.password
            command_str = "on" if on else "off"

            async with asyncio.timeout(timeout):
                logger.info(f"NETIO: Setting {device.host} outlet {port} (ID={netio_id}) to {command_str}")

                # Send POST request to control output
                # NETIO API accepts JSON body with Outputs array
                url = f"http://{device.host}/netio.json"
                auth = httpx.BasicAuth(username, password)

                payload = {
                    "Outputs": [
                        {
                            "ID": netio_id,
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
            logger.error(f"NETIO: Timeout setting power for {device.host} outlet {port}")
            return DeviceResult(
                success=False,
                state=device.state,
                error="Request timeout",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"NETIO: Error setting power for {device.host} outlet {port}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test connection to NETIO device."""
        try:
            timeout = self.config.get("request_timeout", 5)
            creds = resolve_credentials(device, NETIO_DEFAULT_USERNAME, NETIO_DEFAULT_PASSWORD)
            username, password = creds.username, creds.password

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

    async def get_device_info(self, device) -> dict:
        """
        Query device information from NETIO power strip.

        Returns dict with:
            - model: Device model name
            - mac: MAC address
            - firmware: Firmware version
            - serial: Serial number
            - uptime: Device uptime in seconds
            - outputs: List of output info (name, state)
        """
        info = {}

        try:
            creds = resolve_credentials(device, NETIO_DEFAULT_USERNAME, NETIO_DEFAULT_PASSWORD)
            username, password = creds.username, creds.password

            url = f"http://{device.host}/netio.json"
            auth = httpx.BasicAuth(username, password)
            response = await self.http_client.get(url, auth=auth)

            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}

            data = response.json()

            # Agent info (device metadata)
            agent = data.get("Agent", {})
            info["model"] = agent.get("Model")
            info["mac"] = agent.get("MAC")
            info["firmware"] = agent.get("Version")
            info["serial"] = agent.get("SerialNumber")
            info["device_name"] = agent.get("DeviceName")
            info["uptime"] = agent.get("Uptime")
            info["num_outputs"] = agent.get("NumOutputs")

            # Global measurements if available
            global_measure = data.get("GlobalMeasure", {})
            if global_measure:
                info["voltage"] = global_measure.get("Voltage")
                info["frequency"] = global_measure.get("Frequency")
                info["total_current"] = global_measure.get("TotalCurrent")
                info["total_power"] = global_measure.get("TotalLoad")
                info["total_energy"] = global_measure.get("TotalEnergy")

            # Output details
            outputs = data.get("Outputs", [])
            info["outputs"] = [
                {
                    "id": o.get("ID"),
                    "name": o.get("Name"),
                    "state": o.get("State"),
                    "current": o.get("Current"),
                    "power": o.get("Load"),
                    "energy": o.get("Energy"),
                }
                for o in outputs
            ]

            logger.info(f"NETIO: Retrieved device info for {device.host}",
                       extra={"info": info})

            return info

        except Exception as e:
            logger.error(f"NETIO: Failed to get device info for {device.host}: {e}")
            return {"error": str(e)}
