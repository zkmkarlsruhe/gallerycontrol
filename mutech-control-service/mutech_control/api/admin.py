"""Admin API endpoints for managing exhibitions, artworks, and devices."""

import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from mutech_control.database.connection import get_session
from mutech_control.database.models import Artwork, Device, Exhibition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Pydantic models
class ExhibitionCreate(BaseModel):
    """Exhibition creation model."""

    name: str
    enabled: bool = True


class ExhibitionUpdate(BaseModel):
    """Exhibition update model."""

    name: str | None = None
    enabled: bool | None = None


class ArtworkCreate(BaseModel):
    """Artwork creation model."""

    exhibition_id: str
    name: str
    enabled: bool = True


class ArtworkUpdate(BaseModel):
    """Artwork update model."""

    name: str | None = None
    enabled: bool | None = None
    exhibition_id: str | None = None


class DeviceCreate(BaseModel):
    """Device creation model."""

    artwork_id: str
    name: str
    device_type: str  # 'pjlink', 'netio', 'anel', 'shell'
    host: str
    port: int | None = None
    enabled: bool = True
    automation_enabled: bool = True
    exclude_from_auto_onoff: bool = False
    config: Dict[str, Any] = {}


class DeviceUpdate(BaseModel):
    """Device update model."""

    name: str | None = None
    artwork_id: str | None = None
    host: str | None = None
    port: int | None = None
    enabled: bool | None = None
    automation_enabled: bool | None = None
    exclude_from_auto_onoff: bool | None = None
    config: Dict[str, Any] | None = None


# Exhibition endpoints
@router.get("/exhibitions")
async def list_exhibitions(session=Depends(get_session)):
    """List all exhibitions."""
    try:
        stmt = select(Exhibition).order_by(Exhibition.name)
        result = await session.execute(stmt)
        exhibitions = result.scalars().all()

        return [
            {
                "id": str(ex.id),
                "name": ex.name,
                "enabled": ex.enabled,
                "created_at": ex.created_at.isoformat(),
                "updated_at": ex.updated_at.isoformat(),
            }
            for ex in exhibitions
        ]

    except Exception as e:
        logger.error(f"Error listing exhibitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exhibitions", status_code=201)
async def create_exhibition(
    exhibition: ExhibitionCreate, session=Depends(get_session)
):
    """Create a new exhibition."""
    try:
        new_exhibition = Exhibition(name=exhibition.name, enabled=exhibition.enabled)
        session.add(new_exhibition)
        await session.flush()

        return {
            "id": str(new_exhibition.id),
            "name": new_exhibition.name,
            "enabled": new_exhibition.enabled,
        }

    except Exception as e:
        logger.error(f"Error creating exhibition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/exhibitions/{exhibition_id}")
