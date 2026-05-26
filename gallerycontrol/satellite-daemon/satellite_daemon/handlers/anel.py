# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""ANEL NET-PwrCtrl device handler.

ANEL devices use UDP for control. Two firmware variants exist:
- Classic firmware: send on UDP 75, listens for replies on UDP 77.
- Newer firmware: 9975 / 9977.

The defaults below match the classic firmware (which is what's deployed in the
Subraum exhibition). Newer firmware can be configured per-device by setting
`device.config.anel_send_port` and `device.config.anel_recv_port`.

Status query: send the ASCII string "wer da?" — device replies with a
colon-separated state record:

    NET-PwrCtrl:<name>:<ip>:<mask>:<gw>:<mac>:<port1name>,<state>:<port2name>,<state>:...
"""

import asyncio
import logging
import socket
import time
from typing import Dict, Optional, Tuple

from .base import BaseHandler

logger = logging.getLogger(__name__)

DEFAULT_SEND_PORT = 75
DEFAULT_RECV_PORT = 77
DEFAULT_TIMEOUT = 3.0
DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "anel"


class ANELHandler(BaseHandler):
    """Handler for ANEL NET-PwrCtrl power sockets."""

    async def get_state(self, device: Dict) -> Dict:
        host = device.get("resolved") or device.get("host")
        port_index = self._port_index(device)
        send_port, recv_port = self._ports(device)

        response = await self._query(host, "wer da?", send_port, recv_port)
        if not response:
            return {"success": False, "state": -1, "error": "No response from device"}

        state = self._parse_port_state(response, port_index)
        return {"success": True, "state": state, "raw_response": response}

    async def set_power(self, device: Dict, on: bool) -> Dict:
        host = device.get("resolved") or device.get("host")
        config = device.get("config", {}) or {}
        port_index = self._port_index(device)
        send_port, recv_port = self._ports(device)
        username = config.get("username", DEFAULT_USER)
        password = config.get("password", DEFAULT_PASSWORD)

        action = "on" if on else "off"
        # Port numbering: 0-indexed in config, 1-indexed in protocol.
        cmd = f"Sw_{action}{port_index + 1}{username}{password}"

        send_resp = await self._query(host, cmd, send_port, recv_port)
        # Re-query state to confirm.
        state_resp = await self._query(host, "wer da?", send_port, recv_port)
        if not state_resp:
            return {
                "success": False, "state": -1,
                "error": "No state response after command",
                "raw_response": send_resp,
            }
        state = self._parse_port_state(state_resp, port_index)
        expected = 1 if on else 0
        return {
            "success": state == expected,
            "state": state,
            "raw_response": state_resp,
        }

    async def get_device_info(self, device: Dict) -> Dict:
        host = device.get("resolved") or device.get("host")
        send_port, recv_port = self._ports(device)
        response = await self._query(host, "wer da?", send_port, recv_port)
        if not response:
            return {"success": False, "info": {}, "error": "No response from device"}

        parts = response.split(":")
        info = {}
        if len(parts) >= 6:
            info = {
                "name": parts[1].strip(),
                "ip": parts[2].strip(),
                "netmask": parts[3].strip(),
                "gateway": parts[4].strip(),
                "mac": parts[5].strip(),
            }
        return {"success": True, "info": info, "raw_response": response}

    # --- helpers ---

    @staticmethod
    def _ports(device: Dict) -> Tuple[int, int]:
        config = device.get("config", {}) or {}
        return (
            int(config.get("anel_send_port", DEFAULT_SEND_PORT)),
            int(config.get("anel_recv_port", DEFAULT_RECV_PORT)),
        )

    @staticmethod
    def _port_index(device: Dict) -> int:
        config = device.get("config", {}) or {}
        # Accept either nested config.port_index or top-level port (the server's
        # admin model stores the outlet number as `device.port`).
        if "port_index" in config:
            return int(config["port_index"])
        port = device.get("port")
        return int(port) if port is not None else 0

    async def _query(
        self, host: str, command: str, send_port: int, recv_port: int,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Optional[str]:
        """Send a UDP command and wait for the device's reply on recv_port.

        Uses the runner-proven dual-socket pattern: bind the listener on
        recv_port BEFORE sending so a fast reply isn't lost. Send from a
        separate ephemeral socket. Both sockets are closed at the end.
        """
        loop = asyncio.get_event_loop()

        def blocking():
            listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                listener.bind(("", recv_port))
            except OSError as e:
                listener.close()
                logger.error(f"ANEL: failed to bind recv socket on port {recv_port}: {e}")
                return None
            listener.settimeout(timeout)

            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                sender.sendto(command.encode(), (host, send_port))
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    listener.settimeout(max(0.01, deadline - time.monotonic()))
                    try:
                        data, (src_ip, _) = listener.recvfrom(2048)
                    except socket.timeout:
                        return None
                    if src_ip == host:
                        return data.decode("latin-1", errors="replace")
                    # Reply from a different device on the broadcast — ignore.
                return None
            except Exception as e:
                logger.error(f"ANEL: send/recv error for {host}: {e}")
                return None
            finally:
                listener.close()
                sender.close()

        return await loop.run_in_executor(None, blocking)

    @staticmethod
    def _parse_port_state(response: str, port_index: int) -> int:
        """Parse a "wer da?" response and return the state of the requested outlet.

        Response format (colon-separated):
            NET-PwrCtrl:<name>:<ip>:<mask>:<gw>:<mac>:<n1>,<s1>:<n2>,<s2>:...
        Port states `<sN>` are 0 or 1. Some firmwares append additional fields
        (temperature, http port, firmware, flags) — we only look at the first 8
        slots after the MAC.
        """
        if not response:
            return -1
        parts = response.split(":")
        # First 6 parts are header (header, name, ip, mask, gw, mac).
        port_slots = parts[6:14]
        if port_index >= len(port_slots):
            return -1
        slot = port_slots[port_index]
        # Slot format "name,state". State is 0 or 1.
        if "," in slot:
            _, state_str = slot.rsplit(",", 1)
            state_str = state_str.strip()
            if state_str in ("0", "1"):
                return int(state_str)
        return -1
