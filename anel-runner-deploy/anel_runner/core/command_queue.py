# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Thread-safe command queue for ANEL operations."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """Command queue item with future for result tracking."""

    command_fn: Callable[..., Awaitable[Any]]
    args: tuple
    kwargs: dict
    future: asyncio.Future
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CommandQueue:
    """
    Thread-safe async command queue.

    Implements the same pattern as Node.js ANELManager:
    - Commands added via queue_command() return a Future
    - Queue processor pops items with configurable delay
    - Fast lane bypasses queue entirely
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize command queue.

        Args:
            max_size: Maximum queue size (0 for unlimited)
        """
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=max_size)
        self._lock = asyncio.Lock()

    async def queue_command(
        self,
        command_fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Future:
        """
        Add command to queue and return Future for result.

        Args:
            command_fn: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Future that will be resolved when command completes
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        item = QueueItem(
            command_fn=command_fn,
            args=args,
            kwargs=kwargs,
            future=future,
        )

        await self._queue.put(item)
        logger.debug(f"Command queued, queue size: {self._queue.qsize()}")

        return future

    async def pop(self) -> QueueItem | None:
        """
        Get next command from queue (non-blocking).

        Returns:
            Next QueueItem or None if queue empty
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def qsize(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    async def clear(self) -> int:
        """
        Clear all pending commands from queue.

        Returns:
            Number of cancelled commands
        """
        cancelled = 0
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if not item.future.done():
                    item.future.cancel()
                    cancelled += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Queue cleared, cancelled {cancelled} commands")
        return cancelled
