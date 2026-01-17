"""State change logging utilities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from mutech_control.database.models import Artwork, Device, StateChangeLog
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


async def update_device_state_with_log(
    db_manager,
    device_id: UUID,
    new_state: int,
    trigger: str,
    current_state: int | None = None,
) -> bool:
    """Update device state in database and log the change if state differs.

    Args:
        db_manager: Database manager instance
        device_id: UUID of the device
        new_state: New state value (-1=error, 0=off, 1=on, 2=cooling, 3=warming)
        trigger: What triggered the change ('polling', 'command', 'verification')
        current_state: Current state if known (avoids extra DB query)

    Returns:
        True if state changed, False if state was the same
    """
    try:
        async with db_manager.session() as session:
            # Get current state and artwork/exhibition info for denormalized logging
            stmt = (
                select(Device.state, Device.artwork_id, Artwork.exhibition_id)
                .join(Artwork, Device.artwork_id == Artwork.id)
                .where(Device.id == device_id)
            )
            result = await session.execute(stmt)
            row = result.first()
            if row is None:
                logger.warning("Device not found for state update",
                              device_id=str(device_id)[:8])
                return False

            if current_state is None:
                current_state = row.state
            artwork_id = row.artwork_id
            exhibition_id = row.exhibition_id

            # Check if state actually changed
            state_changed = current_state != new_state

            # Update device state
            update_stmt = (
                update(Device)
                .where(Device.id == device_id)
                .values(
                    state=new_state,
                    last_checked_at=datetime.utcnow()
                )
            )
            await session.execute(update_stmt)

            # Log state change only if state differs
            if state_changed:
                state_log = StateChangeLog(
                    device_id=device_id,
                    artwork_id=artwork_id,
                    exhibition_id=exhibition_id,
                    previous_state=current_state,
                    new_state=new_state,
                    trigger=trigger,
                )
                session.add(state_log)

                logger.info("Device state changed",
                           device_id=str(device_id)[:8],
                           previous_state=current_state,
                           new_state=new_state,
                           trigger=trigger)

            return state_changed

    except Exception as e:
        logger.error("Error updating device state with log",
                    device_id=str(device_id)[:8],
                    error=str(e))
        return False


def format_state(state: int) -> str:
    """Format state integer to human-readable string."""
    states = {
        -1: "error",
        0: "off",
        1: "on",
        2: "cooling",
        3: "warming",
    }
    return states.get(state, f"unknown({state})")
