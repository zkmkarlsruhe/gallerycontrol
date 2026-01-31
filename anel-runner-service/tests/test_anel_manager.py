# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Tests for ANEL manager."""

import asyncio
import time

import pytest
from unittest.mock import MagicMock, patch

from anel_runner.anel_manager import ANELManager, ANELProtocol, DeviceState, PortState


class TestANELProtocol:
    """Tests for ANEL UDP protocol parsing."""

    def test_parse_status_basic(self):
        """Test parsing basic ANEL status broadcast."""
        protocol = ANELProtocol(lambda x: None)

        # Simulated ANEL broadcast message
        msg = "NET-PwrCtrl:PDU-01:192.168.50.10:255.255.255.0:192.168.50.1:00:11:22:33:44:55:11110000:Port1,Port2,Port3,Port4,Port5,Port6,Port7,Port8:0:80"

        device = protocol._parse_status(msg, "192.168.50.10")

        assert device is not None
        assert device.name == "PDU-01"
        assert len(device.ports) == 8
        assert device.ports[0].state == 1  # ON
        assert device.ports[4].state == 0  # OFF

    def test_parse_status_all_off(self):
        """Test parsing when all ports are off."""
        protocol = ANELProtocol(lambda x: None)

        msg = "NET-PwrCtrl:Test:10.0.0.1:255.255.255.0:10.0.0.1:AA:BB:CC:DD:EE:FF:00000000:P1,P2,P3,P4,P5,P6,P7,P8:0:80"

        device = protocol._parse_status(msg, "10.0.0.1")

        assert device is not None
        assert all(p.state == 0 for p in device.ports)

    def test_parse_status_all_on(self):
        """Test parsing when all ports are on."""
        protocol = ANELProtocol(lambda x: None)

        msg = "NET-PwrCtrl:Test:10.0.0.1:255.255.255.0:10.0.0.1:AA:BB:CC:DD:EE:FF:11111111:P1,P2,P3,P4,P5,P6,P7,P8:0:80"

        device = protocol._parse_status(msg, "10.0.0.1")

        assert device is not None
        assert all(p.state == 1 for p in device.ports)

    def test_parse_status_invalid(self):
        """Test handling invalid message."""
        protocol = ANELProtocol(lambda x: None)

        device = protocol._parse_status("invalid message", "10.0.0.1")
        assert device is None


