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
    """Tracks a single device verification task."""

    device_id: str
    device_name: str
    device_type: str
    direction: VerificationDirection
    target_states: List[int]
    task: asyncio.Task
    state_reached_event: asyncio.Event
    reached_state: int | None = None
    attempt: int = 0
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class CommandVerifier:
    """Verify device states after ON/OFF commands with stability check and retries.

    Uses StateMonitor for polling instead of polling directly. When target state
    is reached, StateMonitor notifies via callback.

    Verification algorithm:
    1. Register with StateMonitor for fast polling until desired state reached
    2. If initial_timeout_seconds passes without reaching state -> mark as ERROR (broken)
    3. Once state reached, wait stable_duration_seconds
    4. Check state again
    5. If still in desired state -> SUCCESS
    6. If state changed (device lied) -> retry command, back to step 1
    7. After max_retries -> mark as ERROR
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

            # Create event for waiting on target state
            state_reached_event = asyncio.Event()

            # Start new verification task
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
                state_reached_event=state_reached_event,
                attempt=0,
            )

            logger.info(
                "Verification task started",
                device=device.name,
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
            attempt=task_info.attempt,
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
        task_info.state_reached_event.set()

        logger.debug(
            "State reached callback received",
            device=task_info.device_name,
            state=state,
        )

    # ========== Verification Logic ==========

    async def _verify_single_device(
        self, device, direction: VerificationDirection, verify_config: dict
    ) -> None:
        """Verify a single device with the stability-based algorithm."""
        device_id = str(device.id)

        try:
            initial_timeout = verify_config.get("initial_timeout_seconds", 300)
            stable_duration = verify_config.get("stable_duration_seconds", 300)
            max_retries = verify_config.get("max_retries", 3)

            direction_config = verify_config.get(direction.value, {})
            success_states = direction_config.get("success_states", [])

            manager = self.device_managers.get(device.device_type)
            if not manager:
                logger.error(f"No manager found for device type {device.device_type}")
                return

            attempt = 0

            while attempt < max_retries:
                attempt += 1
                self._update_attempt_count(device_id, attempt)

                logger.info(
                    "Verification attempt started",
                    device=device.name,
                    direction=direction.value.upper(),
                    attempt=f"{attempt}/{max_retries}",
                )

                # Phase 1: Register for fast polling and wait for target state
                task_info = self._active_verifications[device_id]
                task_info.state_reached_event.clear()
                task_info.reached_state = None

                # Register with StateMonitor for fast polling
                self.state_monitor.register_fast_poll(
                    device_id=device_id,
                    target_states=success_states,
                    callback=self.on_state_reached,
                )

                try:
                    # Wait for StateMonitor to notify us that target state reached
                    await asyncio.wait_for(
                        task_info.state_reached_event.wait(),
                        timeout=initial_timeout,
                    )
                except asyncio.TimeoutError:
                    # Device never reached state - mark as broken, stop
                    logger.error(
                        "Device failed to reach target state - marking as error",
                        device=device.name,
                        direction=direction.value.upper(),
                        timeout_seconds=initial_timeout,
                    )
                    self.state_monitor.unregister_fast_poll(device_id)
                    await update_device_state_with_log(
                        self.db_manager, UUID(device_id), -1, "verification"
                    )
                    return

                # Phase 2: Wait stable duration (keep fast polling for UI updates)
                logger.info(
                    "Initial state reached, waiting for stability",
                    device=device.name,
                    reached_state=task_info.reached_state,
                    stable_duration_seconds=stable_duration,
                )

                await asyncio.sleep(stable_duration)

                # Phase 3: Verify state is still in desired state
                # Unregister from fast polling first
                self.state_monitor.unregister_fast_poll(device_id)

                result = await manager.get_state(device)

                if result.success and result.state in success_states:
                    # SUCCESS! Device is stable in desired state
                    logger.info(
                        "Device verified successfully",
                        device=device.name,
                        direction=direction.value.upper(),
                        final_state=result.state,
                        attempts=attempt,
                    )
                    await update_device_state_with_log(
                        self.db_manager, UUID(device_id), result.state, "verification"
                    )
                    return
                else:
                    # State changed during stable period - device lied
                    current_state = result.state if result.success else -1
                    logger.warning(
                        "State changed during stability period",
                        device=device.name,
                        expected_states=success_states,
                        actual_state=current_state,
                        attempt=attempt,
                    )

                    if attempt < max_retries:
                        # Retry the command
                        await self._retry_command(device, manager, direction, attempt)
                    # Loop continues for next attempt

            # All retries exhausted
            logger.error(
                "Verification failed - max retries exceeded",
                device=device.name,
                direction=direction.value.upper(),
                max_retries=max_retries,
            )
            await update_device_state_with_log(
                self.db_manager, UUID(device_id), -1, "verification"
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

    async def _retry_command(
        self, device, manager, direction: VerificationDirection, attempt: int
    ) -> None:
        """Retry the ON or OFF command."""
        is_on = direction == VerificationDirection.ON
        command = "on" if is_on else "off"

        logger.info(
            "Retrying command", device=device.name, command=command.upper(), attempt=attempt
        )

        result = await manager.set_power(device, is_on)

        # Log retry command
        await self._log_command(
            device_id=str(device.id),
            command=command,
            source="verification",
            success=result.success,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    # ========== Helper Methods ==========

    def _get_verify_config(self, device_type: str) -> dict | None:
        """Get verification config for a device type."""
        device_types = self.config.get("device_types", {})
        device_type_config = device_types.get(device_type, {})
        verify_config = device_type_config.get("verify", {})

        if not verify_config.get("enabled", False):
            return None

        return verify_config

    def _update_attempt_count(self, device_id: str, attempt: int) -> None:
        """Update attempt count in active verification tracking."""
        if device_id in self._active_verifications:
            self._active_verifications[device_id].attempt = attempt

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
        """Get information about an active verification."""
        if device_id not in self._active_verifications:
            return None

        task_info = self._active_verifications[device_id]
        return {
            "device_id": task_info.device_id,
            "device_name": task_info.device_name,
            "device_type": task_info.device_type,
            "direction": task_info.direction.value,
            "attempt": task_info.attempt,
            "created_at": task_info.created_at,
        }

    def get_all_verifications(self) -> list:
        """Get information about all active verifications."""
        return [
            self.get_verification_info(device_id)
            for device_id in self._active_verifications
        ]
