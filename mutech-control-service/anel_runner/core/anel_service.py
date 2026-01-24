"""Main ANEL service coordinator."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from anel_runner.config import ANELConfig
from anel_runner.core.command_queue import CommandQueue
from anel_runner.core.queue_processor import QueueProcessor
from anel_runner.exceptions import ANELShutdownError
from anel_runner.protocol.commands import format_power_command, format_status_query
from anel_runner.protocol.connection import UDPConnection
from anel_runner.protocol.parser import (
    DeviceStatus,
    parse_command_response,
    parse_status_response,
    extract_port_state,
)

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a power command."""

    success: bool
    host: str
    port: int
    command: str
    state: int | None = None
    error: str | None = None


@dataclass
class StateResult:
    """Result of a state query."""

    success: bool
    host: str
    port: int
    state: int
    name: str | None = None
    error: str | None = None


class ANELService:
    """
    Main ANEL service coordinator.

    Manages:
    - Command queue with configurable delay
    - Dual UDP socket connections
    - Status broadcast monitoring
    - Thread-safe operation
    """

    def __init__(self, config: ANELConfig):
        self.config = config
        self.command_queue = CommandQueue()
        self.connection: UDPConnection | None = None
        self.queue_processor: QueueProcessor | None = None

        # Cache of last known device states (from broadcasts)
        self._device_states: dict[str, DeviceStatus] = {}
        self._state_lock = asyncio.Lock()
        self._is_shutdown = False

        # Track background tasks for proper error handling
        self._background_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        """Initialize connections and start background tasks."""
        logger.info("Starting ANEL service...")

        # Create UDP connection with broadcast listener
        self.connection = UDPConnection(
            send_port=self.config.udp_send_port,
            receive_port=self.config.udp_receive_port,
            on_message=self._handle_broadcast,
        )
        await self.connection.start()

        # Start queue processor
        self.queue_processor = QueueProcessor(
            queue=self.command_queue,
            delay_seconds=self.config.command_delay_seconds,
        )
        await self.queue_processor.start()

        logger.info("ANEL service started")

    def _create_background_task(self, coro, name: str = None) -> asyncio.Task:
        """Create a tracked background task with error handling."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)
        return task

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        """Callback when background task completes."""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Background task failed",
                        extra={"task_name": task.get_name(), "error": str(exc)})

    async def shutdown(self) -> None:
        """Graceful shutdown with queue drain."""
        logger.info("Shutting down ANEL service...")
        self._is_shutdown = True

        # Stop queue processor
        if self.queue_processor:
            await self.queue_processor.stop()
            self.queue_processor = None

        # Clear remaining queue
        cancelled = await self.command_queue.clear()
        if cancelled:
            logger.info(f"Cancelled {cancelled} pending commands")

        # Cancel all background tasks
        for task in list(self._background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._background_tasks.clear()

        # Cleanup connection
        if self.connection:
            await self.connection.cleanup()
            self.connection = None

        logger.info("ANEL service shutdown complete")

    def _handle_broadcast(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming status broadcast."""
        try:
            status = parse_status_response(data)
            if status:
                # Update cached state (tracked task for proper error handling)
                self._create_background_task(
                    self._update_device_state(status),
                    name=f"update_state_{status.ip}"
                )
                logger.debug(
                    f"Broadcast from {status.ip}: {len(status.ports)} ports"
                )
        except Exception as e:
            logger.error(f"Error handling broadcast from {addr}: {e}")

    async def _update_device_state(self, status: DeviceStatus) -> None:
        """Update cached device state."""
        async with self._state_lock:
            self._device_states[status.ip] = status

    async def set_power_state(
        self,
        host: str,
        port: int,
        state: bool,
        user: str | None = None,
        password: str | None = None,
        fast_lane: bool = False,
    ) -> CommandResult:
        """
        Set power state for a port.

        Args:
            host: Device IP address
            port: Port number (0-based)
            state: True for on, False for off
            user: Username (uses default if None)
            password: Password (uses default if None)
            fast_lane: Bypass queue for immediate execution

        Returns:
            CommandResult with success status
        """
        if self._is_shutdown:
            raise ANELShutdownError("Service is shutting down")

        cmd = "on" if state else "off"
        actual_user = user or self.config.default_user
        actual_password = password or self.config.default_password

        if fast_lane:
            # Execute immediately, bypassing queue
            return await self._execute_power_command(
                host, port, cmd, actual_user, actual_password
            )
        else:
            # Queue command and wait for result
            future = await self.command_queue.queue_command(
                self._execute_power_command,
                host,
                port,
                cmd,
                actual_user,
                actual_password,
            )
            return await future

    async def _execute_power_command(
        self,
        host: str,
        port: int,
        command: str,
        user: str,
        password: str,
    ) -> CommandResult:
        """Execute power command via UDP."""
        if not self.connection:
            return CommandResult(
                success=False,
                host=host,
                port=port,
                command=command,
                error="Connection not initialized",
            )

        try:
            # Format command
            cmd_str = format_power_command(command, port, user, password)

            # Send and wait for response
            response = await self.connection.send_and_receive(
                cmd_str,
                host,
                timeout=self.config.connection_timeout_seconds,
            )

            # Parse response
            success = parse_command_response(response)

            if success:
                # Determine new state
                new_state = 1 if command == "on" else 0
                logger.info(f"Power command successful: {host}:{port} -> {command}")
                return CommandResult(
                    success=True,
                    host=host,
                    port=port,
                    command=command,
                    state=new_state,
                )
            else:
                logger.warning(f"Unexpected response from {host}: {response}")
                return CommandResult(
                    success=False,
                    host=host,
                    port=port,
                    command=command,
                    error=f"Unexpected response: {response}",
                )

        except Exception as e:
            logger.error(f"Power command failed for {host}:{port}: {e}")
            return CommandResult(
                success=False,
                host=host,
                port=port,
                command=command,
                error=str(e),
            )

    async def get_power_state(
        self,
        host: str,
        port: int,
    ) -> StateResult:
        """
        Get power state for a port.

        First checks cached state from broadcasts, then queries device.

        Args:
            host: Device IP address
            port: Port number (0-based)

        Returns:
            StateResult with current state
        """
        if self._is_shutdown:
            raise ANELShutdownError("Service is shutting down")

        if not self.connection:
            return StateResult(
                success=False,
                host=host,
                port=port,
                state=-1,
                error="Connection not initialized",
            )

        try:
            # Query device state
            query = format_status_query()
            response = await self.connection.send_and_receive(
                query,
                host,
                timeout=self.config.connection_timeout_seconds,
            )

            # Parse response
            status = parse_status_response(response)

            if status and port < len(status.ports):
                port_status = status.ports[port]
                # Update cache
                await self._update_device_state(status)

                return StateResult(
                    success=True,
                    host=host,
                    port=port,
                    state=port_status.state,
                    name=port_status.name,
                )
            else:
                # Try extracting single port state
                state = extract_port_state(response, port)
                return StateResult(
                    success=state != -1,
                    host=host,
                    port=port,
                    state=state,
                    error="Could not parse port state" if state == -1 else None,
                )

        except Exception as e:
            logger.error(f"Get state failed for {host}:{port}: {e}")
            return StateResult(
                success=False,
                host=host,
                port=port,
                state=-1,
                error=str(e),
            )

    async def get_device_info(self, host: str) -> DeviceStatus | None:
        """
        Get full device information.

        Args:
            host: Device IP address

        Returns:
            DeviceStatus or None if query fails
        """
        if self._is_shutdown:
            raise ANELShutdownError("Service is shutting down")

        if not self.connection:
            return None

        try:
            query = format_status_query()
            response = await self.connection.send_and_receive(
                query,
                host,
                timeout=self.config.connection_timeout_seconds,
            )

            status = parse_status_response(response)
            if status:
                await self._update_device_state(status)

            return status

        except Exception as e:
            logger.error(f"Get device info failed for {host}: {e}")
            return None

    def get_cached_state(self, host: str) -> DeviceStatus | None:
        """Get cached device state (from broadcasts).

        Note: This is safe without lock because dict.get() is atomic in Python.
        """
        return self._device_states.get(host)

    async def get_all_cached_states(self) -> dict[str, DeviceStatus]:
        """Get all cached device states (thread-safe copy).

        Returns a snapshot to avoid iteration during modification.
        """
        async with self._state_lock:
            return dict(self._device_states)

    @property
    def queue_length(self) -> int:
        """Get current command queue length."""
        return self.command_queue.qsize()

    @property
    def is_processing(self) -> bool:
        """Check if queue processor is currently executing."""
        return self.queue_processor.is_processing if self.queue_processor else False
