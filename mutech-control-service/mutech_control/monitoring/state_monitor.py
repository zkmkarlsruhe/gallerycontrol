"""State monitoring service - periodically polls device states."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import select, update

from mutech_control.database.models import Device
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


class StateMonitor:
    """Background service that monitors device states."""

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
        self.batch_size = monitor_config.get("batch_size", 10)
        self.batch_delay = monitor_config.get("batch_delay_seconds", 1.0)

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

    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("State monitoring loop started")

        while self._running:
            try:
                await self._poll_devices()
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))

            # Wait for next interval
            await asyncio.sleep(self.interval)

    async def _poll_devices(self):
        """Poll all enabled devices for their current state."""
        try:
            # Get all enabled devices with automation enabled
            async with self.db_manager.session() as session:
                stmt = (
                    select(Device)
                    .where(Device.enabled == True)
                    .where(Device.automation_enabled == True)
                )
                result = await session.execute(stmt)
                devices = list(result.scalars().all())

            if not devices:
                logger.debug("No devices to monitor")
                return

            logger.info("Starting device state poll",
                       total_devices=len(devices))

            successful = 0
            failed = 0

            # Process devices in batches to avoid overwhelming the system
            for i in range(0, len(devices), self.batch_size):
                batch = devices[i:i + self.batch_size]

                # Poll batch in parallel
                tasks = [self._poll_single_device(device) for device in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count successes/failures
                for result in results:
                    if isinstance(result, Exception):
                        failed += 1
                    elif result:
                        successful += 1
                    else:
                        failed += 1

                # Small delay between batches
                if i + self.batch_size < len(devices):
                    await asyncio.sleep(self.batch_delay)

            logger.info("Device state poll completed",
                       total_devices=len(devices),
                       successful=successful,
                       failed=failed)

        except Exception as e:
            logger.error("Error polling devices", error=str(e))

    async def _poll_single_device(self, device: Device) -> bool:
        """Poll a single device and update its state."""
        manager = self.device_managers.get(device.device_type)

        if not manager:
            logger.warning("No manager for device type",
                          device=device.name,
                          type=device.device_type)
            return False

        try:
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
                            duration_ms=result.duration_ms)
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

    async def _update_device_state(self, device_id, new_state: int):
        """Update device state in database."""
        try:
            async with self.db_manager.session() as session:
                stmt = (
                    update(Device)
                    .where(Device.id == device_id)
                    .values(
                        state=new_state,
                        last_checked_at=datetime.utcnow()
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
        await self._poll_devices()