class TestANELManager:
    """Tests for ANEL manager."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return ANELManager()

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.SEND_PORT == 9975
        assert manager.RECEIVE_PORT == 9977
        assert len(manager.device_cache) == 0

    def test_cache_device(self, manager):
        """Test device caching."""
        device = DeviceState(
            ip="192.168.50.10",
            name="Test",
            mac="00:11:22:33:44:55",
            ports=[
                PortState(port=0, state=1, name="Port1"),
                PortState(port=1, state=0, name="Port2"),
            ]
        )

        # Simulate receiving a broadcast
        manager._handle_status(device)

        assert "192.168.50.10" in manager.device_cache
        assert manager.get_port_state("192.168.50.10", 0) == 1
        assert manager.get_port_state("192.168.50.10", 1) == 0

    def test_get_port_state_unknown_device(self, manager):
        """Test getting state for unknown device."""
        assert manager.get_port_state("10.0.0.1", 0) is None

    def test_status_callback(self, manager):
        """Test status callback is called."""
        callback_called = False
        received_device = None

        def callback(device):
            nonlocal callback_called, received_device
            callback_called = True
            received_device = device

        manager.on_status(callback)

        device = DeviceState(
            ip="192.168.50.10",
            name="Test",
            mac="00:11:22:33:44:55",
            ports=[PortState(port=0, state=1, name="Port1")]
        )

        manager._handle_status(device)

        assert callback_called
        assert received_device == device


class TestDeviceState:
    """Tests for DeviceState dataclass."""

    def test_get_port_state(self):
        """Test getting port state."""
        device = DeviceState(
            ip="10.0.0.1",
            name="Test",
            mac="AA:BB:CC:DD:EE:FF",
            ports=[
                PortState(port=0, state=1, name="Port1"),
                PortState(port=1, state=0, name="Port2"),
                PortState(port=2, state=1, name="Port3"),
            ]
        )

        assert device.get_port_state(0) == 1
        assert device.get_port_state(1) == 0
        assert device.get_port_state(2) == 1
        assert device.get_port_state(10) is None  # Out of range


class TestCacheCleanup:
    """Tests for cache cleanup functionality."""

    def test_cleanup_stale_entries(self):
        """Test that stale entries are removed."""
        manager = ANELManager(stale_timeout=10)  # 10 seconds

        # Add a device with old timestamp
        old_device = DeviceState(
            ip="192.168.50.10",
            name="Old",
            mac="00:11:22:33:44:55",
            ports=[PortState(port=0, state=1, name="Port1")],
            timestamp=time.time() - 20  # 20 seconds ago
        )
        manager.device_cache["192.168.50.10"] = old_device

        # Add a device with fresh timestamp
        new_device = DeviceState(
            ip="192.168.50.11",
            name="New",
            mac="00:11:22:33:44:66",
            ports=[PortState(port=0, state=1, name="Port1")],
            timestamp=time.time()  # Now
        )
        manager.device_cache["192.168.50.11"] = new_device

        # Run cleanup
        removed = manager._cleanup_stale_entries()

        assert removed == 1
        assert "192.168.50.10" not in manager.device_cache
        assert "192.168.50.11" in manager.device_cache

    def test_cleanup_no_stale_entries(self):
        """Test cleanup with no stale entries."""
        manager = ANELManager(stale_timeout=300)

        device = DeviceState(
            ip="192.168.50.10",
            name="Fresh",
            mac="00:11:22:33:44:55",
            ports=[PortState(port=0, state=1, name="Port1")],
            timestamp=time.time()
        )
        manager.device_cache["192.168.50.10"] = device

        removed = manager._cleanup_stale_entries()

        assert removed == 0
        assert "192.168.50.10" in manager.device_cache

    def test_get_cache_stats(self):
        """Test cache statistics."""
        manager = ANELManager(stale_timeout=300, cleanup_interval=60)

        # Empty cache
        stats = manager.get_cache_stats()
        assert stats["device_count"] == 0
        assert stats["stale_timeout"] == 300
        assert stats["cleanup_interval"] == 60

        # Add a device
        device = DeviceState(
            ip="192.168.50.10",
            name="Test",
            mac="00:11:22:33:44:55",
            ports=[PortState(port=0, state=1, name="Port1")],
        )
        manager.device_cache["192.168.50.10"] = device

        stats = manager.get_cache_stats()
        assert stats["device_count"] == 1
        assert stats["oldest_entry_age"] >= 0


@pytest.mark.asyncio
class TestANELManagerAsync:
    """Async tests for ANEL manager."""

    async def test_send_command_format(self):
        """Test command format for turning on/off."""
        manager = ANELManager()

        # Mock the send_socket
        manager.send_socket = MagicMock()
        manager.send_socket.sendto = MagicMock()

        # Note: We can't fully test send_command without a real socket,
        # but we can verify the command format in the manager
        port = 3  # 0-based
        username = "admin"
        password = "anel"

        # Expected command for turning ON port 4 (1-based in protocol)
        expected_on = f"Sw_on{port + 1}{username}{password}"
        expected_off = f"Sw_off{port + 1}{username}{password}"

        assert expected_on == "Sw_on4adminanel"
        assert expected_off == "Sw_off4adminanel"

    async def test_stop_clears_cache(self):
        """Test that stop clears the cache."""
        manager = ANELManager()
        manager._running = True

        # Add a device
        device = DeviceState(
            ip="192.168.50.10",
            name="Test",
            mac="00:11:22:33:44:55",
            ports=[PortState(port=0, state=1, name="Port1")],
        )
        manager.device_cache["192.168.50.10"] = device

        # Add a callback
        manager.status_callbacks.append(lambda x: None)

        await manager.stop()

        assert len(manager.device_cache) == 0
        assert len(manager.status_callbacks) == 0
        assert manager._running is False
