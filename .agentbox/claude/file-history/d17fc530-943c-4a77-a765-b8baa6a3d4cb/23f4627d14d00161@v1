"""Control API endpoints for device control."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control", tags=["control"])


def get_orchestrator():
    """Dependency to get orchestrator instance."""
    from mutech_control.main import app

    return app.state.orchestrator


@router.post("/exhibition/{exhibition_id}/{command}")
async def control_exhibition(
    exhibition_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control all devices in an exhibition.

    - **ON**: Devices turned on with 1s stagger
    - **OFF**: Devices turned off in parallel with verification
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="exhibition",
            target_id=exhibition_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling exhibition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/artwork/{artwork_id}/{command}")
async def control_artwork(
    artwork_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control all devices in an artwork.

    - **ON**: Devices turned on with 1s stagger
    - **OFF**: Devices turned off in parallel with verification
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="artwork",
            target_id=artwork_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling artwork: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/device/{device_id}/{command}")
async def control_device(
    device_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control a single device.

    - **ON**: Device turned on
    - **OFF**: Device turned off with verification (except shell devices)
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="device",
            target_id=device_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling device: {e}")
        raise HTTPException(status_code=500, detail=str(e))
