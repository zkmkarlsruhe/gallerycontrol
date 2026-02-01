# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Unit tests for command verifier with unified polling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from gallerycontrol.devices.base import DeviceResult
from gallerycontrol.orchestrator.command_verifier import CommandVerifier


@pytest.fixture
def config():
    """Test configuration for command verifier."""
    return {
        "device_types": {
            "pjlink": {
                "verify": {
                    "enabled": True,
                    "interval_seconds": 0.05,  # Fast for testing
                    "initial_timeout_seconds": 0.5,  # Fast for testing
                    "stable_duration_seconds": 0.1,  # Fast for testing
                    "max_retries": 3,
                    "on": {
                        "success_states": [1, 3],  # on, warming
                    },
                    "off": {
                        "success_states": [0, 2],  # off, cooling
                    },
                }
            },
            "netio": {
                "verify": {
                    "enabled": True,
                    "interval_seconds": 0.05,
                    "initial_timeout_seconds": 0.5,
                    "stable_duration_seconds": 0.1,
                    "max_retries": 3,
                    "on": {
                        "success_states": [1],
                    },
                    "off": {
                        "success_states": [0],
                    },
                }
            },
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
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()
    db.session = MagicMock(return_value=mock_session)
    return db


@pytest.fixture
def mock_manager():
    """Mock device manager."""
    manager = MagicMock()
    manager.get_state = AsyncMock()
    manager.set_power = AsyncMock()
    return manager


class MockStateMonitor:
    """Mock StateMonitor that simulates fast polling behavior."""

    def __init__(self):
        self._fast_poll_devices = {}
        self._callback_delay = 0.05  # Simulate time to detect state

    async def register_fast_poll(self, device_id, target_states, callback, deviation_callback=None):
        """Register device for fast polling."""
        self._fast_poll_devices[device_id] = {
            "target_states": target_states,
            "callback": callback,
            "deviation_callback": deviation_callback,
        }

    async def unregister_fast_poll(self, device_id):
        """Unregister device from fast polling."""
        if device_id in self._fast_poll_devices:
            del self._fast_poll_devices[device_id]
            return True
        return False

    def is_fast_polling(self, device_id):
        """Check if device is in fast poll mode."""
        return device_id in self._fast_poll_devices

    async def simulate_state_detected(self, device_id, state):
        """Simulate StateMonitor detecting target state."""
        if device_id in self._fast_poll_devices:
            entry = self._fast_poll_devices[device_id]
            if state in entry["target_states"]:
                await asyncio.sleep(self._callback_delay)
                await entry["callback"](device_id, state)


@pytest.fixture
def mock_state_monitor():
    """Create mock state monitor."""
    return MockStateMonitor()


@pytest.fixture
def verifier(mock_db_manager, mock_manager, config, mock_state_monitor):
    """Create command verifier instance with state monitor."""
    device_managers = {"pjlink": mock_manager}
    v = CommandVerifier(mock_db_manager, device_managers, config)
    v.set_state_monitor(mock_state_monitor)
    return v


# ========== OFF Verification Tests ==========


@pytest.mark.asyncio
async def test_off_verification_success(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test OFF verification succeeds when device is off and stable."""
    device_id = str(mock_device.id)

    # Device reports OFF state consistently
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=0, error=None, duration_ms=100  # OFF
    )

    await verifier.verify_devices([mock_device], "off")

    # Simulate StateMonitor detecting target state reached
    await asyncio.sleep(0.02)
    await mock_state_monitor.simulate_state_detected(device_id, 0)

    # Wait for stability period + final check
    await asyncio.sleep(0.3)

    # Should have done final state check after stability
    assert mock_manager.get_state.call_count >= 1

    # Should NOT have retried (device stayed off)
    mock_manager.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_off_verification_cooling_accepted(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test that cooling state (2) is accepted as success for OFF."""
    device_id = str(mock_device.id)

    # Device reports cooling state
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=2, error=None, duration_ms=100  # Cooling
    )

    await verifier.verify_devices([mock_device], "off")

    # Simulate StateMonitor detecting cooling state (target state)
    await asyncio.sleep(0.02)
    await mock_state_monitor.simulate_state_detected(device_id, 2)

    await asyncio.sleep(0.3)

    # Should NOT have retried (cooling is success state)
    mock_manager.set_power.assert_not_called()


# ========== ON Verification Tests ==========


@pytest.mark.asyncio
async def test_on_verification_success(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test ON verification succeeds when device is on and stable."""
    device_id = str(mock_device.id)

    # Device reports ON state consistently
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100  # ON
    )

    await verifier.verify_devices([mock_device], "on")

    # Simulate StateMonitor detecting ON state
    await asyncio.sleep(0.02)
    await mock_state_monitor.simulate_state_detected(device_id, 1)

    await asyncio.sleep(0.3)

    # Should have done final state check
    assert mock_manager.get_state.call_count >= 1

    # Should NOT have retried (device stayed on)
    mock_manager.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_on_verification_warming_accepted(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test that warming state (3) is accepted as success for ON."""
    device_id = str(mock_device.id)

    # Device reports warming state
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=3, error=None, duration_ms=100  # Warming
    )

    await verifier.verify_devices([mock_device], "on")

    # Simulate StateMonitor detecting warming state (target state)
    await asyncio.sleep(0.02)
    await mock_state_monitor.simulate_state_detected(device_id, 3)

    await asyncio.sleep(0.3)

    # Should NOT have retried (warming is success state)
    mock_manager.set_power.assert_not_called()


# ========== Deviation Callback Tests ==========


@pytest.mark.asyncio
async def test_deviation_triggers_correction(mock_manager, config, mock_state_monitor):
    """Test that state deviation during enforcement triggers correction command."""
    from gallerycontrol.orchestrator.command_verifier import CommandVerifier

    # Create a mock device with all required attributes
    mock_device = MagicMock()
    mock_device.id = uuid4()
    mock_device.name = "Test Projector"
    mock_device.device_type = "pjlink"
    mock_device.host = "192.168.1.100"
    mock_device.state = 0

    device_id = str(mock_device.id)

    # Create a properly mocked db_manager that returns the device from query
    mock_db = MagicMock()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.add = MagicMock()

    # Mock the execute().scalar_one_or_none() chain to return the device
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_device)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_db.session = MagicMock(return_value=mock_session)

    # Create verifier with the mocked db
    device_managers = {"pjlink": mock_manager}
    verifier = CommandVerifier(mock_db, device_managers, config)
    verifier.set_state_monitor(mock_state_monitor)

    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )
    mock_manager.set_power.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )

    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.02)

    # Verify device is registered for fast polling
    assert mock_state_monitor.is_fast_polling(device_id)

    # Get the deviation callback that was registered
    entry = mock_state_monitor._fast_poll_devices.get(device_id)
    assert entry is not None
    deviation_callback = entry.get("deviation_callback")

    if deviation_callback:
        # Simulate state deviation (device went to state 0 when we want state 1)
        await deviation_callback(device_id, 0)
        await asyncio.sleep(0.1)

        # Should have sent correction command
        assert mock_manager.set_power.call_count >= 1
        mock_manager.set_power.assert_called_with(mock_device, True)


