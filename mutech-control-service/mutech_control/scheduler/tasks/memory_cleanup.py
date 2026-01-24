"""Memory cleanup task - removes stale entries from in-memory caches.

This task runs periodically to clean up:
- StateMonitor._last_polled entries for deleted devices
- CooldownManager entries for deleted devices

Prevents memory leaks from accumulating entries for devices that no longer exist.
"""

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select

from mutech_control.database.models import Device
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


async def run_memory_cleanup(
    db_manager,
    state_monitor,
    device_managers: dict,
) -> Dict[str, Any]:
    """Clean up stale entries from in-memory caches.

    Args:
        db_manager: Database manager instance
        state_monitor: StateMonitor instance
        device_managers: Dict of device type -> manager

    Returns:
        Dict with cleanup counts
    """
    results = {
        "state_monitor_cleaned": 0,
        "cooldown_expired_cleaned": 0,
        "cooldown_stale_cleaned": 0,
    }

    try:
        # Get all valid device IDs from database
        async with db_manager.session() as session:
            stmt = select(Device.id)
            result = await session.execute(stmt)
            valid_device_ids = {str(row[0]) for row in result.fetchall()}
            valid_device_uuids = {UUID(device_id) for device_id in valid_device_ids}

        # Clean up StateMonitor
        if state_monitor:
            cleaned = await state_monitor.cleanup_stale_entries(valid_device_ids)
            results["state_monitor_cleaned"] = cleaned

        # Clean up CooldownManagers in each device manager
        total_expired = 0
        total_stale = 0

        for device_type, manager in device_managers.items():
            if hasattr(manager, "cooldown_manager"):
                cm = manager.cooldown_manager

                # Clean expired cooldowns
                expired = cm.cleanup_expired()
                total_expired += expired

                # Clean stale device entries
                stale = cm.cleanup_devices(valid_device_uuids)
                total_stale += stale

        results["cooldown_expired_cleaned"] = total_expired
        results["cooldown_stale_cleaned"] = total_stale

        total = (
            results["state_monitor_cleaned"]
            + results["cooldown_expired_cleaned"]
            + results["cooldown_stale_cleaned"]
        )

        if total > 0:
            logger.info(
                "Memory cleanup completed",
                state_monitor_cleaned=results["state_monitor_cleaned"],
                cooldown_expired=results["cooldown_expired_cleaned"],
                cooldown_stale=results["cooldown_stale_cleaned"],
            )

    except Exception as e:
        logger.error("Error in memory cleanup", error=str(e))
        results["error"] = str(e)

    return results
