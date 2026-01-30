"""Command orchestrator - coordinates device control operations."""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Literal, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from mutech_control.database.models import Artwork, CommandLog, Device, Exhibition
from mutech_control.database.operation_logger import log_device_operation
from mutech_control.database.state_logger import update_device_state_with_log
from mutech_control.orchestrator.command_verifier import CommandVerifier
from mutech_control.utils.logging import get_logger, set_request_id

if TYPE_CHECKING:
    from mutech_control.devices.satellite_router import SatelliteRouter
    from mutech_control.monitoring.state_monitor import StateMonitor
    from mutech_control.scheduler.cron_scheduler import CronScheduler
    from mutech_control.services.asset_service import AssetService
    from mutech_control.services.protection_service import ProtectionService

logger = get_logger(__name__)


class CommandOrchestrator:
    """Orchestrate device control commands with staggering and verification."""

    def __init__(self, db_manager, device_managers: Dict, config: dict):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self.command_verifier = CommandVerifier(db_manager, device_managers, config)
        self._asset_service: Optional["AssetService"] = None
        self._scheduler: Optional["CronScheduler"] = None
        self._protection_service: Optional["ProtectionService"] = None
        self._satellite_router: Optional["SatelliteRouter"] = None
        self._sse_broadcaster = None

        orchestrator_config = config.get("orchestrator", {})

        # Concurrency limits to prevent network flooding
        max_on = orchestrator_config.get("max_concurrent_on_commands", 10)
        max_off = orchestrator_config.get("max_concurrent_off_commands", 20)
        max_fast = orchestrator_config.get("max_concurrent_fast_commands", 20)

        self._on_semaphore = asyncio.Semaphore(max_on)
        self._off_semaphore = asyncio.Semaphore(max_off)
        self._fast_semaphore = asyncio.Semaphore(max_fast)

    def set_state_monitor(self, state_monitor: "StateMonitor") -> None:
        """Set state monitor reference for verification polling.

        This must be called after both orchestrator and state_monitor are created,
        as they have a circular dependency (verifier needs monitor, monitor needs managers).
        """
        self.command_verifier.set_state_monitor(state_monitor)

    def set_asset_service(self, asset_service: "AssetService") -> None:
        """Set asset service reference for lamp hours recording."""
        self._asset_service = asset_service

    def set_scheduler(self, scheduler: "CronScheduler") -> None:
        """Set scheduler reference for one-shot task scheduling."""
        self._scheduler = scheduler

    def set_protection_service(self, protection_service: "ProtectionService") -> None:
        """Set protection service reference for artwork overuse prevention."""
        self._protection_service = protection_service

    def set_sse_broadcaster(self, sse_broadcaster) -> None:
        """Set SSE broadcaster reference for real-time updates."""
        self._sse_broadcaster = sse_broadcaster

    def set_satellite_router(self, satellite_router: "SatelliteRouter") -> None:
        """Set satellite router reference for routing commands through satellites."""
        self._satellite_router = satellite_router

    def _on_verification_done(self, task: asyncio.Task) -> None:
        """Callback for verification task completion - logs any errors."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Verification task failed unexpectedly", error=str(exc))

    async def execute_control_command(
        self,
        target_type: Literal["exhibition", "artwork", "device"],
        target_id: str,
        command: Literal["on", "off"],
        source: Literal["web", "fast", "scheduler", "sensor", "protection"],
    ) -> dict:
        """
        Main entry point for control commands.

        Args:
            target_type: Type of target (exhibition, artwork, or device)
            target_id: UUID of target
            command: Command to execute (on or off)
            source: Source of command:
                - web: Web UI manual control
                - fast: Fast lane API (legacy trigger)
                - scheduler: Scheduled jobs
                - sensor: External sensor triggers (lidar, motion, etc.)
                - protection: Protection service forced stop

        Returns:
            dict with success status and results
        """
        # Generate request ID for tracing
        request_id = set_request_id()
        start_time = asyncio.get_event_loop().time()

        logger.info("Command execution started",
                   command=command.upper(),
                   target_type=target_type,
                   target_id=target_id[:8],
                   source=source)

        try:
            # 0. Check protection rules for ON commands
            # For exhibitions, check ALL protected artworks - block if ANY are blocked
            if command == "on" and self._protection_service:
                artwork_ids = await self._get_artwork_ids_for_target(target_type, target_id)
                for artwork_id in artwork_ids:
                    if self._protection_service.is_protected(artwork_id):
                        allowed, reason = await self._protection_service.check_can_start(artwork_id)
                        if not allowed:
                            logger.warning(
                                "Command blocked by protection",
                                command=command.upper(),
                                target_type=target_type,
                                target_id=target_id[:8],
                                artwork_id=str(artwork_id)[:8],
                                reason=reason,
                            )
                            return {
                                "success": False,
                                "blocked": True,
                                "reason": reason,
                                "request_id": request_id,
                            }

            # 1. Resolve target to list of devices
            devices = await self._resolve_target(target_type, target_id)

            if not devices:
                logger.warning("No devices found for target",
                              target_type=target_type,
                              target_id=target_id[:8])
                return {"success": True, "devices_targeted": 0, "results": [], "request_id": request_id}

            # 2. Filter devices based on enabled flags
            devices = self._filter_devices(devices, command, source)

            logger.info("Devices resolved and filtered",
                       total_devices=len(devices),
                       command=command)

            # 3. Cancel any active verifications for these devices
            # Both web and fast sources should cancel verifications since the
            # expected device state is changing
            for device in devices:
                device_id = str(device.id)
                if self.command_verifier.is_verifying(device_id):
                    await self.command_verifier.cancel_verification(device_id)
                    logger.info("Cancelled active verification for new command",
                               device=device.name,
                               new_command=command,
                               source=source)

            # 4. Execute command based on source and command type
            if source in ("web", "scheduler"):
                if command == "on":
                    results = await self._execute_on_with_verification(devices, source)
                else:
                    results = await self._execute_off_with_verification(devices, source)
            elif source in ("sensor", "protection"):
                # Sensor and protection use fast execution (no stagger, no verification)
                results = await self._execute_fast(devices, command)
            else:  # fast lane
                results = await self._execute_fast(devices, command)

            successful = sum(1 for r in results if r.get("success"))
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Update accepting_triggers gate for web/scheduler commands (not device-level)
            # Device-level = maintenance mode, doesn't change gate
            # Sensor/protection sources do NOT update accepting_triggers (only web/scheduler do)
            if successful > 0 and source in ("web", "scheduler") and target_type != "device":
                await self._update_accepting_triggers(
                    target_type, target_id, accepting=(command == "on")
                )

            # Notify protection service of state changes
            # Pass source so protection service knows if this is a forced stop (cooldown)
            if successful > 0 and self._protection_service:
                artwork_ids = await self._get_artwork_ids_for_target(target_type, target_id)
                for artwork_id in artwork_ids:
                    if self._protection_service.is_protected(artwork_id):
                        if command == "on":
                            await self._protection_service.notify_started(artwork_id, source=source)
                        elif command == "off":
                            await self._protection_service.notify_stopped(artwork_id, source=source)

            logger.info("Command execution completed",
                       command=command.upper(),
                       devices_targeted=len(devices),
                       devices_successful=successful,
                       duration_ms=duration_ms,
                       success_rate=f"{successful}/{len(devices)}")

            return {
                "success": True,
                "devices_targeted": len(devices),
                "devices_successful": successful,
                "results": results,
                "source": source,
                "request_id": request_id,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error("Command execution failed",
                        command=command.upper(),
                        error=str(e),
                        duration_ms=duration_ms)
            return {"success": False, "error": str(e), "request_id": request_id}

    async def _get_artwork_id_for_target(
        self, target_type: str, target_id: str
    ) -> Optional[UUID]:
        """Get artwork ID for a given target.

        Returns artwork ID if target is an artwork or single device in an artwork.
        Returns None for exhibitions (protection is per-artwork).
        """
        if target_type == "artwork":
            return UUID(target_id)
        elif target_type == "device":
            # Get device's artwork_id
            async with self.db_manager.session() as session:
                stmt = select(Device.artwork_id).where(Device.id == UUID(target_id))
                result = await session.execute(stmt)
                row = result.first()
                return row[0] if row else None
        # Exhibition-level commands don't trigger protection (too broad)
        return None

    async def _get_artwork_ids_for_target(
        self, target_type: str, target_id: str
    ) -> List[UUID]:
        """Get all artwork IDs for a given target.

        Returns:
            - [UUID(target_id)] for artwork targets
            - [device.artwork_id] for device targets (if device has an artwork)
            - All artwork IDs in the exhibition for exhibition targets
        """
        if target_type == "artwork":
            return [UUID(target_id)]
        elif target_type == "device":
            # Get device's artwork_id
            async with self.db_manager.session() as session:
                stmt = select(Device.artwork_id).where(Device.id == UUID(target_id))
                result = await session.execute(stmt)
                row = result.first()
                if row and row[0]:
                    return [row[0]]
                return []
        elif target_type == "exhibition":
            # Get all artwork IDs in the exhibition
            async with self.db_manager.session() as session:
                stmt = select(Artwork.id).where(Artwork.exhibition_id == UUID(target_id))
                result = await session.execute(stmt)
                return [row[0] for row in result.fetchall()]
        return []

    async def _update_accepting_triggers(
        self, target_type: str, target_id: str, accepting: bool
    ) -> None:
        """Update accepting_triggers flag for artworks.

        Sets the flag based on target type:
        - artwork: Update single artwork
        - exhibition: Update all artworks in exhibition
        - all: Update all artworks

        Device-level targets do NOT update this flag (maintenance mode).
        """
        if target_type == "device":
            # Maintenance mode - don't change gate
            return

        try:
            async with self.db_manager.session() as session:
                if target_type == "artwork":
                    stmt = (
                        update(Artwork)
                        .where(Artwork.id == UUID(target_id))
                        .values(accepting_triggers=accepting)
                    )
                elif target_type == "exhibition":
                    stmt = (
                        update(Artwork)
                        .where(Artwork.exhibition_id == UUID(target_id))
                        .values(accepting_triggers=accepting)
                    )
                elif target_type == "all":
                    stmt = update(Artwork).values(accepting_triggers=accepting)
                else:
                    return

                result = await session.execute(stmt)
                affected_count = result.rowcount
                logger.info(
                    "Updated accepting_triggers",
                    target_type=target_type,
                    target_id=target_id[:8] if target_id else "all",
                    accepting=accepting,
                    rows_affected=affected_count,
                )

                # Broadcast SSE events for affected artworks
                if self._sse_broadcaster and affected_count > 0:
                    if target_type == "artwork":
                        await self._sse_broadcaster.send_accepting_triggers_change(
                            target_id, accepting
                        )
                    elif target_type == "exhibition":
                        # Get all artwork IDs in exhibition
                        artwork_stmt = select(Artwork.id).where(
                            Artwork.exhibition_id == UUID(target_id)
                        )
                        artwork_result = await session.execute(artwork_stmt)
                        for row in artwork_result:
                            await self._sse_broadcaster.send_accepting_triggers_change(
                                str(row[0]), accepting
                            )
                    elif target_type == "all":
                        # Get all artwork IDs
                        artwork_stmt = select(Artwork.id)
                        artwork_result = await session.execute(artwork_stmt)
                        for row in artwork_result:
                            await self._sse_broadcaster.send_accepting_triggers_change(
                                str(row[0]), accepting
                            )

        except Exception as e:
            logger.error(
                "Failed to update accepting_triggers",
                target_type=target_type,
                error=str(e),
            )

    async def _resolve_target(
        self, target_type: str, target_id: str
    ) -> List[Device]:
        """Resolve target to list of devices."""
        try:
            # "all" target doesn't need a valid UUID
            target_uuid = None if target_type == "all" else UUID(target_id)

            async with self.db_manager.session() as session:
                if target_type == "exhibition":
                    # Get all devices in exhibition
                    stmt = (
                        select(Device)
                        .join(Artwork)
                        .join(Exhibition)
                        .where(Exhibition.id == target_uuid)
                        .options(selectinload(Device.artwork).selectinload(Artwork.exhibition))
                    )
                    result = await session.execute(stmt)
                    devices = result.scalars().all()

                elif target_type == "artwork":
                    # Get all devices in artwork
                    stmt = (
                        select(Device)
                        .where(Device.artwork_id == target_uuid)
                        .options(selectinload(Device.artwork).selectinload(Artwork.exhibition))
                    )
                    result = await session.execute(stmt)
                    devices = result.scalars().all()

                elif target_type == "device":
                    # Get single device
                    stmt = select(Device).where(Device.id == target_uuid).options(selectinload(Device.artwork).selectinload(Artwork.exhibition))
                    result = await session.execute(stmt)
                    device = result.scalar_one_or_none()
                    devices = [device] if device else []

                elif target_type == "all":
                    # Get all devices (for system-wide scheduling)
                    stmt = select(Device).options(
                        selectinload(Device.artwork).selectinload(Artwork.exhibition)
                    )
                    result = await session.execute(stmt)
                    devices = result.scalars().all()

                else:
                    logger.error(f"Unknown target type: {target_type}")
                    return []

                return list(devices)

        except Exception as e:
            logger.error(f"Error resolving target {target_type} {target_id}: {e}")
            return []

    def _is_effectively_enabled(self, device: Device) -> bool:
        """Check if device is effectively enabled (considers parent chain).

        A device is effectively enabled only if:
        - The device itself is enabled
        - Its parent artwork is enabled
        - Its parent exhibition is enabled

        This allows disabling an entire exhibition or artwork with one toggle.
        """
        if not device.enabled:
            return False
        if device.artwork and not device.artwork.enabled:
            return False
        if device.artwork and device.artwork.exhibition:
            if not device.artwork.exhibition.enabled:
                return False
        return True

    def _filter_devices(
        self, devices: List[Device], command: str, source: str = "web"
    ) -> List[Device]:
        """Filter devices based on enabled flags (including parent inheritance).

        Args:
            devices: List of devices to filter
            command: Command being executed (on/off)
            source: Command source (web/fast/scheduler). Scheduler bypasses
                   automation_enabled check since schedules should work
                   independently - use device.enabled to disable scheduling.
        """
        filtered = []

        for device in devices:
            # Skip effectively disabled devices (checks device + artwork + exhibition)
            if not self._is_effectively_enabled(device):
                logger.debug(f"Skipping effectively disabled device: {device.name}")
                continue

            # Skip devices with automation disabled (requires manual control)
            # Scheduler bypasses this - schedules work on enabled devices regardless
            # of automation_enabled flag. Use device.enabled to disable scheduling.
            if source != "scheduler" and not device.automation_enabled and command in ["on", "off"]:
                logger.debug(
                    f"Skipping device with automation disabled: {device.name}"
                )
                continue

            filtered.append(device)

        return filtered

    async def _execute_on_with_verification(
        self, devices: List[Device], source: str = "web"
    ) -> List[dict]:
        """Execute ON commands with stagger, then verify."""
        orchestrator_config = self.config.get("orchestrator", {})
        stagger_delay = orchestrator_config.get("on_stagger_delay_seconds", 1.0)

        results = []

        for device in devices:
            # Limit concurrent ON operations
            async with self._on_semaphore:
                result = await self._execute_single_device(device, "on", source)
                results.append(result)

                # Stagger delay between devices
                await asyncio.sleep(stagger_delay)

        # Start verification tasks for successful devices AND cooldown failures (excluding shell)
        # Cooldown failures should still get enforcement - the enforcement will retry
        if orchestrator_config.get("enable_verification", True):
            devices_to_verify = [
                device
                for device, result in zip(devices, results)
                if device.device_type != "shell" and (
                    result.get("success") or
                    "cooldown" in str(result.get("error", "")).lower()
                )
            ]

            if devices_to_verify:
                logger.info(f"Starting ON verification for {len(devices_to_verify)} devices")
                task = asyncio.create_task(
                    self.command_verifier.verify_devices(devices_to_verify, "on")
                )
                # Track task for proper error handling
                task.add_done_callback(self._on_verification_done)

        return results

    async def _execute_off_with_verification(
        self, devices: List[Device], source: str = "web"
    ) -> List[dict]:
        """Execute OFF commands with concurrency limit, then verify."""

        async def execute_with_semaphore(device: Device) -> dict:
            """Execute single OFF command with semaphore protection."""
            async with self._off_semaphore:
                return await self._execute_single_device(device, "off", source)

        # Execute with concurrency limit
        tasks = [execute_with_semaphore(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "device_id": str(devices[i].id),
                        "success": False,
                        "error": str(result),
                    }
                )
            else:
                processed_results.append(result)

        # 2. Start verification tasks for successful devices AND cooldown failures (excluding shell)
        # Cooldown failures should still get enforcement - the enforcement will retry
        orchestrator_config = self.config.get("orchestrator", {})
        if orchestrator_config.get("enable_verification", True):
            devices_to_verify = [
                device
                for device, result in zip(devices, processed_results)
                if device.device_type != "shell" and (
                    result.get("success") or
                    "cooldown" in str(result.get("error", "")).lower()
                )
            ]

            if devices_to_verify:
                logger.info(f"Starting OFF verification for {len(devices_to_verify)} devices")
                task = asyncio.create_task(
                    self.command_verifier.verify_devices(devices_to_verify, "off")
                )
                # Track task for proper error handling
                task.add_done_callback(self._on_verification_done)

        return processed_results

    async def _execute_fast(
        self, devices: List[Device], command: str
    ) -> List[dict]:
        """Execute commands in fast lane with concurrency limit, no verification."""

        async def execute_with_semaphore(device: Device) -> dict:
            """Execute single FAST command with semaphore protection."""
            async with self._fast_semaphore:
                return await self._execute_single_device(device, command, "fast")

        # Execute with concurrency limit
        tasks = [execute_with_semaphore(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "device_id": str(devices[i].id),
                        "success": False,
                        "error": str(result),
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_single_device(
        self, device: Device, command: str, source: str
    ) -> dict:
        """Execute command on single device."""
        try:
            state_before = device.state

            # Check if device should be routed through satellite
            if self._satellite_router:
                satellite_id = self._satellite_router.should_route_via_satellite(device)
                if satellite_id:
                    # Route through satellite
                    result = await self._satellite_router.route_command(
                        device, command, satellite_id
                    )
                else:
                    # Direct execution
                    manager = self.device_managers.get(device.device_type)
                    if not manager:
                        error = f"No manager available for device type {device.device_type}"
                        logger.error(error)
                        return {
                            "device_id": str(device.id),
                            "device_name": device.name,
                            "device_type": device.device_type,
                            "success": False,
                            "error": error,
                        }
                    result = await manager.set_power(device, command == "on")
            else:
                # No satellite router configured - direct execution
                manager = self.device_managers.get(device.device_type)
                if not manager:
                    error = f"No manager available for device type {device.device_type}"
                    logger.error(error)
                    return {
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "device_type": device.device_type,
                        "success": False,
                        "error": error,
                    }
                result = await manager.set_power(device, command == "on")

            # Update database state if successful
            if result.success:
                await update_device_state_with_log(
                    self.db_manager, device.id, result.state, "command", device.state
                )

            # Log command to CommandLog (existing)
            await self._log_command(
                device_id=device.id,
                command=command,
                source=source,
                success=result.success,
                error=result.error,
                duration_ms=result.duration_ms,
            )

            # Log detailed operation with raw response (new debug log)
            await log_device_operation(
                db_manager=self.db_manager,
                device_id=device.id,
                operation_type=f"power_{command}",
                source=source,
                success=result.success,
                state_before=state_before,
                state_after=result.state if result.success else None,
                raw_response=result.raw_response,
                error_message=result.error,
                duration_ms=result.duration_ms,
            )

            # Record lamp hours for PJLink devices with asset link on power_off
            # Recording on power-off captures total lamp usage for that session
            # 7 min delay ensures projector cooldown is complete before querying
            # Uses persistent scheduler instead of fire-and-forget for reliability
            if (
                result.success
                and command == "off"
                and device.device_type == "pjlink"
                and device.asset_id
                and self._scheduler
            ):
                await self._schedule_lamp_hours_recording(device.id, "power_off")

            return {
                "device_id": str(device.id),
                "device_name": device.name,
                "device_type": device.device_type,
                "success": result.success,
                "state": result.state,
                "error": result.error,
                "duration_ms": result.duration_ms,
            }

        except Exception as e:
            logger.error(f"Error executing command on {device.name}: {e}")
            return {
                "device_id": str(device.id),
                "device_name": device.name,
                "device_type": device.device_type,
                "success": False,
                "error": str(e),
            }

    async def _log_command(
        self,
        device_id: UUID,
        command: str,
        source: str,
        success: bool,
        error: str | None,
        duration_ms: int | None,
    ) -> None:
        """Log command execution to database."""
        try:
            async with self.db_manager.session() as session:
                log = CommandLog(
                    device_id=device_id,
                    command=command,
                    source=source,
                    success=success,
                    error_message=error,
                    duration_ms=duration_ms,
                )
                session.add(log)

        except Exception as e:
            logger.error(f"Error logging command: {e}")

    async def _schedule_lamp_hours_recording(
        self, device_id: UUID, event_type: str
    ) -> None:
        """Schedule lamp hours recording via persistent one-shot task.

        Uses the scheduler's schedule_once() for persistence and deduplication.
        This replaces the fire-and-forget approach with a reliable scheduled task.

        Args:
            device_id: Device UUID
            event_type: Event type (power_off, power_on, etc.)
        """
        if not self._scheduler:
            logger.warning(
                "Cannot schedule lamp hours - scheduler not set",
                device_id=str(device_id)[:8],
            )
            return

        # Schedule 7 minutes from now (wait for projector cooldown)
        run_at = datetime.utcnow() + timedelta(minutes=7)
        dedupe_name = f"lamp_hours:{device_id}"

        try:
            job_id = await self._scheduler.schedule_once(
                name=dedupe_name,
                job_type="system",
                task_name="lamp_hours_record",
                task_config={
                    "device_id": str(device_id),
                    "event_type": event_type,
                },
                run_at=run_at,
                dedupe_key=dedupe_name,
            )

            if job_id:
                logger.debug(
                    "Scheduled lamp hours recording",
                    device_id=str(device_id)[:8],
                    event_type=event_type,
                    run_at=run_at.isoformat(),
                )
            else:
                logger.debug(
                    "Lamp hours recording already scheduled (dedupe)",
                    device_id=str(device_id)[:8],
                )

        except Exception as e:
            logger.error(
                "Failed to schedule lamp hours recording",
                device_id=str(device_id)[:8],
                error=str(e),
            )
