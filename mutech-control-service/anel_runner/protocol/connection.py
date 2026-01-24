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

    async def start(self) -> None:
        """Initialize both sockets."""
        if self._is_shutdown:
            raise ANELSocketError("Connection already shutdown")

        await self._create_receive_socket()
        logger.info(
            f"UDP connection started (send:{self.send_port}, receive:{self.receive_port})"
        )

    async def _create_receive_socket(self) -> None:
        """Create and bind the receive socket for broadcasts."""
        if not self.on_message:
            logger.info("No broadcast callback provided, skipping receive socket")
            return

        try:
            loop = asyncio.get_event_loop()

            # Create UDP endpoint for receiving broadcasts
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: BroadcastProtocol(self.on_message),
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

        loop = asyncio.get_event_loop()

        # Create socket for request-response
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        try:
            data = message.encode("utf-8")

            # Send
            await loop.run_in_executor(
                None, sock.sendto, data, (host, self.send_port)
            )
            logger.debug(f"Sent query to {host}:{self.send_port}")

            # Receive
            response_data, addr = await loop.run_in_executor(
                None, sock.recvfrom, 2048
            )
            response = response_data.decode("utf-8").strip()
            logger.debug(f"Received response from {addr}: {response[:100]}...")

            return response

        except socket.timeout:
            raise ANELTimeoutError(f"Timeout waiting for response", device_ip=host)

        except OSError as e:
            raise ANELConnectionError(f"Connection error: {e}", device_ip=host)

        finally:
            sock.close()

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