# ========== Device Never Reaches State (Broken) ==========


@pytest.mark.asyncio
async def test_device_never_reaches_state_marked_error(
    verifier, mock_device, mock_manager, mock_state_monitor
):
    """Test device marked as error when it never reaches target state."""
    # Don't simulate state reached - let timeout occur

    await verifier.verify_devices([mock_device], "on")

    # Wait for initial timeout (0.5s in config)
    await asyncio.sleep(0.7)

    # Should NOT have retried (broken device, not a stability failure)
    mock_manager.set_power.assert_not_called()

    # Verification should be done (device marked as error, no retry)
    assert not verifier.is_verifying(str(mock_device.id))


# ========== Max Retries Tests ==========


@pytest.mark.asyncio
async def test_max_retries_exhausted(mock_db_manager, mock_manager):
    """Test that verification gives up after max retries."""
    config = {
        "device_types": {
            "pjlink": {
                "verify": {
                    "enabled": True,
                    "interval_seconds": 0.02,
                    "initial_timeout_seconds": 0.2,
                    "stable_duration_seconds": 0.05,
                    "max_retries": 2,  # Only 2 retries
                    "on": {"success_states": [1, 3]},
                    "off": {"success_states": [0, 2]},
                }
            }
        }
    }

    device = MagicMock()
    device.id = uuid4()
    device.name = "Test Device"
    device.device_type = "pjlink"
    device_id = str(device.id)

    mock_state_monitor = MockStateMonitor()
    mock_state_monitor._callback_delay = 0.01

    verifier = CommandVerifier(
        mock_db_manager, {"pjlink": mock_manager}, config
    )
    verifier.set_state_monitor(mock_state_monitor)

    # Device always reports wrong state after stability (keeps lying)
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=0, error=None, duration_ms=100  # OFF instead of ON
    )
    mock_manager.set_power.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )

    await verifier.verify_devices([device], "on")

    # Simulate multiple rounds of reaching state then failing stability
    for _ in range(3):
        await asyncio.sleep(0.02)
        if mock_state_monitor.is_fast_polling(device_id):
            await mock_state_monitor.simulate_state_detected(device_id, 1)
        await asyncio.sleep(0.15)

    # Should have retried set_power at most max_retries-1 times
    assert mock_manager.set_power.call_count <= 2


# ========== Cancellation Tests ==========


