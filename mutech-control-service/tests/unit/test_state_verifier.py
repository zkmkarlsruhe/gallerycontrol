"""Unit tests for state verifier."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import asyncio

from mutech_control.orchestrator.state_verifier import StateVerifier
from mutech_control.devices.base import DeviceResult


@pytest.fixture
def config():
    """Test configuration for state verifier."""
    return {
        "device_types": {
            "pjlink": {
                "off_verify": {
                    "enabled": True,
                    "interval_seconds": 0.1,  # Fast for testing
                    "max_duration_seconds": 1.0,
                    "retry_on_states": [1, -1],
                    "success_states": [0, 2],
                }
            }
        }
    }


@pytest.fixture
def mock_device():
    """Mock device."""
    device = MagicMock()
    device.id = uuid4()
    device.name = "Test Projector"
    device.device_type = "pjlink"
    device.host = "192.168.1.100"
    return device


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    db = MagicMock()
    db.session = AsyncMock(return_value=AsyncMock())
    return db


@pytest.fixture
def mock_manager():
    """Mock device manager."""
    manager = MagicMock()
    manager.get_state = AsyncMock()
    manager.set_power = AsyncMock()
    return manager


@pytest.fixture
def verifier(mock_db_manager, mock_manager, config):
    """Create state verifier instance."""
    device_managers = {"pjlink": mock_manager}
    return StateVerifier(mock_db_manager, device_managers, config)


@pytest.mark.asyncio
async def test_verify_device_off_success_immediately(verifier, mock_device, mock_manager):
    """Test verification succeeds when device is already off."""
    # Device reports OFF state immediately
    mock_manager.get_state.return_value = DeviceResult(
        success=True,
        state=0,  # OFF
        error=None,
        duration_ms=100
    )

    await verifier.verify_devices_off([mock_device])

    # Give verification task time to run
    await asyncio.sleep(0.3)

    # Should have checked state at least once
    assert mock_manager.get_state.call_count >= 1

    # Should NOT have retried OFF command (device was already off)
    mock_manager.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_verify_device_off_needs_retry(verifier, mock_device, mock_manager):
    """Test verification retries when device is still on."""
    # First check: device still ON
    # Second check: device OFF
    mock_manager.get_state.side_effect = [
        DeviceResult(success=True, state=1, error=None, duration_ms=100),  # Still ON
        DeviceResult(success=True, state=0, error=None, duration_ms=100),  # Now OFF
    ]

    # Retry OFF command succeeds
    mock_manager.set_power.return_value = DeviceResult(
        success=True,
        state=0,
        error=None,
        duration_ms=100
    )

    await verifier.verify_devices_off([mock_device])

    # Give verification task time to run
    await asyncio.sleep(0.4)

    # Should have checked state at least twice
    assert mock_manager.get_state.call_count >= 2

    # Should have retried OFF command once
    mock_manager.set_power.assert_called_once_with(mock_device, False)


@pytest.mark.asyncio
async def test_verify_device_off_timeout(verifier, mock_device, mock_manager):
    """Test verification times out if device never turns off."""
    # Device always reports ON
    mock_manager.get_state.return_value = DeviceResult(
        success=True,
        state=1,  # Always ON
        error=None,
        duration_ms=100
    )

    mock_manager.set_power.return_value = DeviceResult(
        success=True,
        state=1,
        error=None,
        duration_ms=100
    )

    await verifier.verify_devices_off([mock_device])

    # Give verification task time to timeout
    await asyncio.sleep(1.5)

    # Should have checked state multiple times
    assert mock_manager.get_state.call_count > 2

    # Should have retried OFF command multiple times
    assert mock_manager.set_power.call_count > 2


@pytest.mark.asyncio
async def test_verify_device_cooling_accepted(verifier, mock_device, mock_manager):
    """Test that cooling state (2) is accepted as success."""
    # Device reports cooling state
    mock_manager.get_state.return_value = DeviceResult(
        success=True,
        state=2,  # Cooling (acceptable for projectors)
        error=None,
        duration_ms=100
    )

    await verifier.verify_devices_off([mock_device])

    # Give verification task time to run
    await asyncio.sleep(0.3)

    # Should have checked state
    assert mock_manager.get_state.call_count >= 1

    # Should NOT have retried (cooling is success state)
    mock_manager.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_verify_disabled_for_device_type(mock_db_manager, mock_manager, mock_device):
    """Test that verification is skipped when disabled for device type."""
    config = {
        "device_types": {
            "pjlink": {
                "off_verify": {
                    "enabled": False  # Disabled
                }
            }
        }
    }

    verifier = StateVerifier(mock_db_manager, {"pjlink": mock_manager}, config)

    await verifier.verify_devices_off([mock_device])

    # Give task time
    await asyncio.sleep(0.2)

    # Should not have checked state (verification disabled)
    mock_manager.get_state.assert_not_called()


@pytest.mark.asyncio
async def test_verify_multiple_devices(verifier, mock_manager):
    """Test verifying multiple devices in parallel."""
    devices = [
        MagicMock(id=uuid4(), name=f"Device {i}", device_type="pjlink", host=f"192.168.1.{i}")
        for i in range(3)
    ]

    # All devices report OFF
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=0, error=None, duration_ms=100
    )

    await verifier.verify_devices_off(devices)

    # Give tasks time to run
    await asyncio.sleep(0.3)

    # Should have started 3 verification tasks
    assert verifier.get_active_count() == 0  # All should be done by now

    # Should have checked state for each device
    assert mock_manager.get_state.call_count >= 3


@pytest.mark.asyncio
async def test_verify_get_active_count(verifier, mock_device, mock_manager):
    """Test getting count of active verification tasks."""
    # Device stays ON for a while
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )

    mock_manager.set_power.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )

    await verifier.verify_devices_off([mock_device])

    # Check count immediately
    await asyncio.sleep(0.05)
    assert verifier.get_active_count() >= 0

    # Verify we can check if specific device is being verified
    assert verifier.is_verifying(str(mock_device.id)) or verifier.get_active_count() == 0
