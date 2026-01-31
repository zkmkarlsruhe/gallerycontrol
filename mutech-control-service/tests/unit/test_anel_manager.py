# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Unit tests for ANEL manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from mutech_control.devices.anel_manager import ANELManager
from mutech_control.devices.base import DeviceResult, ConnectionResult


@pytest.fixture
def config():
    """Test configuration for ANEL."""
    return {
        "cooldown_seconds": 1,
        "request_timeout": 5,
    }


@pytest.fixture
def mock_device():
    """Mock device model."""
    device = MagicMock()
    device.id = uuid4()
    device.host = "192.168.1.102"
    device.port = 0  # 0-based port number
    device.state = 0
    device.config = {"username": "admin", "password": "anel"}
    return device


@pytest.fixture
def manager(config):
    """Create ANEL manager instance."""
    return ANELManager(config)


@pytest.mark.asyncio
async def test_get_state_success(manager, mock_device):
    """Test successful state query."""
    # Mock UDP response - port states at position 6
    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:10101010:Port0,Port1,Port2,Port3,Port4,Port5,Port6,Port7:0:80:25.5"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1  # Port 0 is on (first character in "10101010")
        assert result.error is None


@pytest.mark.asyncio
async def test_get_state_port_off(manager, mock_device):
    """Test state query for off port."""
    # Use different device to avoid cooldown
    mock_device.id = uuid4()
    mock_device.port = 1

    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:10101010:Port0,Port1,Port2,Port3,Port4,Port5,Port6,Port7:0:80:25.5"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 0  # Port 1 is off (second character in "10101010")


@pytest.mark.asyncio
async def test_set_power_on(manager, mock_device):
    """Test power on command."""
    mock_response = "OK"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.set_power(mock_device, True)

        assert result.success is True
        assert result.state == 1  # on
        assert result.error is None


@pytest.mark.asyncio
async def test_set_power_off(manager, mock_device):
    """Test power off command."""
    mock_response = "OK"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.set_power(mock_device, False)

        assert result.success is True
        assert result.state == 0  # off
        assert result.error is None


@pytest.mark.asyncio
async def test_power_command_format(manager, mock_device):
    """Test that power commands are formatted correctly."""
    mock_response = "OK"

    with patch.object(manager, '_send_udp_command', return_value=mock_response) as mock_udp:
        await manager.set_power(mock_device, True)

        # Verify command format: Sw_on<port+1><username><password>
        mock_udp.assert_called_once()
        command = mock_udp.call_args[0][1]
        assert command == "Sw_on1adminanel"  # port 0 -> port 1, username=admin, password=anel


@pytest.mark.asyncio
async def test_power_off_command_format(manager, mock_device):
    """Test OFF command format."""
    mock_response = "OK"

    with patch.object(manager, '_send_udp_command', return_value=mock_response) as mock_udp:
        await manager.set_power(mock_device, False)

        command = mock_udp.call_args[0][1]
        assert command == "Sw_off1adminanel"  # port 0 -> port 1


@pytest.mark.asyncio
async def test_unexpected_response(manager, mock_device):
    """Test handling of unexpected response."""
    mock_response = "ERROR"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.set_power(mock_device, True)

        assert result.success is True
        assert result.state == -1  # Unknown due to unexpected response


@pytest.mark.asyncio
async def test_timeout_error(manager, mock_device):
    """Test timeout handling."""
    with patch.object(manager, '_send_udp_command', side_effect=TimeoutError("UDP timeout")):
        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_requests(manager, mock_device):
    """Test that cooldown prevents rapid polling."""
    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:10000000:Ports...:0:80:25.5"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
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
    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:00000000:Ports...:0:80:25.5"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.test_connection(mock_device)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_test_connection_failure(manager, mock_device):
    """Test connection test failure."""
    with patch.object(manager, '_send_udp_command', side_effect=TimeoutError("Connection timeout")):
        result = await manager.test_connection(mock_device)

        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
async def test_parse_invalid_status_response(manager, mock_device):
    """Test parsing of invalid status response."""
    mock_response = "INVALID"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # Cannot parse


@pytest.mark.asyncio
async def test_port_out_of_range(manager, mock_device):
    """Test handling of invalid port number."""
    mock_device.port = 10  # Out of range

    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:10101010:Ports...:0:80:25.5"

    with patch.object(manager, '_send_udp_command', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # Port out of range


@pytest.mark.asyncio
async def test_different_ports(manager, mock_device):
    """Test state query for different ports."""
    mock_response = "NET-PwrCtrl:TestDevice:192.168.1.102:255.255.255.0:192.168.1.1:00:11:22:33:44:55:10101010:Ports...:0:80:25.5"

    test_cases = [
        (0, 1),  # First port on
        (1, 0),  # Second port off
        (2, 1),  # Third port on
        (3, 0),  # Fourth port off
        (4, 1),  # Fifth port on
    ]

    for port, expected_state in test_cases:
        # Use unique device ID for each port to avoid cooldown
        mock_device.id = uuid4()
        mock_device.port = port

        with patch.object(manager, '_send_udp_command', return_value=mock_response):
            result = await manager.get_state(mock_device)

            assert result.success is True
            assert result.state == expected_state, f"Port {port} should be {expected_state}"
