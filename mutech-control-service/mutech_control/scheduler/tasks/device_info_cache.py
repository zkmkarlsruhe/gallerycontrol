# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Device info cache task - periodically caches device info for all online devices.

This task runs periodically to:
1. Query all online devices (state != -1) that support device info
2. Fetch device info from each device with bounded concurrency
3. Cache core identity info (MAC, model, etc.) in the database

Uses semaphore-based concurrency control to:
- Bound execution time (won't overrun interval)
- Limit concurrent requests per device type
- Handle timeouts gracefully
"""

import asyncio
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import select

from mutech_control.database.models import Device
from mutech_control.services.device_cache import extract_core_info, update_device_cache
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)

# Device types that support get_device_info
SUPPORTED_DEVICE_TYPES = ["pjlink", "netio", "anel"]


async def run_device_info_cache(
    db_manager,
    orchestrator,
    max_concurrent: int = 5,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """Cache device info for all online devices.

    Uses semaphore-based concurrency (not serial sleep) to:
    - Bound execution time (won't overrun interval)
    - Limit concurrent requests
    - Handle timeouts gracefully

    Args:
        db_manager: Database manager instance
        orchestrator: CommandOrchestrator with device_managers
        max_concurrent: Maximum concurrent requests
        timeout_seconds: Timeout per device

    Returns:
        Dict with processed, updated, failed, timed_out counts
    """
    results = {
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "timed_out": 0,
        "skipped": 0,
    }

    async with db_manager.session() as session:
        # Find online devices (state != -1) of supported types
        stmt = (
            select(Device)
            .where(Device.state != -1)
            .where(Device.device_type.in_(SUPPORTED_DEVICE_TYPES))
            .where(Device.enabled == True)
        )
        result = await session.execute(stmt)
        devices = result.scalars().all()

        if not devices:
            logger.debug("No online devices found for cache update")
            return results

        logger.info(
            "Starting device info cache update",
            device_count=len(devices),
            max_concurrent=max_concurrent,
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_device(device: Device) -> str:
            """Process a single device with semaphore protection."""
            async with semaphore:
                manager = orchestrator.device_managers.get(device.device_type)
                if not manager or not hasattr(manager, "get_device_info"):
                    return "skipped"

                try:
                    async with asyncio.timeout(timeout_seconds):
                        info = await manager.get_device_info(device)

                        # Skip if error in response
                        if info.get("error"):
                            return "failed"

                        # Extract core info and update cache
                        core_info = extract_core_info(info, device.device_type)
                        if core_info:
                            # Use a new session for the update to avoid conflicts
                            async with db_manager.session() as update_session:
                                await update_device_cache(
                                    update_session,
                                    device.id,
                                    core_info,
                                    datetime.utcnow(),
                                )
                            return "updated"
                        return "skipped"

                except asyncio.TimeoutError:
                    logger.debug(
                        "Device info fetch timed out",
                        device=device.name,
                        timeout=timeout_seconds,
                    )
                    return "timed_out"
                except Exception as e:
                    logger.debug(
                        "Device info fetch failed",
                        device=device.name,
                        error=str(e),
                    )
                    return "failed"

        # Process all devices concurrently (bounded by semaphore)
        tasks = [process_device(device) for device in devices]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        for task_result in task_results:
            results["processed"] += 1
            if isinstance(task_result, Exception):
                results["failed"] += 1
            elif task_result == "updated":
                results["updated"] += 1
            elif task_result == "timed_out":
                results["timed_out"] += 1
            elif task_result == "skipped":
                results["skipped"] += 1
            else:
                results["failed"] += 1

    logger.info(
        "Device info cache update completed",
        **results,
    )

    return results
