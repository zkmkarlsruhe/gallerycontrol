# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Lamp hours record task - record lamp hours for a single device.

This task is used for one-shot scheduled lamp hours recording, replacing
the fire-and-forget approach. It provides:
- Persistence (survives restarts)
- Visibility in Admin UI
- Error handling and retry via scheduler
- Deduplication via schedule_once()
"""

from typing import TYPE_CHECKING, Any, Dict
from uuid import UUID

from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.services.asset_service import AssetService

logger = get_logger(__name__)


async def run_lamp_hours_record(
    db_manager,
    asset_service: "AssetService",
    device_id: str,
    event_type: str,
) -> Dict[str, Any]:
    """Record lamp hours for a single device.

    Args:
        db_manager: Database manager instance (required by scheduler interface)
        asset_service: AssetService instance for lamp hours recording
        device_id: Device UUID string
        event_type: Event type (power_off, power_on, onboard, etc.)

    Returns:
        Dict with device_id, event_type, and success status
    """
    device_uuid = UUID(device_id)

    try:
        await asset_service.record_lamp_hours_background(device_uuid, event_type)

        logger.debug(
            "Lamp hours recorded via scheduler",
            device_id=device_id[:8],
            event_type=event_type,
        )

        return {
            "device_id": device_id,
            "event_type": event_type,
            "success": True,
        }

    except Exception as e:
        logger.warning(
            "Lamp hours recording failed",
            device_id=device_id[:8],
            event_type=event_type,
            error=str(e),
        )

        # Re-raise to let scheduler handle retry
        raise
