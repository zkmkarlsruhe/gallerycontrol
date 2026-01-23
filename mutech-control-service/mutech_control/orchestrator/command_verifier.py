"""Command verifier - handles ON and OFF command verification with stability checks."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Literal
from uuid import UUID

from mutech_control.database.state_logger import update_device_state_with_log
from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.monitoring.state_monitor import StateMonitor

logger = get_logger(__name__)


class VerificationDirection(Enum):
    """Direction of verification."""

    ON = "on"
    OFF = "off"


@dataclass
class VerificationTask:
    """Tracks a single device enforcement task."""

    device_id: str
    device_name: str
    device_type: str
    direction: VerificationDirection
    target_states: List[int]
    task: asyncio.Task
    enforcement_duration: int = 300  # Duration in seconds (default 5 min)
    reached_state: int | None = None
    deviated_state: int | None = None
    correction_count: int = 0  # Number of correction commands sent
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class CommandVerifier:
    """Verify and enforce device states after ON/OFF commands.

    Uses StateMonitor for polling instead of polling directly.

    Active Enforcement Algorithm:
    1. Start active enforcement period (default 5 minutes)
    2. Register with StateMonitor for fast polling (every 30s)
    3. On every poll during the period:
       - If state is correct (in success_states): good, keep monitoring
       - If state is wrong: immediately send command to correct it
       - If device is offline: skip, don't mark as error
    4. Period ends when timer expires:
       - Final state check: correct -> SUCCESS, wrong -> ERROR
    5. Frontend command cancels current enforcement and starts fresh with new target
    """

    def __init__(
        self,
        db_manager,
        device_managers: Dict,
        config: dict,
        state_monitor: "StateMonitor | None" = None,
    ):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self.state_monitor = state_monitor
        self._active_verifications: Dict[str, VerificationTask] = {}

    def set_state_monitor(self, state_monitor: "StateMonitor") -> None:
        """Set state monitor reference (for deferred initialization)."""
        self.state_monitor = state_monitor

    # ========== Public API ==========

    async def verify_devices(
        self, devices: list, direction: Literal["on", "off"]
    ) -> None:
        """Start verification tasks for multiple devices."""
        if not self.state_monitor:
            logger.warning("StateMonitor not set, skipping verification")
            return

        ver_direction = VerificationDirection(direction)
        logger.info(
            "Starting verification tasks",
            direction=direction.upper(),
            device_count=len(devices),
        )

        for device in devices:
            device_id = str(device.id)

            # Cancel any existing verification for this device
            if device_id in self._active_verifications:
                await self.cancel_verification(device_id)

            # Get verification config for this device type
            verify_config = self._get_verify_config(device.device_type)
            if not verify_config:
                logger.info(
                    f"Verification disabled for device type {device.device_type}"
                )
                continue

            direction_config = verify_config.get(direction, {})
            success_states = direction_config.get("success_states", [])

            if not success_states:
                logger.warning(
                    f"No success states defined for {direction} verification",
                    device_type=device.device_type,
                )
                continue

            enforcement_duration = verify_config.get("stable_duration_seconds", 300)

            # Start new enforcement task
            task = asyncio.create_task(
                self._verify_single_device(device, ver_direction, verify_config)
            )

            self._active_verifications[device_id] = VerificationTask(
                device_id=device_id,
                device_name=device.name,
                device_type=device.device_type,
                direction=ver_direction,
                target_states=success_states,
                task=task,
                enforcement_duration=enforcement_duration,
                correction_count=0,
            )

            logger.info(
                "Enforcement task started",
                device=device.name,
                enforcement_duration_seconds=enforcement_duration,
                device_id=device_id[:8],
                direction=direction.upper(),
                type=device.device_type,
            )

    async def cancel_verification(self, device_id: str) -> bool:
        """Cancel an active verification for a device.

        Returns True if a verification was cancelled, False if none was active.
        """
        if device_id not in self._active_verifications:
            return False

        task_info = self._active_verifications[device_id]
        logger.info(
            "Cancelling active verification",
            device=task_info.device_name,
            device_id=device_id[:8],
            direction=task_info.direction.value.upper(),
        )

        # Unregister from fast polling
        if self.state_monitor:
            self.state_monitor.unregister_fast_poll(device_id)

        task_info.task.cancel()
        try:
            await task_info.task
        except asyncio.CancelledError:
            pass

        # Task's finally block may have already cleaned up
        if device_id in self._active_verifications:
            del self._active_verifications[device_id]
        return True

    async def cancel_all_verifications(self) -> int:
        """Cancel all active verifications. Returns count of cancelled tasks."""
        count = len(self._active_verifications)
        device_ids = list(self._active_verifications.keys())

        for device_id in device_ids:
            await self.cancel_verification(device_id)

        logger.info("All verifications cancelled", count=count)
        return count

    # ========== Callback from StateMonitor ==========

    async def on_state_reached(self, device_id: str, state: int) -> None:
        """Callback from StateMonitor when device reaches target state.

        This is called by StateMonitor when a fast-poll device reaches
        one of its target states.
        """
        if device_id not in self._active_verifications:
            return

        task_info = self._active_verifications[device_id]
        task_info.reached_state = state

        # Calculate remaining enforcement time
        elapsed = asyncio.get_event_loop().time() - task_info.created_at
        remaining = max(0, task_info.enforcement_duration - elapsed)

        logger.info(
            "State OK during enforcement",
            device=task_info.device_name,
            state=state,
            enforcement_remaining_seconds=int(remaining),
            corrections_sent=task_info.correction_count,
        )

    async def on_state_deviated(self, device_id: str, state: int) -> None:
        """Callback from StateMonitor when device state deviates from target.

        During active enforcement, this triggers an immediate correction command.
        We keep trying for the full enforcement period (no max retries).
        """
        if device_id not in self._active_verifications:
            return

        task_info = self._active_verifications[device_id]
        task_info.deviated_state = state
        task_info.correction_count += 1

        # Calculate remaining enforcement time
        elapsed = asyncio.get_event_loop().time() - task_info.created_at
        remaining = max(0, task_info.enforcement_duration - elapsed)

        logger.warning(
            "State WRONG during enforcement - sending correction",
            device=task_info.device_name,
            detected_state=state,
            target_states=task_info.target_states,
            enforcement_remaining_seconds=int(remaining),
            correction_count=task_info.correction_count,
        )

        # Send correction command
        await self._send_correction_command(device_id, task_info)

    async def _send_correction_command(self, device_id: str, task_info: VerificationTask) -> None:
        """Send correction command to device during active enforcement."""
        # We need to get the device from DB to send the command
        try:
            from mutech_control.database.models import Device
            from sqlalchemy import select

            async with self.db_manager.session() as session:
                stmt = select(Device).where(Device.id == UUID(device_id))
                result = await session.execute(stmt)
                device = result.scalar_one_or_none()

                if device:
                    manager = self.device_managers.get(device.device_type)
                    if manager:
                        is_on = task_info.direction == VerificationDirection.ON
                        command = "on" if is_on else "off"

                        result = await manager.set_power(device, is_on)

                        logger.info(
                            "Correction command sent",
                            device=device.name,
                            command=command,
                            success=result.success,
                            correction_count=task_info.correction_count,
                        )

                        # Log the correction command
                        await self._log_command(
                            device_id=device_id,
                            command=command,
                            source="enforcement",
                            success=result.success,
                            error=result.error,
                            duration_ms=result.duration_ms,
                        )
        except Exception as e:
            logger.error(
                "Error sending correction command",
                device_id=device_id[:8],
                error=str(e),
            )

    # ========== Verification Logic ==========

    async def _verify_single_device(
        self, device, direction: VerificationDirection, verify_config: dict
    ) -> None:
        """Active enforcement for a single device.

        Runs for the full enforcement period (default 5 min), sending correction
        commands whenever the state deviates from target. No max retries - we
        keep trying for the entire period.
        """
        device_id = str(device.id)

        try:
            enforcement_duration = verify_config.get("stable_duration_seconds", 300)

            direction_config = verify_config.get(direction.value, {})
            success_states = direction_config.get("success_states", [])

            manager = self.device_managers.get(device.device_type)
            if not manager:
                logger.error(f"No manager found for device type {device.device_type}")
                return

            task_info = self._active_verifications[device_id]

            logger.info(
                "Active enforcement started",
                device=device.name,
                direction=direction.value.upper(),
                duration_seconds=enforcement_duration,
            )

            # Register with StateMonitor for fast polling
            # The deviation_callback will handle corrections automatically
            self.state_monitor.register_fast_poll(
                device_id=device_id,
                target_states=success_states,
                callback=self.on_state_reached,
                deviation_callback=self.on_state_deviated,
            )

            # Wait for the full enforcement period
            await asyncio.sleep(enforcement_duration)

            # Enforcement period ended - do final state check
            self.state_monitor.unregister_fast_poll(device_id)

            result = await manager.get_state(device)

            if result.success and result.state in success_states:
                # SUCCESS! Device is in correct state at end of enforcement
                logger.info(
                    "Active enforcement completed successfully",
                    device=device.name,
                    direction=direction.value.upper(),
                    final_state=result.state,
                    corrections_sent=task_info.correction_count,
                )
                await update_device_state_with_log(
                    self.db_manager, UUID(device_id), result.state, "enforcement"
                )
            elif not result.success:
                # Device offline at end - don't mark as error, just log
                logger.warning(
                    "Device offline at end of enforcement period - skipping",
                    device=device.name,
                    direction=direction.value.upper(),
                    error=result.error,
                )
            else:
                # State is wrong at end of enforcement
                logger.error(
                    "Active enforcement failed - wrong state at end",
                    device=device.name,
                    direction=direction.value.upper(),
                    expected_states=success_states,
                    actual_state=result.state,
                    corrections_sent=task_info.correction_count,
                )
                await update_device_state_with_log(
                    self.db_manager, UUID(device_id), -1, "enforcement"
                )

        except asyncio.CancelledError:
            logger.info(
                "Verification cancelled",
                device=device.name,
                direction=direction.value.upper(),
            )
            raise  # Re-raise to propagate cancellation

        except Exception as e:
            logger.error(
                "Error in verification task",
                device=device.name,
                direction=direction.value.upper(),
                error=str(e),
            )

        finally:
            # Clean up - ensure unregistered from fast polling
            if self.state_monitor:
                self.state_monitor.unregister_fast_poll(device_id)
            if device_id in self._active_verifications:
                del self._active_verifications[device_id]

    # ========== Helper Methods ==========

    def _get_verify_config(self, device_type: str) -> dict | None:
        """Get verification config for a device type."""
        device_types = self.config.get("device_types", {})
        device_type_config = device_types.get(device_type, {})
        verify_config = device_type_config.get("verify", {})

        if not verify_config.get("enabled", False):
            return None

        return verify_config

    async def _log_command(
        self,
        device_id: str,
        command: str,
        source: str,
        success: bool,
        error: str | None,
        duration_ms: int | None,
    ) -> None:
        """Log command to database."""
        try:
            from uuid import UUID

            from mutech_control.database.models import CommandLog

            async with self.db_manager.session() as session:
                log = CommandLog(
                    device_id=UUID(device_id),
                    command=command,
                    source=source,
                    success=success,
                    error_message=error,
                    duration_ms=duration_ms,
                )
                session.add(log)

        except Exception as e:
            logger.error(f"Error logging command: {e}")

    # ========== Status Methods ==========

    def get_active_count(self) -> int:
        """Get count of active verification tasks."""
        return len(self._active_verifications)

    def is_verifying(self, device_id: str) -> bool:
        """Check if device is currently being verified."""
        return device_id in self._active_verifications

    def get_verification_info(self, device_id: str) -> dict | None:
        """Get information about an active enforcement."""
        if device_id not in self._active_verifications:
            return None

        task_info = self._active_verifications[device_id]
        elapsed = asyncio.get_event_loop().time() - task_info.created_at
        remaining = max(0, task_info.enforcement_duration - elapsed)

        return {
            "device_id": task_info.device_id,
            "device_name": task_info.device_name,
            "device_type": task_info.device_type,
            "direction": task_info.direction.value,
            "correction_count": task_info.correction_count,
            "enforcement_duration_seconds": task_info.enforcement_duration,
            "enforcement_remaining_seconds": int(remaining),
            "created_at": task_info.created_at,
        }

    def get_all_verifications(self) -> list:
        """Get information about all active verifications."""
        return [
            self.get_verification_info(device_id)
            for device_id in self._active_verifications
        ]