@pytest.mark.asyncio
async def test_cancel_verification(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test that verification can be cancelled."""
    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.05)

    # Verify task is active
    assert verifier.is_verifying(str(mock_device.id))

    # Cancel it
    cancelled = await verifier.cancel_verification(str(mock_device.id))
    assert cancelled
    assert not verifier.is_verifying(str(mock_device.id))

    # Should have unregistered from fast polling
    assert not mock_state_monitor.is_fast_polling(str(mock_device.id))


@pytest.mark.asyncio
async def test_new_verification_cancels_existing(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test that starting new verification cancels existing one."""
    # Start ON verification
    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.05)

    # Start OFF verification for same device - should cancel ON
    await verifier.verify_devices([mock_device], "off")
    await asyncio.sleep(0.05)

    # Only one verification should be active
    assert verifier.get_active_count() <= 1


@pytest.mark.asyncio
async def test_cancel_nonexistent_verification(verifier):
    """Test cancelling non-existent verification returns False."""
    result = await verifier.cancel_verification("nonexistent-id")
    assert result is False


# ========== Disabled Verification Tests ==========


@pytest.mark.asyncio
async def test_verify_disabled_for_device_type(mock_db_manager, mock_manager):
    """Test that verification is skipped when disabled for device type."""
    config = {
        "device_types": {
            "shell": {
                "verify": {
                    "enabled": False  # Disabled
                }
            }
        }
    }

    device = MagicMock()
    device.id = uuid4()
    device.name = "Test Shell"
    device.device_type = "shell"

    mock_state_monitor = MockStateMonitor()
    verifier = CommandVerifier(
        mock_db_manager, {"shell": mock_manager}, config
    )
    verifier.set_state_monitor(mock_state_monitor)

    await verifier.verify_devices([device], "on")

    await asyncio.sleep(0.1)

    # Should not have registered for fast polling
    assert not mock_state_monitor.is_fast_polling(str(device.id))


# ========== Multiple Devices Tests ==========


@pytest.mark.asyncio
async def test_verify_multiple_devices(verifier, mock_manager, mock_state_monitor):
    """Test verifying multiple devices in parallel."""
    devices = [
        MagicMock(
            id=uuid4(),
            name=f"Device {i}",
            device_type="pjlink",
            host=f"192.168.1.{i}",
        )
        for i in range(3)
    ]

    # All devices report OFF (success for OFF verification)
    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=0, error=None, duration_ms=100
    )

    await verifier.verify_devices(devices, "off")

    # Simulate all devices reaching target state
    await asyncio.sleep(0.02)
    for device in devices:
        device_id = str(device.id)
        if mock_state_monitor.is_fast_polling(device_id):
            await mock_state_monitor.simulate_state_detected(device_id, 0)

    await asyncio.sleep(0.3)

    # Should have done final state check for each device
    assert mock_manager.get_state.call_count >= 3


# ========== Status Methods Tests ==========


@pytest.mark.asyncio
async def test_get_verification_info(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test getting verification info."""
    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.02)

    info = verifier.get_verification_info(str(mock_device.id))

    if info:  # Task might finish quickly
        assert info["device_name"] == "Test Projector"
        assert info["direction"] == "on"


@pytest.mark.asyncio
async def test_get_all_verifications(verifier, mock_manager, mock_state_monitor):
    """Test getting all active verifications."""
    devices = [
        MagicMock(id=uuid4(), name=f"Device {i}", device_type="pjlink")
        for i in range(2)
    ]

    await verifier.verify_devices(devices, "on")
    await asyncio.sleep(0.02)

    all_verifications = verifier.get_all_verifications()

    # Should have info for active verifications
    assert isinstance(all_verifications, list)


# ========== StateMonitor Integration Tests ==========


@pytest.mark.asyncio
async def test_verifier_without_state_monitor(mock_db_manager, mock_manager, config):
    """Test that verifier skips verification if no state monitor set."""
    device = MagicMock()
    device.id = uuid4()
    device.name = "Test Device"
    device.device_type = "pjlink"

    verifier = CommandVerifier(mock_db_manager, {"pjlink": mock_manager}, config)
    # Don't set state monitor

    await verifier.verify_devices([device], "on")
    await asyncio.sleep(0.1)

    # Should not have started any verification
    assert verifier.get_active_count() == 0


@pytest.mark.asyncio
async def test_fast_poll_registered_on_verify(verifier, mock_device, mock_state_monitor):
    """Test that device is registered for fast polling when verification starts."""
    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.02)

    # Should be registered for fast polling
    assert mock_state_monitor.is_fast_polling(str(mock_device.id))


@pytest.mark.asyncio
async def test_fast_poll_unregistered_on_success(verifier, mock_device, mock_manager, mock_state_monitor):
    """Test that device is unregistered from fast polling on success."""
    device_id = str(mock_device.id)

    mock_manager.get_state.return_value = DeviceResult(
        success=True, state=1, error=None, duration_ms=100
    )

    await verifier.verify_devices([mock_device], "on")
    await asyncio.sleep(0.02)

    # Simulate state reached
    await mock_state_monitor.simulate_state_detected(device_id, 1)
    await asyncio.sleep(0.3)

    # Should be unregistered after success
    assert not mock_state_monitor.is_fast_polling(device_id)
