# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""State monitoring service - periodically polls device states."""

import asyncio
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from gallerycontrol.utils.datetime_utils import utc_now
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select, update

from gallerycontrol.database.models import Artwork, Device, Exhibition
from gallerycontrol.database.operation_logger import log_device_operation
from gallerycontrol.database.state_logger import update_device_state_with_log
from gallerycontrol.utils.logging import get_logger

if TYPE_CHECKING:
    from gallerycontrol.services.sse_broadcaster import SSEBroadcaster

logger = get_logger(__name__)


@dataclass
class FastPollEntry:
    """Tracks a device registered for fast polling during verification."""

    device_id: str
    target_states: List[int]
    callback: Callable[[str, int], Awaitable[None]]  # async callback(device_id, state)
    deviation_callback: Callable[[str, int], Awaitable[None]] | None = None  # called when state NOT in target
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
        satellite_router=None,
    ):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self._running = False
        self._task = None
        self._sse = sse_broadcaster
        self._satellite_router = satellite_router

        # Get monitoring config
        monitor_config = config.get("monitoring", {})
        self.enabled = monitor_config.get("enabled", True)
        self._interval = monitor_config.get("poll_interval_seconds", 60)
        self._fast_interval = monitor_config.get("fast_poll_interval_seconds", 30)
        self._batch_size = monitor_config.get("batch_size", 30)  # Parallel batches
        self.batch_delay = monitor_config.get("batch_delay_seconds", 0)  # No delay for parallel
        self._device_timeout = monitor_config.get("device_timeout_seconds", 5)  # Per-device timeout

        # Lock for thread-safe config updates
        self._config_lock = asyncio.Lock()

        # Lock for fast poll device registry (prevents race during register/unregister)
        self._fast_poll_lock = asyncio.Lock()

        # Fast polling for verification
        self._fast_poll_devices: Dict[str, FastPollEntry] = {}

        # Track last poll time per device for adaptive intervals
        self._last_polled: Dict[str, datetime] = {}

        # Track background tasks to prevent silent failures
        self._background_tasks: set[asyncio.Task] = set()

        # Cycle tracking for progress bars
        self._cycle_start_time: datetime | None = None
        self._cycle_device_count: int = 0
        self._last_cycle_duration: float = 60.0  # Default estimate

        # DNS resolution interval (default 1 hour)
        asset_config = config.get("asset_tracking", {})
        self.dns_resolve_interval = asset_config.get("dns_resolve_interval", 3600)

    # Thread-safe config properties
    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, value: int) -> None:
        self._interval = value

    @property
    def fast_interval(self) -> int:
        return self._fast_interval

    @fast_interval.setter
    def fast_interval(self, value: int) -> None:
        self._fast_interval = value

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        self._batch_size = value

    @property
    def device_timeout(self) -> int:
        return self._device_timeout

    @device_timeout.setter
    def device_timeout(self, value: int) -> None:
        self._device_timeout = value

    def _create_background_task(self, coro, name: str = None) -> asyncio.Task:
        """Create a tracked background task with error handling."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)
        return task

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        """Callback when background task completes."""
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Background task failed",
                        task_name=task.get_name(),
                        error=str(exc))

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

        # Cancel all background tasks
        for task in list(self._background_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._background_tasks.clear()

        logger.info("State monitoring stopped")

    async def cleanup_stale_entries(self, valid_device_ids: set[str]) -> int:
        """
        Remove _last_polled entries for devices that no longer exist.

        Should be called periodically (e.g., hourly) to prevent memory leaks.

        Args:
            valid_device_ids: Set of device UUID strings that still exist

        Returns:
            Number of entries removed
        """
        # Copy keys first to avoid modification during iteration
        last_polled_keys = list(self._last_polled.keys())
        stale = [
            device_id for device_id in last_polled_keys
            if device_id not in valid_device_ids
        ]
        for device_id in stale:
            self._last_polled.pop(device_id, None)

        # Use lock for fast poll entries since they're accessed from multiple coroutines
        async with self._fast_poll_lock:
            fast_poll_keys = list(self._fast_poll_devices.keys())
            stale_fast = [
                device_id for device_id in fast_poll_keys
                if device_id not in valid_device_ids
            ]
            for device_id in stale_fast:
                self._fast_poll_devices.pop(device_id, None)

        if stale or stale_fast:
            logger.debug("Cleaned up stale device entries",
                        last_polled_removed=len(stale),
                        fast_poll_removed=len(stale_fast))

        return len(stale) + len(stale_fast)

    # ========== Fast Polling Registration ==========

    async def register_fast_poll(
        self,
        device_id: str,
        target_states: List[int],
        callback: Callable[[str, int], Awaitable[None]],
        deviation_callback: Callable[[str, int], Awaitable[None]] | None = None,
    ) -> None:
        """Register a device for fast polling during verification.

        Args:
            device_id: UUID string of the device
            target_states: List of states that trigger callback (e.g., [0, 2] for OFF/cooling)
            callback: Async function called when target state reached: callback(device_id, state)
            deviation_callback: Async function called when state NOT in target_states (for enforcement)
        """
        async with self._fast_poll_lock:
            self._fast_poll_devices[device_id] = FastPollEntry(
                device_id=device_id,
                target_states=target_states,
                callback=callback,
                deviation_callback=deviation_callback,
            )
            # Clear last poll time so device gets polled on next cycle
            self._last_polled.pop(device_id, None)

        logger.info("Device registered for fast polling",
                   device_id=device_id[:8],
                   target_states=target_states)

        # Broadcast verification start via SSE
        if self._sse:
            self._create_background_task(
                self._sse.send_verification_change(device_id, started=True, poll_interval=self.fast_interval),
                name=f"sse_verification_start_{device_id[:8]}"
            )

    async def unregister_fast_poll(self, device_id: str) -> bool:
        """Remove a device from fast polling.

        Returns True if device was registered, False otherwise.
        """
        async with self._fast_poll_lock:
            entry = self._fast_poll_devices.pop(device_id, None)
            if entry is None:
                return False

        logger.info("Device unregistered from fast polling",
                   device_id=device_id[:8])

        # Broadcast verification end via SSE
        if self._sse:
            self._create_background_task(
                self._sse.send_verification_change(device_id, started=False, poll_interval=self.interval),
                name=f"sse_verification_end_{device_id[:8]}"
            )

        return True

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
        elapsed = (utc_now() - last).total_seconds()
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
                        poll_time = utc_now()
                        device_id = str(device.id)
                        self._last_polled[device_id] = poll_time

                        # Check if device is in enforcement mode
                        is_enforcing = device_id in self._fast_poll_devices

                        # Log the timeout for debug visibility
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

                        if is_enforcing:
                            # During enforcement, skip - device may be temporarily busy
                            logger.warning(f"Timeout during enforcement for {device.name} - skipping")
                        else:
                            # Update device state to error (-1) on timeout (normal polling only)
                            await update_device_state_with_log(
                                self.db_manager, device.id, -1, "polling"
                            )

                        # Broadcast timeout via SSE
                        if self._sse:
                            poll_interval = self.fast_interval if is_enforcing else self.interval
                            next_poll_at = poll_time + timedelta(seconds=poll_interval)
                            self._create_background_task(
                                self._sse.send_poll_complete(
                                    device_id=device_id,
                                    success=False,
                                    state=device.state if is_enforcing else -1,
                                    duration_ms=self.device_timeout * 1000,
                                    next_poll_at=next_poll_at,
                                    poll_interval=poll_interval,
                                ),
                                name=f"sse_poll_timeout_{device_id[:8]}"
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
        poll_time = utc_now()
        self._last_polled[device_id] = poll_time
        poll_interval = self._get_poll_interval(device_id)
        next_poll_at = poll_time + timedelta(seconds=poll_interval)

        # Periodic DNS resolution (runs in background, doesn't block polling)
        self._create_background_task(
            self._update_device_dns(device),
            name=f"dns_update_{device_id[:8]}"
        )

        if not manager:
            logger.warning("No manager for device type",
                          device=device.name,
                          type=device.device_type)
            # Update to error state and send SSE
            await update_device_state_with_log(
                self.db_manager, device.id, -1, "polling"
            )
            if self._sse:
                self._create_background_task(
                    self._sse.send_poll_complete(
                        device_id=device_id,
                        success=False,
                        state=-1,
                        duration_ms=0,
                        next_poll_at=next_poll_at,
                        poll_interval=poll_interval,
                    ),
                    name=f"sse_no_manager_{device_id[:8]}"
                )
            return False

        start_time = time.monotonic()
        try:
            # Get device state — go through SatelliteRouter so satellite-routed
            # devices use the WebSocket relay; falls back to direct manager when
            # device.satellite_id is null.
            if self._satellite_router is not None:
                result = await self._satellite_router.get_state(device)
            else:
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
                # Don't pass device.state as current_state - it may be stale
                # Let the function fetch the actual current state from DB
                await update_device_state_with_log(
                    self.db_manager, device.id, result.state, "polling"
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
                    self._create_background_task(
                        self._sse.send_poll_complete(
                            device_id=device_id,
                            success=True,
                            state=result.state,
                            duration_ms=duration_ms,
                            next_poll_at=next_poll_at,
                            poll_interval=poll_interval,
                        ),
                        name=f"sse_poll_success_{device_id[:8]}"
                    )

                # Check if this device reached its verification target state
                entry = self._fast_poll_devices.get(device_id)
                if entry is not None:
                    if result.state in entry.target_states:
                        logger.info("Device reached target state",
                                   device=device.name,
                                   state=result.state,
                                   target_states=entry.target_states)
                        # Notify callback (don't await inline to avoid blocking)
                        self._create_background_task(
                            self._notify_target_reached(device_id, result.state, entry.callback),
                            name=f"notify_target_{device_id[:8]}"
                        )
                    elif entry.deviation_callback is not None:
                        # State deviated from target - notify for enforcement
                        logger.warning("Device state deviated from target",
                                      device=device.name,
                                      state=result.state,
                                      target_states=entry.target_states)
                        self._create_background_task(
                            self._notify_state_deviated(device_id, result.state, entry.deviation_callback),
                            name=f"notify_deviation_{device_id[:8]}"
                        )

                return True
            else:
                # During enforcement (fast poll), skip failures - device may be temporarily offline
                # During normal polling, mark as error
                is_enforcing = device_id in self._fast_poll_devices

                if is_enforcing:
                    logger.warning("Device offline during enforcement - skipping",
                                  device=device.name,
                                  host=device.host,
                                  error=result.error)
                    # Don't update state to error, don't call deviation callback
                    # Just broadcast the poll failure for UI and wait for next poll
                else:
                    logger.warning("Failed to get device state",
                                  device=device.name,
                                  host=device.host,
                                  error=result.error)
                    # Update database to error state (-1) on poll failure (normal polling only)
                    await update_device_state_with_log(
                        self.db_manager, device.id, -1, "polling"
                    )

                # Broadcast poll failure via SSE (still useful for frontend)
                if self._sse:
                    self._create_background_task(
                        self._sse.send_poll_complete(
                            device_id=device_id,
                            success=False,
                            state=device.state if is_enforcing else -1,
                            duration_ms=duration_ms,
                            next_poll_at=next_poll_at,
                            poll_interval=poll_interval,
                        ),
                        name=f"sse_poll_fail_{device_id[:8]}"
                    )

                return False

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            is_enforcing = device_id in self._fast_poll_devices

            if is_enforcing:
                logger.warning("Error polling device during enforcement - skipping",
                              device=device.name,
                              host=device.host,
                              error=str(e))
                # Don't update state to error during enforcement
            else:
                logger.error("Error polling device",
                            device=device.name,
                            host=device.host,
                            error=str(e))
                # Update to error state on exception (normal polling only)
                await update_device_state_with_log(
                    self.db_manager, device.id, -1, "polling"
                )

            if self._sse:
                self._create_background_task(
                    self._sse.send_poll_complete(
                        device_id=device_id,
                        success=False,
                        state=device.state if is_enforcing else -1,
                        duration_ms=duration_ms,
                        next_poll_at=next_poll_at,
                        poll_interval=poll_interval,
                    ),
                    name=f"sse_poll_error_{device_id[:8]}"
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

    async def _notify_state_deviated(
        self,
        device_id: str,
        state: int,
        callback: Callable[[str, int], Awaitable[None]],
    ) -> None:
        """Notify callback that device state deviated from target."""
        try:
            await callback(device_id, state)
        except Exception as e:
            logger.error("Error in state deviation callback",
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
            elapsed = (utc_now() - last_polled).total_seconds()
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

    # ========== DNS Resolution ==========

    def _should_resolve_dns(self, device: Device) -> bool:
        """Check if device DNS should be re-resolved.

        Returns True if:
        - Never resolved
        - Resolved more than dns_resolve_interval seconds ago
        """
        if not device.resolved_at:
            return True

        # Use naive UTC comparison (DB stores naive datetimes)
        now = utc_now()
        resolved_at = device.resolved_at
        # Strip timezone info if present (shouldn't be, but be safe)
        if resolved_at.tzinfo is not None:
            resolved_at = resolved_at.replace(tzinfo=None)

        elapsed = (now - resolved_at).total_seconds()
        return elapsed >= self.dns_resolve_interval

    async def _resolve_dns(self, host: str) -> Optional[str]:
        """Resolve IP to hostname or hostname to IP.

        Args:
            host: IP address or hostname

        Returns:
            Resolved hostname if input was IP, resolved IP if input was hostname,
            or None if resolution failed
        """
        try:
            loop = asyncio.get_event_loop()

            # Check if input looks like an IP
            try:
                socket.inet_aton(host)
                is_ip = True
            except socket.error:
                is_ip = False

            if is_ip:
                # Reverse DNS lookup
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: socket.gethostbyaddr(host)),
                    timeout=3.0
                )
                return result[0]  # Returns (hostname, aliases, addresses)
            else:
                # Forward DNS lookup
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: socket.gethostbyname(host)),
                    timeout=3.0
                )
                return result

        except (socket.herror, socket.gaierror, socket.timeout, asyncio.TimeoutError) as e:
            logger.debug("DNS resolution failed", host=host, error=str(e))
            return None
        except Exception as e:
            logger.warning("Unexpected DNS error", host=host, error=str(e))
            return None

    async def _update_device_dns(self, device: Device) -> None:
        """Update DNS resolution for a device if needed.

        Called during polling to periodically refresh DNS.
        """
        if not self._should_resolve_dns(device):
            return

        resolved = await self._resolve_dns(device.host)
        if resolved and resolved != device.resolved:
            # Update via database session
            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == device.id)
                    .values(
                        resolved=resolved,
                        resolved_at=utc_now(),
                    )
                )
                await session.execute(stmt)
                await session.commit()

            logger.debug(
                "Updated DNS resolution",
                device=device.name,
                host=device.host,
                resolved=resolved,
            )
        elif resolved is None and device.resolved_at is None:
            # First resolution attempt failed, still mark as attempted
            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == device.id)
                    .values(resolved_at=utc_now())
                )
                await session.execute(stmt)
                await session.commit()
