# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""ANEL protocol response parsing."""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PortStatus:
    """Status of a single port."""

    port: int
    name: str
    state: int  # 0=off, 1=on


@dataclass
class DeviceStatus:
    """Full device status."""

    ip: str
    name: str
    mac: str | None
    ports: list[PortStatus]
    temperature: float | None = None


def parse_status_response(data: bytes | str) -> DeviceStatus | None:
    """
    Parse ANEL status broadcast response.

    Response format (colon-separated):
    NET-PwrCtrl:NAME:IP:MASK:GW:MAC:port1_name,state1:port2_name,state2:...:temp:http:firmware:flags

    Example:
    NET-PwrCtrl:NET-CONTROL:192.168.232.95:255.255.252.0:192.168.232.1:0.4.163.17.8.92:Diaprojektoren,0:Dose 2,0:Dose 3,0:Nr. 4,0:Nr. 5,0:Nr. 6,0:Nr. 7,0:Nr. 8,0:248:80:NET-PWRCTRL_04.5:H:xo

    Args:
        data: Raw UDP response (bytes or string)

    Returns:
        DeviceStatus if valid, None otherwise
    """
    message = data.decode("utf-8") if isinstance(data, bytes) else data
    message = message.strip()

    if not message.startswith("NET-PwrCtrl"):
        return None

    try:
        parts = message.split(":")
        if len(parts) < 8:
            logger.warning(f"Invalid response format, too few parts: {len(parts)}")
            return None

        # Parts layout:
        # 0: NET-PwrCtrl
        # 1: Device name
        # 2: IP address
        # 3: Subnet mask
        # 4: Gateway
        # 5: MAC address (contains dots, not colons)
        # 6+: port_name,state pairs followed by metadata

        name = parts[1]
        ip = parts[2]
        mac = parts[5] if len(parts) > 5 else None

        # Parse port data starting from index 6
        ports = []
        for i in range(6, len(parts)):
            port_data = parts[i]
            if "," in port_data:
                comma_idx = port_data.rfind(",")
                port_name = port_data[:comma_idx]
                state_str = port_data[comma_idx + 1 :]
                try:
                    state = int(state_str)
                    ports.append(
                        PortStatus(
                            port=len(ports),
                            name=port_name,
                            state=state,
                        )
                    )
                except ValueError:
                    # Not a port status entry
                    break
            else:
                # No comma means we've reached the metadata section
                break

        # Try to extract temperature from remaining parts
        temperature = None
        for part in parts[6 + len(ports) :]:
            try:
                temp_val = float(part)
                if 0 <= temp_val <= 100:  # Reasonable temperature range
                    temperature = temp_val
                    break
            except ValueError:
                continue

        return DeviceStatus(
            ip=ip,
            name=name,
            mac=mac,
            ports=ports,
            temperature=temperature,
        )

    except Exception as e:
        logger.error(f"Error parsing status response: {e}")
        return None


def extract_port_state(response: str, port: int) -> int:
    """
    Extract single port state from status response.

    This is a simplified parser that uses regex to find port states.
    Falls back to full parsing if regex fails.

    Args:
        response: Raw status response string
        port: Port number (0-based)

    Returns:
        Port state: 0=off, 1=on, -1=error
    """
    # Validate port number
    if port < 0:
        return -1

    # First try the full parser
    status = parse_status_response(response)
    if status and port < len(status.ports):
        return status.ports[port].state

    # Fallback: try regex pattern for 8-digit state string
    # Some ANEL firmware versions return states as 8-digit string
    match = re.search(r":([01]{8}):", response)
    if match:
        port_states = match.group(1)
        if 0 <= port < len(port_states):
            return int(port_states[port])

    logger.warning(f"Could not extract state for port {port} from response")
    return -1


def parse_command_response(response: str) -> bool:
    """
    Parse response from power command.

    Args:
        response: Response string from device

    Returns:
        True if command was successful
    """
    return "OK" in response.upper() or response.startswith("NET-PwrCtrl")
