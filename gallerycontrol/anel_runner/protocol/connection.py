# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""UDP connection management for ANEL devices."""

import asyncio
import logging
import socket
from typing import Callable

from anel_runner.exceptions import ANELConnectionError, ANELSocketError, ANELTimeoutError

logger = logging.getLogger(__name__)


class BroadcastProtocol(asyncio.DatagramProtocol):
    """Protocol handler for status broadcasts on UDP port."""

    def __init__(self, callback: Callable[[bytes, tuple[str, int]], None]):
        self.callback = callback
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            self.callback(data, addr)
        except Exception as e:
            logger.error(f"Error in broadcast callback: {e}")

    def error_received(self, exc: Exception) -> None:
        logger.error(f"Broadcast socket error: {exc}")

    def connection_lost(self, exc: Exception | None) -> None:
        if exc:
            logger.error(f"Broadcast connection lost: {exc}")


class UDPConnection:
    """
    Manages dual UDP sockets for ANEL communication.

    - Send socket: ephemeral port -> device:send_port (9975)
    - Receive socket: bound to receive_port (9977) for broadcasts
    """

    def __init__(
        self,
        send_port: int = 9975,
        receive_port: int = 9977,
        on_message: Callable[[bytes, tuple[str, int]], None] | None = None,
    ):
        self.send_port = send_port
        self.receive_port = receive_port
        self.on_message = on_message

        self._receive_transport: asyncio.DatagramTransport | None = None
        self._receive_protocol: BroadcastProtocol | None = None
        self._is_shutdown = False
        self._lock = asyncio.Lock()

        # Track pending responses for concurrent send_and_receive calls
        # Key: host IP, Value: (event, response_data list)
        self._pending_responses: dict[str, tuple[asyncio.Event, list[str]]] = {}

    async def start(self) -> None:
        """Initialize both sockets."""
        if self._is_shutdown:
            raise ANELSocketError("Connection already shutdown")

        await self._create_receive_socket()
        logger.info(
            f"UDP connection started (send:{self.send_port}, receive:{self.receive_port})"
        )

    def _handle_incoming_data(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP data - check pending responses and call user callback."""
        host_ip = addr[0]
        decoded = data.decode("utf-8", errors="ignore")

        # Check if any pending request is waiting for this response
        # Match by source IP or by IP appearing in response data
        matched_host = None
        for pending_host in list(self._pending_responses.keys()):
            if pending_host == host_ip or pending_host in decoded:
                matched_host = pending_host
                break

        if matched_host and matched_host in self._pending_responses:
            event, response_data = self._pending_responses[matched_host]
            response_data.append(decoded.strip())
            event.set()
            logger.debug(f"Matched response for pending request to {matched_host}")

        # Always call the user's broadcast callback too
        if self.on_message:
            self.on_message(data, addr)

    async def _create_receive_socket(self) -> None:
        """Create and bind the receive socket for broadcasts."""
        try:
            loop = asyncio.get_event_loop()

            # Create UDP endpoint for receiving broadcasts
            # Use our internal handler that checks pending responses
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: BroadcastProtocol(self._handle_incoming_data),
                local_addr=("0.0.0.0", self.receive_port),
                allow_broadcast=True,
            )

            self._receive_transport = transport
            self._receive_protocol = protocol

            logger.info(f"Broadcast listener started on port {self.receive_port}")

        except OSError as e:
            raise ANELSocketError(f"Failed to bind receive socket: {e}")

    async def send_command(self, message: str, host: str, timeout: float = 5.0) -> None:
        """
        Send UDP command to device (fire-and-forget).

        Args:
            message: Command string to send
            host: Device IP address
            timeout: Send timeout in seconds (prevents blocking on full buffer)
        """
        if self._is_shutdown:
            raise ANELSocketError("Connection is shutdown")

        loop = asyncio.get_event_loop()

        # Create a new socket for each send (ephemeral port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            data = message.encode("utf-8")
            # Wrap in timeout to prevent blocking if send buffer is full
            await asyncio.wait_for(
                loop.run_in_executor(None, sock.sendto, data, (host, self.send_port)),
                timeout=timeout,
            )
            logger.debug(f"Sent command to {host}:{self.send_port}")
        except asyncio.TimeoutError:
            raise ANELTimeoutError(f"Send timeout", device_ip=host)
        finally:
            sock.close()

    async def send_and_receive(
        self,
        message: str,
        host: str,
        timeout: float = 5.0,
    ) -> str:
        """
        Send command and wait for response.

        ANEL protocol: send to device:75, response comes back on our:77
        We use the broadcast listener socket (port 77) to receive responses.

        This method is safe for concurrent calls - each request is tracked
        separately in _pending_responses.

        Args:
            message: Command string to send
            host: Device IP address
            timeout: Response timeout in seconds

        Returns:
            Response string from device

        Raises:
            ANELTimeoutError: If no response within timeout
            ANELConnectionError: If device unreachable
        """
        if self._is_shutdown:
            raise ANELSocketError("Connection is shutdown")

        # Create event and response storage for this request
        response_event = asyncio.Event()
        response_data: list[str] = []

        # Register this pending request
        async with self._lock:
            self._pending_responses[host] = (response_event, response_data)

        try:
            # Send command to device port
            await self.send_command(message, host, timeout)
            logger.debug(f"Sent query to {host}:{self.send_port}, waiting for response on port {self.receive_port}")

            # Wait for response on port 77
            try:
                await asyncio.wait_for(response_event.wait(), timeout=timeout)
                if response_data:
                    response = response_data[0]
                    logger.debug(f"Received response from {host}: {response[:100]}...")
                    return response
                else:
                    raise ANELTimeoutError("No response data", device_ip=host)
            except asyncio.TimeoutError:
                raise ANELTimeoutError("Timeout waiting for response", device_ip=host)

        except ANELTimeoutError:
            raise
        except Exception as e:
            raise ANELConnectionError(f"Connection error: {e}", device_ip=host)

        finally:
            # Remove pending request
            async with self._lock:
                self._pending_responses.pop(host, None)

    async def cleanup(self) -> None:
        """Close all sockets."""
        self._is_shutdown = True

        if self._receive_transport:
            self._receive_transport.close()
            self._receive_transport = None
            self._receive_protocol = None

        logger.info("UDP connection cleaned up")

    @property
    def is_running(self) -> bool:
        """Check if connection is active."""
        return not self._is_shutdown
