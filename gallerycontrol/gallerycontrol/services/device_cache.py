# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Device info cache helpers.

Provides race-safe cache update functions for device info caching.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from gallerycontrol.database.models import Device
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)


# Core fields to cache by device type (static device identity info only)
CORE_FIELDS = {
    "pjlink": ["manufacturer", "product", "name", "class"],
    "netio": ["model", "mac", "firmware", "serial", "device_name"],
    "anel": ["name", "mac", "ip"],
}


def extract_core_info(info: dict, device_type: str) -> dict:
    """Extract only core device identity fields for caching.

    Args:
        info: Full device info dict from manager.get_device_info()
        device_type: Device type (pjlink, netio, anel)

    Returns:
        Dict with only the core identity fields
    """
    if not info:
        return {}

    fields = CORE_FIELDS.get(device_type, [])
    return {k: v for k, v in info.items() if k in fields and v is not None}


async def update_device_cache(
    session: AsyncSession,
    device_id: UUID,
    info: dict,
    timestamp: Optional[datetime] = None,
) -> bool:
    """Update device cached_info after successful get_device_info().

    Race-safe: Only updates if incoming timestamp is newer than existing.
    Returns True if update was applied, False if skipped (stale data).

    Called from:
    - Scheduled task (device_info_cache)
    - Debug API endpoint (live fallback)

    Args:
        session: Database session
        device_id: Device UUID
        info: Device info dict (should be extracted core info)
        timestamp: Timestamp for the cache (defaults to now)

    Returns:
        True if update was applied, False if skipped
    """
    ts = timestamp or datetime.utcnow()

    result = await session.execute(
        update(Device)
        .where(Device.id == device_id)
        .where(
            or_(
                Device.cached_info_at.is_(None),
                Device.cached_info_at < ts,
            )
        )
        .values(
            cached_info=info,
            cached_info_at=ts,
        )
    )

    updated = result.rowcount > 0
    if updated:
        logger.debug("Updated device cache", device_id=str(device_id)[:8])
    else:
        logger.debug("Skipped stale cache update", device_id=str(device_id)[:8])

    return updated


async def clear_device_cache(session: AsyncSession, device_id: UUID) -> bool:
    """Clear cached device info for a device.

    Called when device config changes to force fresh fetch.

    Args:
        session: Database session
        device_id: Device UUID

    Returns:
        True if cache was cleared
    """
    result = await session.execute(
        update(Device)
        .where(Device.id == device_id)
        .values(
            cached_info=None,
            cached_info_at=None,
        )
    )

    return result.rowcount > 0
