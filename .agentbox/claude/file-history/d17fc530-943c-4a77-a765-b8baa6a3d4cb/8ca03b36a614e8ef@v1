"""State verifier - handles OFF command verification with retries."""

import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class StateVerifier:
    """Verify device states after OFF commands and retry if needed."""

    def __init__(self, db_manager, device_managers: Dict, config: dict):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self._active_verifications: Dict[str, asyncio.Task] = {}  # device_id -> task

    async def verify_devices_off(self, devices: list) -> None:
        """Start verification tasks for multiple devices."""
        for device in devices:
            device_id = str(device.id)
            if device_id not in self._active_verifications:
                task = asyncio.create_task(self._verify_single_device(device))
                self._active_verifications[device_id] = task
                logger.info(f"Started OFF verification for device {device.name} ({device_id})")

    async def _verify_single_device(self, device) -> None:
        """Verify a single device turned off with retries."""
        device_id = str(device.id)

        try:
            # Get device type config
            device_type_config = self.config.get("device_types", {}).get(device.device_type, {})
            verify_config = device_type_config.get("off_verify", {})

            if not verify_config.get("enabled", False):
                logger.info(f"OFF verification disabled for device type {device.device_type}")
                return

            interval = verify_config.get("interval_seconds", 30)
            max_duration = verify_config.get("max_duration_seconds", 300)
            retry_on_states = verify_config.get("retry_on_states", [1, -1])
            success_states = verify_config.get("success_states", [0, 2])

            manager = self.device_managers.get(device.device_type)
            if not manager:
                logger.error(f"No manager found for device type {device.device_type}")
                return

            start_time = asyncio.get_event_loop().time()
            attempts = 0

            while (asyncio.get_event_loop().time() - start_time) < max_duration:
                await asyncio.sleep(interval)
                attempts += 1

                logger.info(f"OFF verification check #{attempts} for {device.name}")

                # Check state
                result = await manager.get_state(device)

                if not result.success:
                    logger.warning(
                        f"Verification check failed for {device.name}: {result.error}"
                    )
                    continue

                if result.state in success_states:
                    logger.info(
                        f"Device {device.name} verified OFF after {attempts} checks (state={result.state})"
                    )
                    # Update database
                    await self._update_device_state(device_id, result.state)
                    return

                if result.state in retry_on_states:
                    # Still on or error - resend OFF command
                    logger.warning(
                        f"Device {device.name} still in state {result.state}, resending OFF"
                    )
                    retry_result = await manager.set_power(device, False)

                    # Log retry command
                    await self._log_command(
                        device_id=device_id,
                        command="off",
                        source="verification",
                        success=retry_result.success,
                        error=retry_result.error,
                        duration_ms=retry_result.duration_ms,
                    )

            # Max duration exceeded
            logger.error(
                f"Device {device.name} failed to verify OFF after {max_duration}s ({attempts} attempts)"
            )
            await self._update_device_state(device_id, -1)  # Mark as error

        except Exception as e:
            logger.error(f"Error in OFF verification for {device.name}: {e}")

        finally:
            # Clean up
            if device_id in self._active_verifications:
                del self._active_verifications[device_id]

    async def _update_device_state(self, device_id: str, new_state: int) -> None:
        """Update device state in database."""
        try:
            from datetime import datetime
            from uuid import UUID

            from sqlalchemy import update

            from mutech_control.database.models import Device

            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == UUID(device_id))
                    .values(state=new_state, last_checked_at=datetime.utcnow())
                )
                await session.execute(stmt)

        except Exception as e:
            logger.error(f"Error updating device state: {e}")

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

    def get_active_count(self) -> int:
        """Get count of active verification tasks."""
        return len(self._active_verifications)

    def is_verifying(self, device_id: str) -> bool:
        """Check if device is currently being verified."""
        return device_id in self._active_verifications