async def update_exhibition(
    exhibition_id: str, exhibition: ExhibitionUpdate, session=Depends(get_session)
):
    """Update an exhibition."""
    try:
        values = {k: v for k, v in exhibition.dict().items() if v is not None}

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        stmt = (
            update(Exhibition)
            .where(Exhibition.id == UUID(exhibition_id))
            .values(**values)
            .returning(Exhibition)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        if not updated:
            raise HTTPException(status_code=404, detail="Exhibition not found")

        return {
            "id": str(updated.id),
            "name": updated.name,
            "enabled": updated.enabled,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating exhibition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/exhibitions/{exhibition_id}", status_code=204)
async def delete_exhibition(exhibition_id: str, session=Depends(get_session)):
    """Delete an exhibition (cascades to artworks and devices)."""
    try:
        stmt = delete(Exhibition).where(Exhibition.id == UUID(exhibition_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Exhibition not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting exhibition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Artwork endpoints
@router.get("/artworks")
async def list_artworks(
    exhibition_id: str | None = None, session=Depends(get_session)
):
    """List all artworks, optionally filtered by exhibition."""
    try:
        stmt = select(Artwork).options(selectinload(Artwork.exhibition))

        if exhibition_id:
            stmt = stmt.where(Artwork.exhibition_id == UUID(exhibition_id))

        stmt = stmt.order_by(Artwork.name)
        result = await session.execute(stmt)
        artworks = result.scalars().all()

        return [
            {
                "id": str(aw.id),
                "name": aw.name,
                "exhibition_id": str(aw.exhibition_id),
                "exhibition_name": aw.exhibition.name if aw.exhibition else None,
                "enabled": aw.enabled,
                "created_at": aw.created_at.isoformat(),
                "updated_at": aw.updated_at.isoformat(),
            }
            for aw in artworks
        ]

    except Exception as e:
        logger.error(f"Error listing artworks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/artworks", status_code=201)
async def create_artwork(artwork: ArtworkCreate, session=Depends(get_session)):
    """Create a new artwork."""
    try:
        new_artwork = Artwork(
            exhibition_id=UUID(artwork.exhibition_id),
            name=artwork.name,
            enabled=artwork.enabled,
        )
        session.add(new_artwork)
        await session.flush()

        return {
            "id": str(new_artwork.id),
            "name": new_artwork.name,
            "exhibition_id": str(new_artwork.exhibition_id),
            "enabled": new_artwork.enabled,
        }

    except Exception as e:
        logger.error(f"Error creating artwork: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/artworks/{artwork_id}")
async def update_artwork(
    artwork_id: str, artwork: ArtworkUpdate, session=Depends(get_session)
):
    """Update an artwork."""
    try:
        values = {}
        for key, value in artwork.dict().items():
            if value is not None:
                if key == "exhibition_id":
                    values[key] = UUID(value)
                else:
                    values[key] = value

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        stmt = (
            update(Artwork)
            .where(Artwork.id == UUID(artwork_id))
            .values(**values)
            .returning(Artwork)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        if not updated:
            raise HTTPException(status_code=404, detail="Artwork not found")

        return {
            "id": str(updated.id),
            "name": updated.name,
            "exhibition_id": str(updated.exhibition_id),
            "enabled": updated.enabled,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating artwork: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/artworks/{artwork_id}", status_code=204)
async def delete_artwork(artwork_id: str, session=Depends(get_session)):
    """Delete an artwork (cascades to devices)."""
    try:
        stmt = delete(Artwork).where(Artwork.id == UUID(artwork_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Artwork not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting artwork: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Device endpoints
@router.get("/devices")
async def list_devices(
    artwork_id: str | None = None,
    device_type: str | None = None,
    session=Depends(get_session),
):
    """List all devices, optionally filtered by artwork or device type."""
    try:
        stmt = select(Device).options(selectinload(Device.artwork))

        if artwork_id:
            stmt = stmt.where(Device.artwork_id == UUID(artwork_id))

        if device_type:
            stmt = stmt.where(Device.device_type == device_type)

        stmt = stmt.order_by(Device.name)
        result = await session.execute(stmt)
        devices = result.scalars().all()

        return [
            {
                "id": str(dev.id),
                "name": dev.name,
                "device_type": dev.device_type,
                "host": dev.host,
                "port": dev.port,
                "artwork_id": str(dev.artwork_id),
                "artwork_name": dev.artwork.name if dev.artwork else None,
                "enabled": dev.enabled,
                "automation_enabled": dev.automation_enabled,
                "exclude_from_auto_onoff": dev.exclude_from_auto_onoff,
                "state": dev.state,
                "config": dev.config,
                "created_at": dev.created_at.isoformat(),
                "updated_at": dev.updated_at.isoformat(),
            }
            for dev in devices
        ]

    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices", status_code=201)
async def create_device(device: DeviceCreate, session=Depends(get_session)):
    """Create a new device."""
    try:
        new_device = Device(
            artwork_id=UUID(device.artwork_id),
            name=device.name,
            device_type=device.device_type,
            host=device.host,
            port=device.port,
            enabled=device.enabled,
            automation_enabled=device.automation_enabled,
            exclude_from_auto_onoff=device.exclude_from_auto_onoff,
            config=device.config,
        )
        session.add(new_device)
        await session.flush()

        return {
            "id": str(new_device.id),
            "name": new_device.name,
            "device_type": new_device.device_type,
            "host": new_device.host,
            "port": new_device.port,
            "artwork_id": str(new_device.artwork_id),
            "enabled": new_device.enabled,
            "automation_enabled": new_device.automation_enabled,
            "exclude_from_auto_onoff": new_device.exclude_from_auto_onoff,
        }

    except Exception as e:
        logger.error(f"Error creating device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/devices/{device_id}")
async def update_device(
    device_id: str, device: DeviceUpdate, session=Depends(get_session)
):
    """Update a device."""
    try:
        values = {}
        for key, value in device.dict().items():
            if value is not None:
                if key == "artwork_id":
                    values[key] = UUID(value)
                else:
                    values[key] = value

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        stmt = (
            update(Device)
            .where(Device.id == UUID(device_id))
            .values(**values)
            .returning(Device)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        if not updated:
            raise HTTPException(status_code=404, detail="Device not found")

        return {
            "id": str(updated.id),
            "name": updated.name,
            "device_type": updated.device_type,
            "host": updated.host,
            "port": updated.port,
            "artwork_id": str(updated.artwork_id),
            "enabled": updated.enabled,
            "automation_enabled": updated.automation_enabled,
            "exclude_from_auto_onoff": updated.exclude_from_auto_onoff,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, session=Depends(get_session)):
    """Delete a device."""
    try:
        stmt = delete(Device).where(Device.id == UUID(device_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Device not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Config reload endpoint
@router.post("/config/reload")
async def reload_config():
    """Manually trigger configuration reload."""
    try:
        from mutech_control.config import reload_config

        reload_config()
        return {"success": True, "message": "Configuration reloaded"}

    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
