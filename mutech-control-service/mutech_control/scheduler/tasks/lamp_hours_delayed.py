"""Delayed lamp hours recording - stagger lamp hours queries after device power-on.

When multiple devices turn on at once (e.g., exhibition power on), this module
delays lamp hours recording to avoid network flooding. Each device's lamp hours
query is scheduled after a configurable delay, naturally staggering the requests.

Features:
- Cancels existing pending tasks for the same device (prevents duplicates)
- Clean cancellation tracking to avoid memory leaks
- Fire-and-forget async scheduling
"""

import asyncio
from typing import TYPE_CHECKING, Dict
from uuid import UUID

from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.services.asset_service import AssetService

logger = get_logger(__name__)

# Pending lamp hours tasks: device_id (str) -> asyncio.Task
_pending_tasks: Dict[str, asyncio.Task] = {}


async def _delayed_record(
    asset_service: "AssetService",
    device_id: UUID,
    event_type: str,
    delay_seconds: float,
) -> None:
    """Execute lamp hours recording after delay.

    Args:
        asset_service: AssetService instance
        device_id: Device UUID to record lamp hours for
        event_type: Event type (power_on, onboard, etc.)
        delay_seconds: Delay before recording
    """
    device_key = str(device_id)

    try:
        await asyncio.sleep(delay_seconds)
        await asset_service.record_lamp_hours_background(device_id, event_type)
        logger.debug(
            "Delayed lamp hours recording completed",
            device_id=device_key[:8],
            event_type=event_type,
            delay=delay_seconds,
        )
    except asyncio.CancelledError:
        logger.debug(
            "Delayed lamp hours recording cancelled",
            device_id=device_key[:8],
            event_type=event_type,
        )
    except Exception as e:
        logger.warning(
            "Delayed lamp hours recording failed",
            device_id=device_key[:8],
            event_type=event_type,
            error=str(e),
        )
    finally:
        # Clean up tracking dict
        _pending_tasks.pop(device_key, None)


def schedule_lamp_hours_recording(
    asset_service: "AssetService",
    device_id: UUID,
    event_type: str,
    delay_seconds: float = 30.0,
) -> bool:
    """Schedule delayed lamp hours recording for a device.

    If a task is already pending for this device, it's cancelled and rescheduled.
    This prevents duplicate recordings when multiple triggers happen quickly.

    Args:
        asset_service: AssetService instance
        device_id: Device UUID to record lamp hours for
        event_type: Event type (power_on, onboard, etc.)
        delay_seconds: Delay before recording (default 30s)

    Returns:
        True if scheduled successfully
    """
    device_key = str(device_id)

    # Cancel existing pending task if any
    existing_task = _pending_tasks.get(device_key)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        logger.debug(
            "Cancelled existing pending lamp hours task",
            device_id=device_key[:8],
        )

    # Schedule new delayed task
    task = asyncio.create_task(
        _delayed_record(asset_service, device_id, event_type, delay_seconds)
    )
    _pending_tasks[device_key] = task

    logger.debug(
        "Scheduled delayed lamp hours recording",
        device_id=device_key[:8],
        event_type=event_type,
        delay=delay_seconds,
    )

    return True


def get_pending_count() -> int:
    """Get count of pending lamp hours tasks (for monitoring)."""
    return sum(1 for task in _pending_tasks.values() if not task.done())
