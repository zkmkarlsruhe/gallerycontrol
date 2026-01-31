# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Tests for command queue and processor."""

import asyncio

import pytest

from anel_runner.core.command_queue import CommandQueue, QueueItem
from anel_runner.core.queue_processor import QueueProcessor


class TestCommandQueue:
    """Tests for CommandQueue."""

    @pytest.fixture
    def queue(self):
        """Create a command queue."""
        return CommandQueue()

    @pytest.mark.asyncio
    async def test_queue_command(self, queue):
        """Test queueing a command."""

        async def dummy_cmd():
            return "result"

        future = await queue.queue_command(dummy_cmd)

        assert queue.qsize() == 1
        assert not queue.is_empty()
        assert isinstance(future, asyncio.Future)

    @pytest.mark.asyncio
    async def test_queue_multiple_commands(self, queue):
        """Test queueing multiple commands."""

        async def cmd1():
            return 1

        async def cmd2():
            return 2

        await queue.queue_command(cmd1)
        await queue.queue_command(cmd2)

        assert queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_pop_command(self, queue):
        """Test popping command from queue."""

        async def dummy_cmd():
            return "result"

        await queue.queue_command(dummy_cmd)

        item = await queue.pop()
        assert item is not None
        assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_pop_empty_queue(self, queue):
        """Test popping from empty queue."""
        item = await queue.pop()
        assert item is None

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue):
        """Test clearing the queue."""

        async def dummy():
            return None

        await queue.queue_command(dummy)
        await queue.queue_command(dummy)
        await queue.queue_command(dummy)

        cancelled = await queue.clear()
        assert cancelled == 3
        assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_queue_with_args(self, queue):
        """Test queueing command with arguments."""

        async def add(a, b):
            return a + b

        future = await queue.queue_command(add, 1, 2)
        item = await queue.pop()

        assert item.args == (1, 2)
        assert item.kwargs == {}


class TestQueueProcessor:
    """Tests for QueueProcessor."""

    @pytest.fixture
    def queue(self):
        """Create a command queue."""
        return CommandQueue()

    @pytest.fixture
    def processor(self, queue):
        """Create a queue processor with short delay."""
        return QueueProcessor(queue, delay_seconds=0.05)

    @pytest.mark.asyncio
    async def test_start_stop(self, processor):
        """Test starting and stopping processor."""
        await processor.start()
        assert processor.is_running

        await processor.stop()
        assert not processor.is_running

    @pytest.mark.asyncio
    async def test_process_command(self, queue, processor):
        """Test processing a command through the queue."""
        result_holder = []

        async def record_result():
            result_holder.append("executed")
            return "done"

        future = await queue.queue_command(record_result)

        await processor.start()
        # Wait for processing
        await asyncio.sleep(0.2)
        await processor.stop()

        # Command should have been executed
        assert "executed" in result_holder
        assert future.done()
        assert future.result() == "done"

    @pytest.mark.asyncio
    async def test_process_multiple_commands(self, queue, processor):
        """Test processing multiple commands with delay."""
        results = []

        async def record(val):
            results.append(val)
            return val

        f1 = await queue.queue_command(record, 1)
        f2 = await queue.queue_command(record, 2)
        f3 = await queue.queue_command(record, 3)

        await processor.start()
        # Wait for all to process (3 * 0.05s delay + buffer)
        await asyncio.sleep(0.5)
        await processor.stop()

        assert len(results) == 3
        assert f1.done() and f2.done() and f3.done()

    @pytest.mark.asyncio
    async def test_command_exception(self, queue, processor):
        """Test handling command exception."""

        async def failing_cmd():
            raise ValueError("Test error")

        future = await queue.queue_command(failing_cmd)

        await processor.start()
        await asyncio.sleep(0.2)
        await processor.stop()

        assert future.done()
        with pytest.raises(ValueError):
            future.result()

    @pytest.mark.asyncio
    async def test_processor_not_double_start(self, processor):
        """Test processor doesn't start twice."""
        await processor.start()
        await processor.start()  # Should not raise

        assert processor.is_running
        await processor.stop()
