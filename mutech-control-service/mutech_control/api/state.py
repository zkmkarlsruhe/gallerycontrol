"""State API endpoints for querying device states."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mutech_control.database.connection import get_session
from mutech_control.database.models import Artwork, Device, Exhibition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


class DevicePollStatus(BaseModel):
    """Device polling status model."""

    is_verifying: bool = False
    poll_interval: int = 60
    last_polled_at: str | None = None
    seconds_until_next_poll: int = 0


class DeviceState(BaseModel):
    """Device state response model."""

    id: str
    name: str
    device_type: str
    host: str
    port: int | None
    state: int
    enabled: bool
    effective_enabled: bool  # Considers parent artwork/exhibition enabled status
    automation_enabled: bool
    exclude_from_auto_onoff: bool
    last_checked_at: str | None
    next_check_allowed_at: str | None
    poll_status: DevicePollStatus | None = None

    class Config:
        from_attributes = True


class ArtworkState(BaseModel):
    """Artwork state with devices."""

    id: str
    name: str
    enabled: bool
    effective_enabled: bool  # Considers parent exhibition enabled status
    devices: List[DeviceState]

    class Config:
        from_attributes = True


class ExhibitionState(BaseModel):
    """Exhibition state with artworks and devices."""

    id: str
    name: str
    enabled: bool
    effective_enabled: bool  # For exhibitions, same as enabled
    artworks: List[ArtworkState]

    class Config:
        from_attributes = True


def _get_poll_status(request: Request, device_id: str) -> dict | None:
    """Get poll status for a device if state_monitor is available."""
    state_monitor = getattr(request.app.state, "state_monitor", None)
    if state_monitor:
        return state_monitor.get_device_poll_status(device_id)
    return None


@router.get("/exhibitions", response_model=List[ExhibitionState])
async def list_all_exhibitions(request: Request, session=Depends(get_session)):
    """List all exhibitions with full state tree."""
    try:
        stmt = (
            select(Exhibition)
            .options(
                selectinload(Exhibition.artworks).selectinload(Artwork.devices)
            )
            .order_by(Exhibition.name)
        )
        result = await session.execute(stmt)
        exhibitions = result.scalars().all()

        return [
            {
                "id": str(ex.id),
                "name": ex.name,
                "enabled": ex.enabled,
                "effective_enabled": ex.enabled,
                "artworks": [
                    {
                        "id": str(aw.id),
                        "name": aw.name,
                        "enabled": aw.enabled,
                        "effective_enabled": aw.enabled and ex.enabled,
                        "devices": [
                            {
                                "id": str(dev.id),
                                "name": dev.name,
                                "device_type": dev.device_type,
                                "host": dev.host,
                                "port": dev.port,
                                "state": dev.state,
                                "enabled": dev.enabled,
                                "effective_enabled": dev.enabled and aw.enabled and ex.enabled,
                                "automation_enabled": dev.automation_enabled,
                                "exclude_from_auto_onoff": dev.exclude_from_auto_onoff,
                                "last_checked_at": dev.last_checked_at.isoformat()
                                if dev.last_checked_at
                                else None,
                                "next_check_allowed_at": dev.next_check_allowed_at.isoformat()
                                if dev.next_check_allowed_at
                                else None,
                                "poll_status": _get_poll_status(request, str(dev.id)),
                            }
                            for dev in aw.devices
                        ],
                    }
                    for aw in ex.artworks
                ],
            }
            for ex in exhibitions
        ]

    except Exception as e:
        logger.error(f"Error listing exhibitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exhibition/{exhibition_id}", response_model=ExhibitionState)
async def get_exhibition_state(request: Request, exhibition_id: str, session=Depends(get_session)):
    """Get exhibition state with all artworks and devices."""
    try:
        stmt = (
            select(Exhibition)
            .where(Exhibition.id == UUID(exhibition_id))
            .options(
                selectinload(Exhibition.artworks).selectinload(Artwork.devices)
            )
        )
        result = await session.execute(stmt)
        exhibition = result.scalar_one_or_none()

        if not exhibition:
            raise HTTPException(status_code=404, detail="Exhibition not found")

        return {
            "id": str(exhibition.id),
            "name": exhibition.name,
            "enabled": exhibition.enabled,
            "effective_enabled": exhibition.enabled,
            "artworks": [
                {
                    "id": str(aw.id),
                    "name": aw.name,
                    "enabled": aw.enabled,
                    "effective_enabled": aw.enabled and exhibition.enabled,
                    "devices": [
                        {
                            "id": str(dev.id),
                            "name": dev.name,
                            "device_type": dev.device_type,
                            "host": dev.host,
                            "port": dev.port,
                            "state": dev.state,
                            "enabled": dev.enabled,
                            "effective_enabled": dev.enabled and aw.enabled and exhibition.enabled,
                            "automation_enabled": dev.automation_enabled,
                            "exclude_from_auto_onoff": dev.exclude_from_auto_onoff,
                            "last_checked_at": dev.last_checked_at.isoformat()
                            if dev.last_checked_at
                            else None,
                            "next_check_allowed_at": dev.next_check_allowed_at.isoformat()
                            if dev.next_check_allowed_at
                            else None,
                            "poll_status": _get_poll_status(request, str(dev.id)),
                        }
                        for dev in aw.devices
                    ],
                }
                for aw in exhibition.artworks
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exhibition state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/device/{device_id}", response_model=DeviceState)
async def get_device_state(request: Request, device_id: str, session=Depends(get_session)):
    """Get single device state."""
    try:
        stmt = (
            select(Device)
            .where(Device.id == UUID(device_id))
            .options(selectinload(Device.artwork).selectinload(Artwork.exhibition))
        )
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # Compute effective_enabled from parent chain
        effective_enabled = device.enabled
        if device.artwork:
            effective_enabled = effective_enabled and device.artwork.enabled
            if device.artwork.exhibition:
                effective_enabled = effective_enabled and device.artwork.exhibition.enabled

        return {
            "id": str(device.id),
            "name": device.name,
            "device_type": device.device_type,
            "host": device.host,
            "port": device.port,
            "state": device.state,
            "enabled": device.enabled,
            "effective_enabled": effective_enabled,
            "automation_enabled": device.automation_enabled,
            "exclude_from_auto_onoff": device.exclude_from_auto_onoff,
            "last_checked_at": device.last_checked_at.isoformat()
            if device.last_checked_at
            else None,
            "next_check_allowed_at": device.next_check_allowed_at.isoformat()
            if device.next_check_allowed_at
            else None,
            "poll_status": _get_poll_status(request, device_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring")
async def get_monitoring_status(request: Request):
    """Get state monitoring status.

    Returns overall monitoring configuration and status including:
    - Whether monitoring is enabled and running
    - Normal and fast poll intervals
    - List of devices currently in fast poll (verification) mode
    """
    state_monitor = getattr(request.app.state, "state_monitor", None)
    if not state_monitor:
        return {
            "enabled": False,
            "running": False,
            "message": "State monitor not initialized",
        }

    return state_monitor.get_monitoring_status()
