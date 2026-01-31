# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Unit tests for PJLink manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from mutech_control.devices.pjlink_manager import PJLinkManager
from mutech_control.devices.base import DeviceResult, ConnectionResult


@pytest.fixture
def config():
    """Test configuration for PJLink."""
    return {
        "cooldown_seconds": 1,
        "request_timeout": 5,
    }


@pytest.fixture
def mock_device():
    """Mock device model."""
    device = MagicMock()
    device.id = uuid4()
    device.host = "192.168.1.100"
    device.port = 4352
    device.state = 0
    device.config = {"password": "panasonic"}
    return device


@pytest.fixture
def manager(config):
    """Create PJLink manager instance."""
    return PJLinkManager(config)


@pytest.mark.asyncio
async def test_get_state_success(manager, mock_device):
    """Test successful state query."""
    # Mock socket communication
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Mock recv to return greeting then power state response
        mock_sock.recv.side_effect = [
            b'PJLINK 0\r',  # No auth needed
            b'%1POWR=1\r'  # Power on
        ]

        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1  # on
        assert result.error is None
        assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_get_state_with_authentication(manager, mock_device):
    """Test state query with MD5 authentication."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Mock recv to return auth challenge
        mock_sock.recv.side_effect = [
            b'PJLINK 1 12345678\r',  # Auth challenge
            b'%1POWR=0\r'  # Power off
        ]

        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 0  # off

        # Verify authentication was used
        send_calls = [call[0][0] for call in mock_sock.sendall.call_args_list]
        assert len(send_calls) == 1
        # Should contain MD5 hash
        assert len(send_calls[0]) > 20  # Hash + command


@pytest.mark.asyncio
async def test_set_power_on(manager, mock_device):
    """Test power on command."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b'PJLINK 0\r',
            b'%1POWR=OK\r'
        ]

        result = await manager.set_power(mock_device, True)

        assert result.success is True
        assert result.state == 3  # warming
        assert result.error is None


@pytest.mark.asyncio
async def test_set_power_off(manager, mock_device):
    """Test power off command."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b'PJLINK 0\r',
            b'%1POWR=OK\r'
        ]

        result = await manager.set_power(mock_device, False)

        assert result.success is True
        assert result.state == 2  # cooling
        assert result.error is None


@pytest.mark.asyncio
async def test_timeout_error(manager, mock_device):
    """Test timeout handling."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Simulate timeout
        mock_sock.recv.side_effect = TimeoutError("Connection timeout")

        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_connection_error(manager, mock_device):
    """Test connection error handling."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Simulate connection refused
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert result.error is not None


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_requests(manager, mock_device):
    """Test that cooldown prevents rapid polling."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b'PJLINK 0\r', b'%1POWR=1\r',  # First request
        ]

        # First request succeeds
        result1 = await manager.get_state(mock_device)
        assert result1.success is True

        # Immediate second request blocked by cooldown
        result2 = await manager.get_state(mock_device)
        assert result2.success is False
        assert "cooldown" in result2.error.lower()


@pytest.mark.asyncio
async def test_test_connection_success(manager, mock_device):
    """Test successful connection test."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b'PJLINK 0\r',
            b'%1POWR=1\r'
        ]

        result = await manager.test_connection(mock_device)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_test_connection_failure(manager, mock_device):
    """Test connection test failure."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.connect.side_effect = TimeoutError("Connection timeout")

        result = await manager.test_connection(mock_device)

        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
async def test_state_mapping(manager, mock_device):
    """Test PJLink state code mapping."""
    test_cases = [
        (b'%1POWR=0\r', 0),  # off
        (b'%1POWR=1\r', 1),  # on
        (b'%1POWR=2\r', 2),  # cooling
        (b'%1POWR=3\r', 3),  # warming
    ]

    for response, expected_state in test_cases:
        # Use unique device ID for each test case to avoid cooldown
        mock_device.id = uuid4()

        with patch('socket.socket') as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            mock_sock.recv.side_effect = [
                b'PJLINK 0\r',
                response
            ]

            result = await manager.get_state(mock_device)

            assert result.success is True
            assert result.state == expected_state


@pytest.mark.asyncio
async def test_invalid_response(manager, mock_device):
    """Test handling of invalid response."""
    with patch('socket.socket') as mock_socket_class:
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            b'PJLINK 0\r',
            b'INVALID RESPONSE\r'
        ]

        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # Unknown state
