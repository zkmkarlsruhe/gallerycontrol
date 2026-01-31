# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Tests for ANEL runner API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from anel_runner.core.anel_service import CommandResult, StateResult


# We need to patch the service before importing the app
@pytest.fixture
def mock_service():
    """Create a mock ANEL service."""
    service = MagicMock()
    service.queue_length = 0
    service.is_processing = False

    # Default return values
    service.get_power_state = AsyncMock(
        return_value=StateResult(
            success=True,
            host="192.168.1.100",
            port=0,
            state=1,
            name="Test Port",
        )
    )

    service.set_power_state = AsyncMock(
        return_value=CommandResult(
            success=True,
            host="192.168.1.100",
            port=0,
            command="on",
            state=1,
        )
    )

    service.get_device_info = AsyncMock(return_value=None)

    return service


@pytest.fixture
def client(mock_service):
    """Create test client with mocked service."""
    # Import app after setting up mocks
    from anel_runner.main import app

    # Patch the service in app state
    app.state.anel_service = mock_service
    app.state.config = MagicMock()
    app.state.config.udp_send_port = 9975
    app.state.config.udp_receive_port = 9977
    app.state.config.command_delay_seconds = 0.5

    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client, mock_service):
        """Test health check returns status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "queue_length" in data
        assert "is_processing" in data


class TestInfoEndpoint:
    """Tests for /info endpoint."""

    def test_info(self, client):
        """Test info endpoint returns configuration."""
        response = client.get("/info")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "udp_send_port" in data
        assert "udp_receive_port" in data


class TestStateEndpoint:
    """Tests for /devices/{host}/state endpoint."""

    def test_get_state_success(self, client, mock_service):
        """Test getting port state."""
        response = client.get("/devices/192.168.1.100/state?port=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["host"] == "192.168.1.100"
        assert data["port"] == 0
        assert data["state"] == 1

    def test_get_state_invalid_port(self, client):
        """Test getting state with invalid port."""
        response = client.get("/devices/192.168.1.100/state?port=10")

        assert response.status_code == 422  # Validation error

    def test_get_state_missing_port(self, client):
        """Test getting state without port parameter."""
        response = client.get("/devices/192.168.1.100/state")

        assert response.status_code == 422  # Validation error

    def test_get_state_error(self, client, mock_service):
        """Test handling state query error."""
        mock_service.get_power_state = AsyncMock(
            return_value=StateResult(
                success=False,
                host="192.168.1.100",
                port=0,
                state=-1,
                error="Connection timeout",
            )
        )

        response = client.get("/devices/192.168.1.100/state?port=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Connection timeout"


class TestPowerOnEndpoint:
    """Tests for /devices/{host}/on endpoint."""

    def test_power_on_success(self, client, mock_service):
        """Test power on command."""
        response = client.post("/devices/192.168.1.100/on?port=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["command"] == "on"
        assert data["state"] == 1

        # Verify service was called correctly
        mock_service.set_power_state.assert_called_once()
        call_kwargs = mock_service.set_power_state.call_args.kwargs
        assert call_kwargs["host"] == "192.168.1.100"
        assert call_kwargs["port"] == 0
        assert call_kwargs["state"] is True

    def test_power_on_fast_lane(self, client, mock_service):
        """Test power on with fast lane."""
        response = client.post("/devices/192.168.1.100/on?port=0&fast_lane=true")

        assert response.status_code == 200

        call_kwargs = mock_service.set_power_state.call_args.kwargs
        assert call_kwargs["fast_lane"] is True

    def test_power_on_with_credentials(self, client, mock_service):
        """Test power on with custom credentials."""
        response = client.post(
            "/devices/192.168.1.100/on?port=0&user=admin&password=secret"
        )

        assert response.status_code == 200

        call_kwargs = mock_service.set_power_state.call_args.kwargs
        assert call_kwargs["user"] == "admin"
        assert call_kwargs["password"] == "secret"


class TestPowerOffEndpoint:
    """Tests for /devices/{host}/off endpoint."""

    def test_power_off_success(self, client, mock_service):
        """Test power off command."""
        mock_service.set_power_state = AsyncMock(
            return_value=CommandResult(
                success=True,
                host="192.168.1.100",
                port=0,
                command="off",
                state=0,
            )
        )

        response = client.post("/devices/192.168.1.100/off?port=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["command"] == "off"
        assert data["state"] == 0

        call_kwargs = mock_service.set_power_state.call_args.kwargs
        assert call_kwargs["state"] is False

    def test_power_off_error(self, client, mock_service):
        """Test power off error handling."""
        mock_service.set_power_state = AsyncMock(
            return_value=CommandResult(
                success=False,
                host="192.168.1.100",
                port=0,
                command="off",
                error="Device not responding",
            )
        )

        response = client.post("/devices/192.168.1.100/off?port=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not responding" in data["error"]


class TestDeviceInfoEndpoint:
    """Tests for /devices/{host}/info endpoint."""

    def test_get_device_info_success(self, client, mock_service):
        """Test getting device info."""
        from anel_runner.protocol.parser import DeviceStatus, PortStatus

        mock_service.get_device_info = AsyncMock(
            return_value=DeviceStatus(
                ip="192.168.1.100",
                name="NET-CONTROL",
                mac="00:11:22:33:44:55",
                ports=[
                    PortStatus(port=0, name="Port 1", state=1),
                    PortStatus(port=1, name="Port 2", state=0),
                ],
                temperature=25.5,
            )
        )

        response = client.get("/devices/192.168.1.100/info")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["name"] == "NET-CONTROL"
        assert len(data["ports"]) == 2
        assert data["ports"][0]["state"] == 1

    def test_get_device_info_not_found(self, client, mock_service):
        """Test device info when device not responding."""
        mock_service.get_device_info = AsyncMock(return_value=None)

        response = client.get("/devices/192.168.1.100/info")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
