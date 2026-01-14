"""Command orchestrator - coordinates device control operations."""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mutech_control.database.models import Artwork, CommandLog, Device, Exhibition
from mutech_control.orchestrator.command_verifier import CommandVerifier
from mutech_control.utils.logging import get_logger, set_request_id

if TYPE_CHECKING:
    from mutech_control.monitoring.state_monitor import StateMonitor

logger = get_logger(__name__)


class CommandOrchestrator:
    """Orchestrate device control commands with staggering and verification."""

    def __init__(self, db_manager, device_managers: Dict, config: dict):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config
        self.command_verifier = CommandVerifier(db_manager, device_managers, config)

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

    async def execute_control_command(
        self,
        target_type: Literal["exhibition", "artwork", "device"],
        target_id: str,
        command: Literal["on", "off"],
        source: Literal["web", "fast"],
    ) -> dict:
        """
        Main entry point for control commands.

        Args:
            target_type: Type of target (exhibition, artwork, or device)
            target_id: UUID of target
            command: Command to execute (on or off)
            source: Source of command (web UI or fast lane)

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
            # 1. Resolve target to list of devices
            devices = await self._resolve_target(target_type, target_id)

            if not devices:
                logger.warning("No devices found for target",
                              target_type=target_type,
                              target_id=target_id[:8])
                return {"success": True, "devices_targeted": 0, "results": [], "request_id": request_id}

            # 2. Filter devices based on enabled flags
            devices = self._filter_devices(devices, command)

            logger.info("Devices resolved and filtered",
                       total_devices=len(devices),
                       command=command)

            # 3. Cancel any active verifications for these devices (web source only)
            if source == "web":
                for device in devices:
                    device_id = str(device.id)
                    if self.command_verifier.is_verifying(device_id):
                        await self.command_verifier.cancel_verification(device_id)
                        logger.info("Cancelled active verification for new command",
                                   device=device.name,
                                   new_command=command)

            # 4. Execute command based on source and command type
            if source == "web":
                if command == "on":
                    results = await self._execute_on_with_verification(devices)
                else:
                    results = await self._execute_off_with_verification(devices)
            else:  # fast lane
                results = await self._execute_fast(devices, command)

            successful = sum(1 for r in results if r.get("success"))
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

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

    async def _resolve_target(
        self, target_type: str, target_id: str
    ) -> List[Device]:
        """Resolve target to list of devices."""
        try:
            target_uuid = UUID(target_id)

            async with self.db_manager.session() as session:
                if target_type == "exhibition":
                    # Get all devices in exhibition
                    stmt = (
                        select(Device)
                        .join(Artwork)
                        .join(Exhibition)
                        .where(Exhibition.id == target_uuid)
                        .options(selectinload(Device.artwork))
                    )
                    result = await session.execute(stmt)
                    devices = result.scalars().all()

                elif target_type == "artwork":
                    # Get all devices in artwork
                    stmt = (
                        select(Device)
                        .where(Device.artwork_id == target_uuid)
                        .options(selectinload(Device.artwork))
                    )
                    result = await session.execute(stmt)
                    devices = result.scalars().all()

                elif target_type == "device":
                    # Get single device
                    stmt = select(Device).where(Device.id == target_uuid).options(selectinload(Device.artwork))
                    result = await session.execute(stmt)
                    device = result.scalar_one_or_none()
                    devices = [device] if device else []

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

    def _filter_devices(self, devices: List[Device], command: str) -> List[Device]:
        """Filter devices based on enabled flags (including parent inheritance)."""
        filtered = []

        for device in devices:
            # Skip effectively disabled devices (checks device + artwork + exhibition)
            if not self._is_effectively_enabled(device):
                logger.debug(f"Skipping effectively disabled device: {device.name}")
                continue

            # Skip devices excluded from auto on/off (shell reboot commands, etc.)
            if device.exclude_from_auto_onoff and command in ["on", "off"]:
                logger.debug(
                    f"Skipping device excluded from auto on/off: {device.name}"
                )
                continue

            filtered.append(device)

        return filtered

    async def _execute_on_with_verification(self, devices: List[Device]) -> List[dict]:
        """Execute ON commands with stagger, then verify."""
        orchestrator_config = self.config.get("orchestrator", {})
        stagger_delay = orchestrator_config.get("on_stagger_delay_seconds", 1.0)

        results = []

        for device in devices:
            # Limit concurrent ON operations
            async with self._on_semaphore:
                result = await self._execute_single_device(device, "on", "web")
                results.append(result)

                # Stagger delay between devices
                await asyncio.sleep(stagger_delay)

        # Start verification tasks for successful devices (excluding shell)
        if orchestrator_config.get("enable_verification", True):
            devices_to_verify = [
                device
                for device, result in zip(devices, results)
                if result.get("success") and device.device_type != "shell"
            ]

            if devices_to_verify:
                logger.info(f"Starting ON verification for {len(devices_to_verify)} devices")
                asyncio.create_task(
                    self.command_verifier.verify_devices(devices_to_verify, "on")
                )

        return results

    async def _execute_off_with_verification(
        self, devices: List[Device]
    ) -> List[dict]:
        """Execute OFF commands with concurrency limit, then verify."""

        async def execute_with_semaphore(device: Device) -> dict:
            """Execute single OFF command with semaphore protection."""
            async with self._off_semaphore:
                return await self._execute_single_device(device, "off", "web")

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

        # 2. Start verification tasks for successful devices (excluding shell)
        orchestrator_config = self.config.get("orchestrator", {})
        if orchestrator_config.get("enable_verification", True):
            devices_to_verify = [
                device
                for device, result in zip(devices, processed_results)
                if result.get("success") and device.device_type != "shell"
            ]

            if devices_to_verify:
                logger.info(f"Starting OFF verification for {len(devices_to_verify)} devices")
                asyncio.create_task(
                    self.command_verifier.verify_devices(devices_to_verify, "off")
                )

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

        try:
            # Execute command
            result = await manager.set_power(device, command == "on")

            # Update database state if successful
            if result.success:
                await self._update_device_state(device.id, result.state)

            # Log command
            await self._log_command(
                device_id=device.id,
                command=command,
                source=source,
                success=result.success,
                error=result.error,
                duration_ms=result.duration_ms,
            )

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

    async def _update_device_state(self, device_id: UUID, new_state: int) -> None:
        """Update device state in database."""
        try:
            from sqlalchemy import update

            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == device_id)
                    .values(state=new_state, last_checked_at=datetime.now(timezone.utc))
                )
                await session.execute(stmt)

        except Exception as e:
            logger.error(f"Error updating device state: {e}")

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
