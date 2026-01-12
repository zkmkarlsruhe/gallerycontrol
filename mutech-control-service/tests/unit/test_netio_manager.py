"""Unit tests for NETIO manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import httpx

from mutech_control.devices.netio_manager import NETIOManager
from mutech_control.devices.base import DeviceResult, ConnectionResult


@pytest.fixture
def config():
    """Test configuration for NETIO."""
    return {
        "cooldown_seconds": 1,
        "request_timeout": 5,
    }


@pytest.fixture
def mock_device():
    """Mock device model."""
    device = MagicMock()
    device.id = uuid4()
    device.host = "192.168.1.101"
    device.port = 1
    device.state = 0
    device.config = {"username": "netio", "password": "netio"}
    return device


@pytest.fixture
def manager(config):
    """Create NETIO manager instance."""
    return NETIOManager(config)


@pytest.mark.asyncio
async def test_get_state_success(manager, mock_device):
    """Test successful state query."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [
            {"ID": 1, "State": 1, "Name": "Port 1"},
            {"ID": 2, "State": 0, "Name": "Port 2"},
        ]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 1  # Port 1 is on
        assert result.error is None


@pytest.mark.asyncio
async def test_get_state_port_2(manager, mock_device):
    """Test state query for different port."""
    mock_device.port = 2

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [
            {"ID": 1, "State": 1},
            {"ID": 2, "State": 0},
        ]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == 0  # Port 2 is off


@pytest.mark.asyncio
async def test_set_power_on(manager, mock_device):
    """Test power on command."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch.object(manager.http_client, 'post', return_value=mock_response):
        result = await manager.set_power(mock_device, True)

        assert result.success is True
        assert result.state == 1  # on
        assert result.error is None


@pytest.mark.asyncio
async def test_set_power_off(manager, mock_device):
    """Test power off command."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch.object(manager.http_client, 'post', return_value=mock_response):
        result = await manager.set_power(mock_device, False)

        assert result.success is True
        assert result.state == 0  # off
        assert result.error is None


@pytest.mark.asyncio
async def test_authentication_used(manager, mock_device):
    """Test that Basic Authentication is used."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [{"ID": 1, "State": 1}]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response) as mock_get:
        await manager.get_state(mock_device)

        # Verify auth parameter was passed
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert 'auth' in call_kwargs
        auth = call_kwargs['auth']
        assert isinstance(auth, httpx.BasicAuth)


@pytest.mark.asyncio
async def test_http_error(manager, mock_device):
    """Test HTTP error handling."""
    mock_response = MagicMock()
    mock_response.status_code = 401  # Unauthorized

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert "401" in result.error


@pytest.mark.asyncio
async def test_timeout_error(manager, mock_device):
    """Test timeout handling."""
    with patch.object(manager.http_client, 'get', side_effect=TimeoutError("Request timeout")):
        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert result.error is not None


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_requests(manager, mock_device):
    """Test that cooldown prevents rapid polling."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [{"ID": 1, "State": 1}]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response):
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
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [{"ID": 1, "State": 1}]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.test_connection(mock_device)

        assert result.success is True
        assert result.error is None


@pytest.mark.asyncio
async def test_test_connection_auth_failure(manager, mock_device):
    """Test connection test with authentication failure."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.test_connection(mock_device)

        assert result.success is False
        assert "Authentication failed" in result.error


@pytest.mark.asyncio
async def test_port_not_found(manager, mock_device):
    """Test handling when requested port doesn't exist."""
    mock_device.port = 10  # Invalid port

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Outputs": [
            {"ID": 1, "State": 1},
            {"ID": 2, "State": 0},
        ]
    }

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # Port not found


@pytest.mark.asyncio
async def test_invalid_json_response(manager, mock_device):
    """Test handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"Invalid": "format"}  # Missing Outputs

    with patch.object(manager.http_client, 'get', return_value=mock_response):
        result = await manager.get_state(mock_device)

        assert result.success is True
        assert result.state == -1  # No outputs found


@pytest.mark.asyncio
async def test_connection_refused(manager, mock_device):
    """Test handling of connection refused."""
    with patch.object(manager.http_client, 'get', side_effect=ConnectionRefusedError("Connection refused")):
        result = await manager.get_state(mock_device)

        assert result.success is False
        assert result.state == -1
        assert result.error is not None
