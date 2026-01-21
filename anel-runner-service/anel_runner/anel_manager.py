"""ANEL device manager - UDP protocol handler for ANEL power outlets.

ANEL devices communicate via UDP:
- Commands sent to port 9975
- Status broadcasts received on port 9977

Broadcast format:
NET-PwrCtrl:<name>:<ip>:<mask>:<gw>:<mac>:<port_states>:<port_names>:<locked>:<http_port>
"""

import asyncio
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PortState:
    """State of a single ANEL port."""
    port: int  # 0-based internally, 1-based in protocol
    state: int  # 0=off, 1=on
    name: str
    locked: bool = False


@dataclass
class DeviceState:
    """Complete state of an ANEL device."""
    ip: str
    name: str
    mac: str
    ports: list[PortState]
    http_port: int = 80
    timestamp: float = field(default_factory=time.time)

    def get_port_state(self, port: int) -> Optional[int]:
        """Get state of a specific port (0-based)."""
        if 0 <= port < len(self.ports):
            return self.ports[port].state
        return None


class ANELProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for receiving ANEL broadcasts."""

    def __init__(self, on_status_received: Callable[[DeviceState], None]):
        self.on_status_received = on_status_received
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.info("ANEL UDP listener started")

    def datagram_received(self, data: bytes, addr: tuple):
        """Called when UDP broadcast received from ANEL device."""
        try:
            msg = data.decode('latin-1').strip()
            logger.debug(f"Received UDP from {addr}: {msg[:100]}...")

            if msg.startswith('NET-PwrCtrl:'):
                device_state = self._parse_status(msg, addr[0])
                if device_state:
                    self.on_status_received(device_state)
        except Exception as e:
            logger.error(f"Error parsing ANEL broadcast from {addr}: {e}")

    def _parse_status(self, msg: str, sender_ip: str) -> Optional[DeviceState]:
        """
        Parse ANEL status broadcast message.

        Format varies by model but generally:
        NET-PwrCtrl:<name>:<ip>:<mask>:<gw>:<mac>:<port_states>:<port_names>:<locked>:<http_port>

        Note: MAC address contains colons, so we use regex to find port states.
        """
        try:
            parts = msg.split(':')

            if len(parts) < 7:
                logger.warning(f"Invalid ANEL message format: {msg[:50]}...")
                return None

            # Device name is usually the second field
            device_name = parts[1] if len(parts) > 1 else "Unknown"

            # Find the 8-digit port states string (binary: 0s and 1s)
            # MAC is XX:XX:XX:XX:XX:XX, so port states follow after MAC
            match = re.search(r':([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}):([01]{8}):', msg)

            if match:
                mac = match.group(1)
                port_states_str = match.group(2)
            else:
                # Alternative format: comma-separated states
                comma_match = re.search(r':([01],[01],[01],[01],[01],[01],[01],[01]):', msg)
                if comma_match:
                    port_states_str = comma_match.group(1).replace(',', '')
                    mac = "unknown"
                else:
                    # Fallback: try to find any 8-character binary string
                    binary_match = re.search(r':([01]{8}):', msg)
                    if binary_match:
                        port_states_str = binary_match.group(1)
                        mac = "unknown"
                    else:
                        logger.warning(f"Could not find port states in: {msg[:100]}...")
                        return None

            # Parse port names if present (comma-separated after port states)
            port_names = []
            names_match = re.search(r':([01]{8}):([^:]+):', msg)
            if names_match:
                names_str = names_match.group(2)
                port_names = names_str.split(',')

            # Build port states
            ports = []
            for i, state_char in enumerate(port_states_str):
                name = port_names[i] if i < len(port_names) else f"Port{i+1}"
                ports.append(PortState(
                    port=i,
                    state=int(state_char),
                    name=name.strip(),
                    locked=False
                ))

            # Use sender IP if not found in message
            device_ip = sender_ip

            return DeviceState(
                ip=device_ip,
                name=device_name,
                mac=mac,
                ports=ports,
                timestamp=time.time()
            )

        except Exception as e:
            logger.error(f"Error parsing ANEL status: {e}, message: {msg[:100]}...")
            return None

    def error_received(self, exc):
        logger.error(f"UDP error received: {exc}")


class ANELManager:
    """
    Manages ANEL device communication via UDP.

    - Listens for status broadcasts on port 9977
    - Sends commands on port 9975
    - Maintains state cache from broadcasts
    - Automatically cleans up stale cache entries
    """

    SEND_PORT = 9975
    RECEIVE_PORT = 9977

    # Cache cleanup settings
    DEFAULT_STALE_TIMEOUT = 300  # 5 minutes - entries older than this are removed
    DEFAULT_CLEANUP_INTERVAL = 60  # Run cleanup every 60 seconds

    def __init__(
        self,
        bind_address: str = "0.0.0.0",
        stale_timeout: float = DEFAULT_STALE_TIMEOUT,
        cleanup_interval: float = DEFAULT_CLEANUP_INTERVAL,
    ):
        self.bind_address = bind_address
        self.stale_timeout = stale_timeout
        self.cleanup_interval = cleanup_interval

        self.protocol: Optional[ANELProtocol] = None
        self.transport = None
        self.send_socket: Optional[socket.socket] = None

        # State cache: {ip: DeviceState}
        self.device_cache: dict[str, DeviceState] = {}

        # Callbacks for status updates
        self.status_callbacks: list[Callable[[DeviceState], None]] = []

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start listening for ANEL broadcasts and cache cleanup."""
        self._running = True
        loop = asyncio.get_event_loop()

        try:
            # Create UDP socket for receiving broadcasts
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: ANELProtocol(self._handle_status),
                local_addr=(self.bind_address, self.RECEIVE_PORT),
                reuse_port=True
            )

            # Create socket for sending commands
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.send_socket.setblocking(False)

            logger.info(f"ANEL Manager started - listening on {self.bind_address}:{self.RECEIVE_PORT}")

        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.warning(f"Port {self.RECEIVE_PORT} already in use, trying with SO_REUSEADDR")
                # Fallback: create socket manually with REUSEADDR
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                sock.bind((self.bind_address, self.RECEIVE_PORT))
                sock.setblocking(False)

                self.transport, self.protocol = await loop.create_datagram_endpoint(
                    lambda: ANELProtocol(self._handle_status),
                    sock=sock
                )

                self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                self.send_socket.setblocking(False)

                logger.info(f"ANEL Manager started with REUSEADDR")
            else:
                raise

        # Start background cache cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"Cache cleanup enabled: stale_timeout={self.stale_timeout}s, "
            f"interval={self.cleanup_interval}s"
        )

    def _handle_status(self, device_state: DeviceState):
        """Handle received status broadcast."""
        # Update cache
        self.device_cache[device_state.ip] = device_state

        logger.debug(
            f"Status update from {device_state.ip}: "
            f"ports={[p.state for p in device_state.ports]}"
        )

        # Notify callbacks
        for callback in self.status_callbacks:
            try:
                result = callback(device_state)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def on_status(self, callback: Callable[[DeviceState], None]):
        """Register callback for status updates."""
        self.status_callbacks.append(callback)

    async def send_command(self, ip: str, command: str) -> bool:
        """Send UDP command to ANEL device."""
        try:
            loop = asyncio.get_event_loop()

            data = command.encode('latin-1')
            await loop.run_in_executor(
                None,
                lambda: self.send_socket.sendto(data, (ip, self.SEND_PORT))
            )

            logger.info(f"Sent command to {ip}:{self.SEND_PORT}: {command}")
            return True

        except Exception as e:
            logger.error(f"Failed to send command to {ip}: {e}")
            return False

    async def query_device(self, ip: str) -> bool:
        """Send status query to device."""
        return await self.send_command(ip, "wer da?")

    async def set_port_state(
        self,
        ip: str,
        port: int,
        state: bool,
        username: str = "admin",
        password: str = "anel"
    ) -> bool:
        """
        Set ANEL port state.

        Args:
            ip: Device IP address
            port: Port number (0-based)
            state: True=on, False=off
            username: Device username
            password: Device password

        Returns:
            True if command sent successfully
        """
        # Port is 1-based in protocol
        port_num = port + 1

        if state:
            command = f"Sw_on{port_num}{username}{password}"
        else:
            command = f"Sw_off{port_num}{username}{password}"

        return await self.send_command(ip, command)

    def get_cached_state(self, ip: str) -> Optional[DeviceState]:
        """Get cached state for a device."""
        return self.device_cache.get(ip)

    def get_port_state(self, ip: str, port: int) -> Optional[int]:
        """Get cached state for a specific port."""
        device = self.device_cache.get(ip)
        if device:
            return device.get_port_state(port)
        return None

    def get_all_devices(self) -> dict[str, DeviceState]:
        """Get all cached device states."""
        return dict(self.device_cache)

    async def _cleanup_loop(self):
        """Background task to clean up stale cache entries."""
        logger.debug("Cache cleanup task started")

        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)

                if not self._running:
                    break

                removed = self._cleanup_stale_entries()
                if removed > 0:
                    logger.info(f"Cache cleanup: removed {removed} stale entries")

            except asyncio.CancelledError:
                logger.debug("Cache cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")

        logger.debug("Cache cleanup task stopped")

    def _cleanup_stale_entries(self) -> int:
        """
        Remove stale entries from the cache.

        Returns:
            Number of entries removed
        """
        now = time.time()
        stale_ips = []

        for ip, device in self.device_cache.items():
            age = now - device.timestamp
            if age > self.stale_timeout:
                stale_ips.append(ip)
                logger.debug(f"Device {ip} stale (age={age:.1f}s > {self.stale_timeout}s)")

        for ip in stale_ips:
            del self.device_cache[ip]

        return len(stale_ips)

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache stats
        """
        now = time.time()
        ages = [now - d.timestamp for d in self.device_cache.values()]

        return {
            "device_count": len(self.device_cache),
            "oldest_entry_age": max(ages) if ages else 0,
            "newest_entry_age": min(ages) if ages else 0,
            "stale_timeout": self.stale_timeout,
            "cleanup_interval": self.cleanup_interval,
        }

    async def stop(self):
        """Stop the manager and cleanup tasks."""
        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Close network resources
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None

        # Clear cache
        self.device_cache.clear()
        self.status_callbacks.clear()

        logger.info("ANEL Manager stopped")
