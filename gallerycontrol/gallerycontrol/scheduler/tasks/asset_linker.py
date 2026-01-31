# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Asset linker task - links unlinked PJLink devices to assets via DNS resolution.

This task runs periodically to:
1. Find PJLink devices without asset_id
2. Resolve their DNS to find hostnames
3. Extract asset numbers from hostnames
4. Link devices to assets
"""

from typing import Any, Dict

from sqlalchemy import select

from gallerycontrol.database.models import Device
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)


async def run_asset_linker(
    db_manager,
    asset_service,
    batch_size: int = 20,
) -> Dict[str, Any]:
    """Link unlinked PJLink devices to assets via DNS resolution.

    Args:
        db_manager: Database manager instance
        asset_service: AssetService instance
        batch_size: Maximum devices to process per run

    Returns:
        Dict with processed, linked, failed, skipped, and lamp_hours_recorded counts
    """
    results = {
        "processed": 0,
        "linked": 0,
        "failed": 0,
        "skipped": 0,
        "lamp_hours_recorded": 0,
    }

    async with db_manager.session() as session:
        # Find PJLink devices without asset_id, ordered by updated_at (oldest first)
        stmt = (
            select(Device)
            .where(Device.device_type == "pjlink")
            .where(Device.asset_id.is_(None))
            .order_by(Device.updated_at)
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        devices = result.scalars().all()

        if not devices:
            logger.debug("No unlinked PJLink devices found")
            return results

        logger.info(
            "Processing unlinked PJLink devices",
            count=len(devices),
            batch_size=batch_size,
        )

        for device in devices:
            results["processed"] += 1

            try:
                asset = await asset_service.link_device_to_asset(device, session)

                if asset:
                    results["linked"] += 1
                    logger.info(
                        "Linked device to asset",
                        device=device.name,
                        asset_number=asset.asset_number,
                    )
                    # Record initial lamp hours on asset link (onboard event)
                    # No delay needed - asset_linker already runs at controlled schedule
                    try:
                        await asset_service.record_lamp_hours_background(device.id, "onboard")
                        results["lamp_hours_recorded"] += 1
                    except Exception as lh_err:
                        logger.warning(
                            "Failed to record onboard lamp hours",
                            device=device.name,
                            error=str(lh_err),
                        )
                else:
                    results["skipped"] += 1
                    logger.debug(
                        "Could not link device (no asset number found)",
                        device=device.name,
                        host=device.host,
                    )

            except Exception as e:
                results["failed"] += 1
                logger.warning(
                    "Failed to link device",
                    device=device.name,
                    error=str(e),
                )

        await session.commit()

    return results
