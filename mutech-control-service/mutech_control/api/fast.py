"""Fast lane API endpoints for external triggers."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fast", tags=["fast-lane"])


def get_orchestrator():
    """Dependency to get orchestrator instance."""
    from mutech_control.main import app

    return app.state.orchestrator


@router.post("/device/{device_id}/{command}")
async def fast_control_device(
    device_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Fast lane control for external triggers.

    **Behavior:**
    - Fire once, no retry
    - No OFF verification
    - No stagger delay
    - Primarily used for NETIO and shell commands from external systems

    **Note:** Projectors typically don't use fast lane due to warm-up/cool-down phases.
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="device",
            target_id=device_id,
            command=command,
            source="fast",
        )
        return result

    except Exception as e:
        logger.error(f"Error in fast lane control: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/device/{device_id}/state")
async def fast_get_device_state(device_id: str, orchestrator=Depends(get_orchestrator)):
    """
    Fast lane state query.

    Returns immediate device state without verification.
    """
    try:
        from mutech_control.database.connection import get_db_manager
        from mutech_control.database.models import Device
        from sqlalchemy import select
        from uuid import UUID

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            stmt = select(Device).where(Device.id == UUID(device_id))
            result = await session.execute(stmt)
            device = result.scalar_one_or_none()

            if not device:
                raise HTTPException(status_code=404, detail="Device not found")

            return {
                "device_id": str(device.id),
                "name": device.name,
                "device_type": device.device_type,
                "state": device.state,
                "last_checked_at": device.last_checked_at.isoformat()
                if device.last_checked_at
                else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device state: {e}")
        raise HTTPException(status_code=500, detail=str(e))
