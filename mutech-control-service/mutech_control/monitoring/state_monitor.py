"""State monitoring service - periodically polls device states."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List

from sqlalchemy import select

from mutech_control.database.models import Artwork, Device, Exhibition
from mutech_control.database.operation_logger import cleanup_old_operation_logs, log_device_operation
from mutech_control.database.state_logger import update_device_state_with_log
from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.services.sse_broadcaster import SSEBroadcaster

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

    def __init__(
        self,
        db_manager,
        device_managers: Dict,
        config: dict,
        sse_broadcaster: "SSEBroadcaster | None" = None,
    ):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self._running = False
        self._task = None
        self._sse = sse_broadcaster

        # Get monitoring config
        monitor_config = config.get("monitoring", {})
        self.enabled = monitor_config.get("enabled", True)
        self.interval = monitor_config.get("poll_interval_seconds", 60)
        self.fast_interval = monitor_config.get("fast_poll_interval_seconds", 30)
        self.batch_size = monitor_config.get("batch_size", 30)  # Parallel batches
        self.batch_delay = monitor_config.get("batch_delay_seconds", 0)  # No delay for parallel
        self.device_timeout = monitor_config.get("device_timeout_seconds", 5)  # Per-device timeout

        # Fast polling for verification
        self._fast_poll_devices: Dict[str, FastPollEntry] = {}

        # Track last poll time per device for adaptive intervals
        self._last_polled: Dict[str, datetime] = {}

        # Cycle tracking for progress bars
        self._cycle_start_time: datetime | None = None
        self._cycle_device_count: int = 0
        self._last_cycle_duration: float = 60.0  # Default estimate

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
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
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

        if hasattr(self, "_cleanup_task") and self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
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

        # Broadcast verification start via SSE
        if self._sse:
            asyncio.create_task(
                self._sse.send_verification_change(device_id, started=True, poll_interval=self.fast_interval)
            )

    def unregister_fast_poll(self, device_id: str) -> bool:
        """Remove a device from fast polling.

        Returns True if device was registered, False otherwise.
        """
        if device_id in self._fast_poll_devices:
            del self._fast_poll_devices[device_id]
            logger.info("Device unregistered from fast polling",
                       device_id=device_id[:8])

            # Broadcast verification end via SSE
            if self._sse:
                asyncio.create_task(
                    self._sse.send_verification_change(device_id, started=False, poll_interval=self.interval)
                )

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
            # Get all enabled devices (poll ALL for status, not just automation_enabled)
            # automation_enabled only controls whether on/off commands are sent
            async with self.db_manager.session() as session:
                stmt = (
                    select(Device)
                    .join(Artwork, Device.artwork_id == Artwork.id)
                    .join(Exhibition, Artwork.exhibition_id == Exhibition.id)
                    .where(Device.enabled == True)
                    .where(Artwork.enabled == True)
                    .where(Exhibition.enabled == True)
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
            timed_out = 0

            # Create batches
            batches = [
                due_devices[i:i + self.batch_size]
                for i in range(0, len(due_devices), self.batch_size)
            ]

            # Process ALL batches in parallel (not sequential)
            async def poll_batch(batch):
                """Poll a batch of devices with per-device timeout."""
                batch_results = []
                for device in batch:
                    try:
                        result = await asyncio.wait_for(
                            self._poll_single_device(device),
                            timeout=self.device_timeout
                        )
                        batch_results.append(("success" if result else "failed", device.name))
                    except asyncio.TimeoutError:
                        # Mark as polled to prevent retry storm
                        poll_time = datetime.now(timezone.utc)
                        self._last_polled[str(device.id)] = poll_time

                        # Log the timeout for debug visibility (guarded so state update still runs)
                        try:
                            await log_device_operation(
                                db_manager=self.db_manager,
                                device_id=device.id,
                                operation_type="state_query",
                                source="polling",
                                success=False,
                                state_before=device.state,
                                state_after=None,
                                error_message=f"Timeout after {self.device_timeout}s",
                                duration_ms=self.device_timeout * 1000,
                            )
                        except Exception as log_err:
                            logger.warning(f"Failed to log timeout for {device.name}: {log_err}")

                        # Update device state to error (-1) on timeout - must run even if logging failed
                        await update_device_state_with_log(
                            self.db_manager, device.id, -1, "polling", device.state
                        )
                        # Broadcast timeout via SSE
                        if self._sse:
                            device_id = str(device.id)
                            poll_interval = self.fast_interval if device_id in self._fast_poll_devices else self.interval
                            next_poll_at = poll_time + timedelta(seconds=poll_interval)
                            asyncio.create_task(
                                self._sse.send_poll_complete(
                                    device_id=device_id,
                                    success=False,
                                    state=-1,
                                    duration_ms=self.device_timeout * 1000,
                                    next_poll_at=next_poll_at,
                                    poll_interval=poll_interval,
                                )
                            )
                        batch_results.append(("timeout", device.name))
                    except Exception as e:
                        batch_results.append(("error", device.name))
                return batch_results

            # Run all batches in parallel
            all_batch_results = await asyncio.gather(
                *[poll_batch(batch) for batch in batches],
                return_exceptions=True
            )

            # Count results across all batches
            for batch_result in all_batch_results:
                if isinstance(batch_result, Exception):
                    failed += len(batches[0]) if batches else 0  # Estimate
                else:
                    for status, _ in batch_result:
                        if status == "success":
                            successful += 1
                        elif status == "timeout":
                            timed_out += 1
                        else:
                            failed += 1

            if due_devices:
                logger.info("Device state poll completed",
                           total_devices=len(due_devices),
                           successful=successful,
                           failed=failed,
                           timed_out=timed_out,
                           batches=len(batches))

        except Exception as e:
            logger.error("Error polling devices", error=str(e))

    async def _poll_single_device(self, device: Device) -> bool:
        """Poll a single device, update state, and check for verification targets."""
        device_id = str(device.id)
        manager = self.device_managers.get(device.device_type)

        # Mark as polled at the start (even if it fails, to prevent retry storm)
        poll_time = datetime.now(timezone.utc)
        self._last_polled[device_id] = poll_time
        poll_interval = self._get_poll_interval(device_id)
        next_poll_at = poll_time + timedelta(seconds=poll_interval)

        if not manager:
            logger.warning("No manager for device type",
                          device=device.name,
                          type=device.device_type)
            # Update to error state and send SSE
            await update_device_state_with_log(
                self.db_manager, device.id, -1, "polling", device.state
            )
            if self._sse:
                asyncio.create_task(
                    self._sse.send_poll_complete(
                        device_id=device_id,
                        success=False,
                        state=-1,
                        duration_ms=0,
                        next_poll_at=next_poll_at,
                        poll_interval=poll_interval,
                    )
                )
            return False

        start_time = time.monotonic()
        try:
            # Get device state
            result = await manager.get_state(device)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Log operation for debug
            await log_device_operation(
                db_manager=self.db_manager,
                device_id=device.id,
                operation_type="state_query",
                source="polling",
                success=result.success,
                state_before=device.state,
                state_after=result.state if result.success else None,
                raw_response=result.raw_response,
                error_message=result.error,
                duration_ms=duration_ms,
            )

            # Update database if successful
            if result.success:
                await update_device_state_with_log(
                    self.db_manager, device.id, result.state, "polling", device.state
                )

                logger.debug("Device state updated",
                            device=device.name,
                            host=device.host,
                            type=device.device_type,
                            state=result.state,
                            fast_poll=device_id in self._fast_poll_devices,
                            duration_ms=duration_ms)

                # Broadcast poll complete via SSE
                if self._sse:
                    asyncio.create_task(
                        self._sse.send_poll_complete(
                            device_id=device_id,
                            success=True,
                            state=result.state,
                            duration_ms=duration_ms,
                            next_poll_at=next_poll_at,
                            poll_interval=poll_interval,
                        )
                    )

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

                # Update database to error state (-1) on poll failure
                await update_device_state_with_log(
                    self.db_manager, device.id, -1, "polling", device.state
                )

                # Broadcast poll failure via SSE (still useful for frontend)
                if self._sse:
                    asyncio.create_task(
                        self._sse.send_poll_complete(
                            device_id=device_id,
                            success=False,
                            state=-1,  # Error state
                            duration_ms=duration_ms,
                            next_poll_at=next_poll_at,
                            poll_interval=poll_interval,
                        )
                    )

                return False

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Error polling device",
                        device=device.name,
                        host=device.host,
                        error=str(e))
            # Update to error state and send SSE on exception
            await update_device_state_with_log(
                self.db_manager, device.id, -1, "polling", device.state
            )
            if self._sse:
                asyncio.create_task(
                    self._sse.send_poll_complete(
                        device_id=device_id,
                        success=False,
                        state=-1,
                        duration_ms=duration_ms,
                        next_poll_at=next_poll_at,
                        poll_interval=poll_interval,
                    )
                )
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

    # ========== Cleanup Loop ==========

    async def _cleanup_loop(self):
        """Background cleanup of old operation logs (24h retention)."""
        logger.info("Operation log cleanup loop started")

        while self._running:
            try:
                # Run cleanup every hour
                await asyncio.sleep(3600)

                if not self._running:
                    break

                deleted = await cleanup_old_operation_logs(self.db_manager, retention_hours=24)
                if deleted > 0:
                    logger.info("Cleaned up old operation logs", deleted_count=deleted)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))
