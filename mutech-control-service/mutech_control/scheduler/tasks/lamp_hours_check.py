# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Periodic lamp hours check task.

Queries lamp hours for all linked PJLink projectors on a schedule.
This catches lamp hour changes even without power events, useful for:
- Projectors that stay on for extended periods
- Monitoring lamp degradation trends
- Catching missed power-off events
"""

from typing import TYPE_CHECKING, Dict, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mutech_control.database.models import Device, LampHoursLog
from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.database.connection import DatabaseManager
    from mutech_control.services.asset_service import AssetService

logger = get_logger(__name__)


async def run_lamp_hours_check(
    db_manager: "DatabaseManager",
    asset_service: "AssetService",
    chunk_size: int = 10,
    delay_between_chunks: float = 2.0,
) -> Dict[str, Any]:
    """Check lamp hours for all linked PJLink projectors.

    Queries each projector and records a 'scheduled' event if lamp hours
    have changed since the last recording.

    Args:
        db_manager: Database manager instance
        asset_service: AssetService for lamp hours recording
        chunk_size: Number of devices to process per chunk
        delay_between_chunks: Seconds to wait between chunks

    Returns:
        Result dict with processed/recorded/skipped/failed counts
    """
    import asyncio

    results = {
        "processed": 0,
        "recorded": 0,
        "unchanged": 0,
        "failed": [],
        "skipped": [],
    }

    async with db_manager.session() as session:
        # Find all PJLink devices with linked assets
        stmt = (
            select(Device)
            .where(Device.device_type == "pjlink")
            .where(Device.asset_id.isnot(None))
            .where(Device.enabled == True)
            .options(selectinload(Device.asset))
        )
        result = await session.execute(stmt)
        devices = list(result.scalars().all())

        if not devices:
            logger.info("No linked PJLink devices found for lamp hours check")
            return results

        logger.info(
            "Starting scheduled lamp hours check",
            device_count=len(devices),
        )

        # Process in chunks to avoid flooding the network
        for i in range(0, len(devices), chunk_size):
            chunk = devices[i : i + chunk_size]

            for device in chunk:
                try:
                    # Get current lamp hours from projector
                    manager = asset_service.device_managers.get("pjlink")
                    if not manager:
                        results["skipped"].append({
                            "device": device.name,
                            "reason": "PJLink manager not available",
                        })
                        results["processed"] += 1
                        continue

                    info = await manager.get_device_info(device)
                    current_hours = info.get("lamp_hours")

                    if current_hours is None:
                        results["skipped"].append({
                            "device": device.name,
                            "reason": "Could not query lamp hours",
                        })
                        results["processed"] += 1
                        continue

                    # Check if hours changed since last recording
                    last_log = await _get_last_lamp_log(session, device.asset_id)

                    if last_log and last_log.lamp_hours == current_hours:
                        # No change, skip recording
                        results["unchanged"] += 1
                        results["processed"] += 1
                        continue

                    # Record the new lamp hours
                    await asset_service._record_lamp_hours_impl(
                        device.id, "scheduled", session
                    )
                    results["recorded"] += 1

                except Exception as e:
                    results["failed"].append({
                        "device": device.name,
                        "error": str(e),
                    })

                results["processed"] += 1

            # Commit after each chunk
            await session.commit()

            # Throttle between chunks
            if i + chunk_size < len(devices):
                await asyncio.sleep(delay_between_chunks)

    logger.info(
        "Scheduled lamp hours check completed",
        processed=results["processed"],
        recorded=results["recorded"],
        unchanged=results["unchanged"],
        failed=len(results["failed"]),
        skipped=len(results["skipped"]),
    )

    return results


async def _get_last_lamp_log(session, asset_id: UUID) -> LampHoursLog | None:
    """Get the most recent lamp hours log for an asset."""
    stmt = (
        select(LampHoursLog)
        .where(LampHoursLog.asset_id == asset_id)
        .order_by(LampHoursLog.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
