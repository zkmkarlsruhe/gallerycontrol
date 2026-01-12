"""Unit tests for Shell manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import asyncio

from mutech_control.devices.shell_manager import ShellManager
from mutech_control.devices.base import DeviceResult, ConnectionResult


@pytest.fixture
def config():
    """Test configuration for Shell."""
    return {
        "cooldown_seconds": 1,
        "request_timeout": 10,
    }


@pytest.fixture
def mock_device():
    """Mock device model."""
    device = MagicMock()
    device.id = uuid4()
    device.host = "192.168.1.103"
    device.name = "Test Shell Device"
    device.state = 0
    device.config = {
        "commands": {
            "status": {
                "cmd": "ps aux | grep app",
                "onPattern": "app.*running",
                "offPattern": "^$"
            },
            "on": {
                "cmd": "./start.sh"
            },
            "off": {
                "cmd": "./stop.sh"
            }
        }
    }
    return device


@pytest.fixture
def manager(config):
    """Create Shell manager instance."""
    return ShellManager(config)


@pytest.mark.asyncio
async def test_get_state_on(manager, mock_device):
    """Test state query when service is running."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"app is running\nPID 12345", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1  # on - matches onPattern
        assert result.error is None


@pytest.mark.asyncio
async def test_get_state_off(manager, mock_device):
    """Test state query when service is off."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 0  # off - matches offPattern (empty)


@pytest.mark.asyncio
async def test_get_state_unknown(manager, mock_device):
    """Test state query when state cannot be determined."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"some other output", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # unknown - matches neither pattern


@pytest.mark.asyncio
async def test_set_power_on(manager, mock_device):
    """Test power on command."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"Started successfully", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.set_power(mock_device, True)

        assert result.success is True
        assert result.state == 1  # on
        assert result.error is None


@pytest.mark.asyncio
async def test_set_power_off(manager, mock_device):
    """Test power off command."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"Stopped successfully", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.set_power(mock_device, False)

        assert result.success is True
        assert result.state == 0  # off
        assert result.error is None


@pytest.mark.asyncio
async def test_command_failure(manager, mock_device):
    """Test handling of command failure (non-zero exit code)."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Command failed"))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.set_power(mock_device, True)

        assert result.success is False
        assert result.state == mock_device.state  # State unchanged
        assert "failed" in result.error.lower()


@pytest.mark.asyncio
async def test_timeout_error(manager, mock_device):
    """Test timeout handling."""
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_requests(manager, mock_device):
    """Test that cooldown prevents rapid polling."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"app running", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        # First request succeeds
        result1 = await manager.get_state(mock_device)
        assert result1.success is True

        # Immediate second request blocked by cooldown
        result2 = await manager.get_state(mock_device)
        assert result2.success is False
        assert "cooldown" in result2.error.lower()


@pytest.mark.asyncio
async def test_no_status_command_configured(manager, mock_device):
    """Test handling when no status command is configured."""
    mock_device.config = {"commands": {}}

    result = await manager.get_state(mock_device)

    assert result.success is False
    assert result.state == -1
    assert "no status command" in result.error.lower()


@pytest.mark.asyncio
async def test_no_on_command_configured(manager, mock_device):
    """Test handling when no on command is configured."""
    mock_device.config = {
        "commands": {
            "status": {"cmd": "echo test"},
            "off": {"cmd": "echo off"}
        }
    }

    result = await manager.set_power(mock_device, True)

    assert result.success is False
    assert "no on command" in result.error.lower()


@pytest.mark.asyncio
async def test_test_connection_success(manager, mock_device):
    """Test successful connection test."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"output", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.test_connection(mock_device)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_test_connection_failure(manager, mock_device):
    """Test connection test failure."""
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=TimeoutError("Connection timeout"))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.test_connection(mock_device)

        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
async def test_test_connection_no_status_command(manager, mock_device):
    """Test connection test when no status command configured."""
    mock_device.config = {"commands": {}}

    result = await manager.test_connection(mock_device)

    assert result.success is False
    assert "no status command" in result.error.lower()


@pytest.mark.asyncio
async def test_pattern_matching_priority(manager, mock_device):
    """Test that onPattern takes priority over offPattern."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    # Output matches onPattern
    mock_proc.communicate = AsyncMock(return_value=(b"app is running", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1  # Matched onPattern


@pytest.mark.asyncio
async def test_complex_regex_patterns(manager, mock_device):
    """Test complex regex patterns."""
    mock_device.config["commands"]["status"]["onPattern"] = r"PID:\s*\d+"
    mock_device.config["commands"]["status"]["offPattern"] = r"not\s+found"

    # Test ON match
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"Service status: PID: 12345", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1

    # Test OFF match - use different device ID to avoid cooldown
    mock_device.id = uuid4()
    mock_proc.communicate = AsyncMock(return_value=(b"Service not found", b""))

    with patch('asyncio.create_subprocess_shell', return_value=mock_proc):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 0
