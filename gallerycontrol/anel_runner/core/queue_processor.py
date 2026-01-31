# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Background queue processor for ANEL commands."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anel_runner.core.command_queue import CommandQueue

logger = logging.getLogger(__name__)


class QueueProcessor:
    """
    Background task that processes command queue.

    Mirrors Node.js setInterval pattern:
    - Runs every command_delay seconds
    - Processes one command per tick
    - Sets is_processing flag to prevent overlap
    """

    def __init__(
        self,
        queue: "CommandQueue",
        delay_seconds: float = 0.5,
    ):
        """
        Initialize queue processor.

        Args:
            queue: CommandQueue to process
            delay_seconds: Delay between processing commands
        """
        self.queue = queue
        self.delay_seconds = delay_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._is_processing = False

    async def start(self) -> None:
        """Start the queue processor task."""
        if self._running:
            logger.warning("Queue processor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info(f"Queue processor started (delay: {self.delay_seconds}s)")

    async def stop(self) -> None:
        """Stop processor, wait for current command to finish."""
        if not self._running:
            return

        logger.info("Stopping queue processor...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Wait for current processing to complete
        while self._is_processing:
            await asyncio.sleep(0.1)

        logger.info("Queue processor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                await self._process_one()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")

            # Wait between processing cycles
            await asyncio.sleep(self.delay_seconds)

    async def _process_one(self) -> None:
        """Process single queue item."""
        if self._is_processing or self.queue.is_empty():
            return

        self._is_processing = True

        try:
            item = await self.queue.pop()
            if item is None:
                return

            logger.debug("Processing queued command")

            try:
                result = await item.command_fn(*item.args, **item.kwargs)
                if not item.future.done():
                    item.future.set_result(result)
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                if not item.future.done():
                    item.future.set_exception(e)

        finally:
            self._is_processing = False

    @property
    def is_processing(self) -> bool:
        """Check if currently processing a command."""
        return self._is_processing

    @property
    def is_running(self) -> bool:
        """Check if processor is running."""
        return self._running
