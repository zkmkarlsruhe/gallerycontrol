"""State monitoring service - periodically polls device states."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List

from sqlalchemy import select, update

from mutech_control.database.models import Device
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FastPollEntry:
    """Tracks a device registered for fast polling during verification."""

    device_id: str
    target_states: List[int]
    callback: Callable[[str, int], Awaitable[None]]  # async callback(device_id, state)
    registered_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class StateMonitor:
    """Background service that monitors device states with adaptive polling intervals.

    Normal devices are polled at the standard interval (default 60s).
    Devices in verification mode are polled at the fast interval (default 30s).
    """

    def __init__(self, db_manager, device_managers: Dict, config: dict):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self._running = False
        self._task = None

        # Get monitoring config
        monitor_config = config.get("monitoring", {})
        self.enabled = monitor_config.get("enabled", True)
        self.interval = monitor_config.get("poll_interval_seconds", 60)
        self.fast_interval = monitor_config.get("fast_poll_interval_seconds", 30)
        self.batch_size = monitor_config.get("batch_size", 10)
        self.batch_delay = monitor_config.get("batch_delay_seconds", 1.0)

        # Fast polling for verification
        self._fast_poll_devices: Dict[str, FastPollEntry] = {}

        # Track last poll time per device for adaptive intervals
        self._last_polled: Dict[str, datetime] = {}

    async def start(self):
        """Start the monitoring service."""
        if not self.enabled:
            logger.info("State monitoring disabled in configuration")
            return

        if self._running:
            logger.warning("State monitoring already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("State monitoring started",
                   interval=self.interval,
                   fast_interval=self.fast_interval,
                   batch_size=self.batch_size)

    async def stop(self):
        """Stop the monitoring service."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("State monitoring stopped")

    # ========== Fast Polling Registration ==========

    def register_fast_poll(
        self,
        device_id: str,
        target_states: List[int],
        callback: Callable[[str, int], Awaitable[None]],
    ) -> None:
        """Register a device for fast polling during verification.

        Args:
            device_id: UUID string of the device
            target_states: List of states that trigger callback (e.g., [0, 2] for OFF/cooling)
            callback: Async function called when target state reached: callback(device_id, state)
        """
        self._fast_poll_devices[device_id] = FastPollEntry(
            device_id=device_id,
            target_states=target_states,
            callback=callback,
        )
        # Clear last poll time so device gets polled on next cycle
        self._last_polled.pop(device_id, None)

        logger.info("Device registered for fast polling",
                   device_id=device_id[:8],
                   target_states=target_states)

    def unregister_fast_poll(self, device_id: str) -> bool:
        """Remove a device from fast polling.

        Returns True if device was registered, False otherwise.
        """
        if device_id in self._fast_poll_devices:
            del self._fast_poll_devices[device_id]
            logger.info("Device unregistered from fast polling",
                       device_id=device_id[:8])
            return True
        return False

    def is_fast_polling(self, device_id: str) -> bool:
        """Check if device is currently in fast polling mode."""
        return device_id in self._fast_poll_devices

    def get_fast_poll_count(self) -> int:
        """Get count of devices in fast polling mode."""
        return len(self._fast_poll_devices)

    # ========== Polling Logic ==========

    async def _monitor_loop(self):
        """Main monitoring loop - checks for devices due for polling."""
        logger.info("State monitoring loop started")

        while self._running:
            try:
                await self._poll_due_devices()
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))

            # Check frequently for fast poll devices, but polling respects intervals
            await asyncio.sleep(5)  # Check every 5 seconds

    def _get_poll_interval(self, device_id: str) -> float:
        """Get polling interval for a device.

        Returns fast interval if device is in verification mode, normal otherwise.
        """
        if device_id in self._fast_poll_devices:
            return self.fast_interval
        return self.interval

    def _is_due_for_poll(self, device_id: str) -> bool:
        """Check if a device is due for polling based on its interval."""
        last = self._last_polled.get(device_id)
        if last is None:
            return True

        interval = self._get_poll_interval(device_id)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= interval

    async def _poll_due_devices(self):
        """Poll devices that are due for polling."""
        try:
            # Get all enabled devices
            async with self.db_manager.session() as session:
                stmt = (
                    select(Device)
                    .where(Device.enabled == True)
                    .where(Device.automation_enabled == True)
                )
                result = await session.execute(stmt)
                devices = list(result.scalars().all())

            if not devices:
                return

            # Filter to devices that are due for polling
            due_devices = [d for d in devices if self._is_due_for_poll(str(d.id))]

            if not due_devices:
                return

            # Separate fast poll devices for logging
            fast_count = sum(1 for d in due_devices if str(d.id) in self._fast_poll_devices)
            normal_count = len(due_devices) - fast_count

            logger.debug("Polling due devices",
                        total=len(due_devices),
                        fast_poll=fast_count,
                        normal=normal_count)

            successful = 0
            failed = 0

            # Process devices in batches to avoid overwhelming the network
            for i in range(0, len(due_devices), self.batch_size):
                batch = due_devices[i:i + self.batch_size]

                # Poll batch in parallel
                tasks = [self._poll_single_device(device) for device in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count successes/failures
                for r in results:
                    if isinstance(r, Exception):
                        failed += 1
                    elif r:
                        successful += 1
                    else:
                        failed += 1

                # Small delay between batches
                if i + self.batch_size < len(due_devices):
                    await asyncio.sleep(self.batch_delay)

            if due_devices:
                logger.info("Device state poll completed",
                           total_devices=len(due_devices),
                           successful=successful,
                           failed=failed)

        except Exception as e:
            logger.error("Error polling devices", error=str(e))

    async def _poll_single_device(self, device: Device) -> bool:
        """Poll a single device, update state, and check for verification targets."""
        device_id = str(device.id)
        manager = self.device_managers.get(device.device_type)

        if not manager:
            logger.warning("No manager for device type",
                          device=device.name,
                          type=device.device_type)
            return False

        try:
            # Mark as polled (even if it fails, to prevent retry storm)
            self._last_polled[device_id] = datetime.now(timezone.utc)

            # Get device state
            result = await manager.get_state(device)

            # Update database if successful
            if result.success:
                await self._update_device_state(device.id, result.state)

                logger.debug("Device state updated",
                            device=device.name,
                            host=device.host,
                            type=device.device_type,
                            state=result.state,
                            fast_poll=device_id in self._fast_poll_devices,
                            duration_ms=result.duration_ms)

                # Check if this device reached its verification target state
                if device_id in self._fast_poll_devices:
                    entry = self._fast_poll_devices[device_id]
                    if result.state in entry.target_states:
                        logger.info("Device reached target state",
                                   device=device.name,
                                   state=result.state,
                                   target_states=entry.target_states)
                        # Notify callback (don't await inline to avoid blocking)
                        asyncio.create_task(
                            self._notify_target_reached(device_id, result.state, entry.callback)
                        )

                return True
            else:
                logger.warning("Failed to get device state",
                              device=device.name,
                              host=device.host,
                              error=result.error)
                return False

        except Exception as e:
            logger.error("Error polling device",
                        device=device.name,
                        host=device.host,
                        error=str(e))
            return False

    async def _notify_target_reached(
        self,
        device_id: str,
        state: int,
        callback: Callable[[str, int], Awaitable[None]],
    ) -> None:
        """Notify callback that device reached target state."""
        try:
            await callback(device_id, state)
        except Exception as e:
            logger.error("Error in target state callback",
                        device_id=device_id[:8],
                        error=str(e))

    async def _update_device_state(self, device_id, new_state: int):
        """Update device state in database."""
        try:
            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == device_id)
                    .values(
                        state=new_state,
                        last_checked_at=datetime.now(timezone.utc)
                    )
                )
                await session.execute(stmt)

        except Exception as e:
            logger.error("Error updating device state",
                        device_id=str(device_id),
                        error=str(e))

    async def trigger_immediate_poll(self):
        """Trigger an immediate poll of all devices (useful for testing)."""
        logger.info("Immediate device poll triggered")
        # Clear all last_polled times to force immediate poll
        self._last_polled.clear()
        await self._poll_due_devices()

    # ========== Status API for Frontend ==========

    def get_device_poll_status(self, device_id: str) -> dict:
        """Get polling status for a single device.

        Returns:
            dict with is_verifying, poll_interval, last_polled_at, seconds_until_next_poll
        """
        is_verifying = device_id in self._fast_poll_devices
        interval = self.fast_interval if is_verifying else self.interval
        last_polled = self._last_polled.get(device_id)

        seconds_until_next = 0
        if last_polled:
            elapsed = (datetime.now(timezone.utc) - last_polled).total_seconds()
            seconds_until_next = max(0, int(interval - elapsed))

        return {
            "is_verifying": is_verifying,
            "poll_interval": interval,
            "last_polled_at": last_polled.isoformat() if last_polled else None,
            "seconds_until_next_poll": seconds_until_next,
        }

    def get_monitoring_status(self) -> dict:
        """Get overall monitoring status.

        Returns:
            dict with enabled, running, intervals, fast_poll_count, etc.
        """
        return {
            "enabled": self.enabled,
            "running": self._running,
            "poll_interval_seconds": self.interval,
            "fast_poll_interval_seconds": self.fast_interval,
            "fast_poll_device_count": len(self._fast_poll_devices),
            "fast_poll_device_ids": list(self._fast_poll_devices.keys()),
            "batch_size": self.batch_size,
        }
