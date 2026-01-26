"""Admin API endpoints for managing exhibitions, artworks, and devices."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from mutech_control.database.connection import get_session
from mutech_control.database.models import (
    Artwork,
    Credential,
    Device,
    Exhibition,
    ScheduledJob,
    ScheduledJobLog,
    ShellTemplate,
)
from mutech_control.devices.shell_manager import load_credentials

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
    schedules_enabled: bool | None = None


class ArtworkCreate(BaseModel):
    """Artwork creation model."""

    exhibition_id: str
    name: str
    enabled: bool = True


class ProtectionTimeSlice(BaseModel):
    """Time slice protection rule."""

    window: int  # Window size in minutes
    max: int  # Max runtime in minutes


class ProtectionConfig(BaseModel):
    """Artwork protection configuration."""

    time_slices: List[ProtectionTimeSlice] | None = None
    max_runtime: int | None = None  # Max continuous runtime in seconds
    cooldown: int | None = None  # Cooldown period in seconds
    force_completion: bool = False  # Ignore OFF until max_runtime
    min_budget_to_start: int = 0  # Minimum budget to start (seconds)


class ArtworkUpdate(BaseModel):
    """Artwork update model."""

    name: str | None = None
    enabled: bool | None = None
    exhibition_id: str | None = None
    protection_config: ProtectionConfig | Dict[str, Any] | None = None
    timeslice_enabled: bool | None = None
    schedules_enabled: bool | None = None


class DeviceCreate(BaseModel):
    """Device creation model."""

    artwork_id: str
    name: str
    device_type: str  # 'pjlink', 'netio', 'anel', 'shell'
    host: str
    port: int | None = None
    enabled: bool = True
    automation_enabled: bool = True
    config: Dict[str, Any] = {}


class DeviceUpdate(BaseModel):
    """Device update model."""

    name: str | None = None
    artwork_id: str | None = None
    host: str | None = None
    port: int | None = None
    enabled: bool | None = None
    automation_enabled: bool | None = None
    schedules_enabled: bool | None = None
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
                "effective_enabled": ex.enabled,
                "created_at": ex.created_at.isoformat(),
                "updated_at": ex.updated_at.isoformat(),
            }
            for ex in exhibitions
        ]

    except Exception as e:
        logger.error(f"Error listing exhibitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exhibitions/{exhibition_id}")
async def get_exhibition(exhibition_id: str, session=Depends(get_session)):
    """Get a single exhibition by ID."""
    try:
        stmt = (
            select(Exhibition)
            .where(Exhibition.id == UUID(exhibition_id))
            .options(selectinload(Exhibition.artworks))
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
            "created_at": exhibition.created_at.isoformat(),
            "updated_at": exhibition.updated_at.isoformat(),
            "artwork_count": len(exhibition.artworks),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exhibition: {e}")
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
            "schedules_enabled": updated.schedules_enabled,
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
                "effective_enabled": aw.enabled and (aw.exhibition.enabled if aw.exhibition else True),
                "created_at": aw.created_at.isoformat(),
                "updated_at": aw.updated_at.isoformat(),
            }
            for aw in artworks
        ]

    except Exception as e:
        logger.error(f"Error listing artworks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artworks/{artwork_id}")
async def get_artwork(artwork_id: str, session=Depends(get_session)):
    """Get a single artwork by ID."""
    try:
        stmt = (
            select(Artwork)
            .where(Artwork.id == UUID(artwork_id))
            .options(
                selectinload(Artwork.exhibition),
                selectinload(Artwork.devices),
            )
        )
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

        return {
            "id": str(artwork.id),
            "name": artwork.name,
            "exhibition_id": str(artwork.exhibition_id),
            "exhibition_name": artwork.exhibition.name if artwork.exhibition else None,
            "enabled": artwork.enabled,
            "effective_enabled": artwork.enabled and (artwork.exhibition.enabled if artwork.exhibition else True),
            "created_at": artwork.created_at.isoformat(),
            "updated_at": artwork.updated_at.isoformat(),
            "device_count": len(artwork.devices),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artwork: {e}")
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


def _validate_protection_config(config: dict) -> None:
    """Validate time slice consistency in protection config.

    For each pair (inner, outer) where outer.window > inner.window:
        max_possible = (outer.window / inner.window) * inner.max
        outer.max must be <= max_possible
    """
    time_slices = config.get("time_slices", [])
    if not time_slices:
        return

    # Sort by window size
    sorted_slices = sorted(time_slices, key=lambda x: x.get("window", 0))

    for i, inner in enumerate(sorted_slices):
        for outer in sorted_slices[i + 1:]:
            inner_window = inner.get("window", 0)
            outer_window = outer.get("window", 0)
            inner_max = inner.get("max", 0)
            outer_max = outer.get("max", 0)

            if inner_window == 0:
                continue

            max_possible = (outer_window / inner_window) * inner_max
            if outer_max > max_possible:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid time slice: {outer_window}min max ({outer_max}min) "
                    f"exceeds possible from {inner_window}min window ({max_possible:.0f}min max)"
                )


@router.put("/artworks/{artwork_id}")
async def update_artwork(
    artwork_id: str, artwork: ArtworkUpdate, request: Request, session=Depends(get_session)
):
    """Update an artwork."""
    try:
        values = {}
        protection_updated = False

        for key, value in artwork.dict().items():
            if value is not None:
                if key == "exhibition_id":
                    values[key] = UUID(value)
                elif key == "protection_config":
                    # Handle protection_config - convert Pydantic model to dict
                    if isinstance(value, dict):
                        # Validate before saving
                        _validate_protection_config(value)
                        values[key] = value
                        protection_updated = True
                else:
                    values[key] = value

        # Allow clearing protection_config by explicitly passing null/empty
        if artwork.protection_config == {} or artwork.dict().get("protection_config") == {}:
            values["protection_config"] = None
            protection_updated = True

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

        # Reload protection config in protection service if updated
        if protection_updated:
            protection_service = getattr(request.app.state, "protection_service", None)
            if protection_service:
                await protection_service.reload_config(UUID(artwork_id))

        return {
            "id": str(updated.id),
            "name": updated.name,
            "exhibition_id": str(updated.exhibition_id),
            "enabled": updated.enabled,
            "protection_config": updated.protection_config,
            "timeslice_enabled": updated.timeslice_enabled,
            "schedules_enabled": updated.schedules_enabled,
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
        stmt = select(Device).options(
            selectinload(Device.artwork).selectinload(Artwork.exhibition)
        )

        if artwork_id:
            stmt = stmt.where(Device.artwork_id == UUID(artwork_id))

        if device_type:
            stmt = stmt.where(Device.device_type == device_type)

        stmt = stmt.order_by(Device.name)
        result = await session.execute(stmt)
        devices = result.scalars().all()

        def compute_effective_enabled(dev):
            """Compute effective_enabled from parent chain."""
            if not dev.enabled:
                return False
            if dev.artwork and not dev.artwork.enabled:
                return False
            if dev.artwork and dev.artwork.exhibition and not dev.artwork.exhibition.enabled:
                return False
            return True

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
                "effective_enabled": compute_effective_enabled(dev),
                "automation_enabled": dev.automation_enabled,
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


@router.get("/devices/{device_id}")
async def get_device(device_id: str, session=Depends(get_session)):
    """Get a single device by ID."""
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
            "artwork_id": str(device.artwork_id),
            "artwork_name": device.artwork.name if device.artwork else None,
            "exhibition_id": str(device.artwork.exhibition_id) if device.artwork else None,
            "exhibition_name": device.artwork.exhibition.name if device.artwork and device.artwork.exhibition else None,
            "enabled": device.enabled,
            "effective_enabled": effective_enabled,
            "automation_enabled": device.automation_enabled,
            "state": device.state,
            "config": device.config,
            "last_checked_at": device.last_checked_at.isoformat() if device.last_checked_at else None,
            "created_at": device.created_at.isoformat(),
            "updated_at": device.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices", status_code=201)
async def create_device(device: DeviceCreate, request: Request, session=Depends(get_session)):
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
            config=device.config,
        )
        session.add(new_device)
        await session.flush()

        # For PJLink devices, link to asset and schedule onboard lamp hours recording
        asset_number = None
        if device.device_type == 'pjlink':
            asset_service = getattr(request.app.state, 'asset_service', None)
            if asset_service:
                asset = await asset_service.link_device_to_asset(new_device, session)
                if asset:
                    asset_number = asset.asset_number
                    # Record initial lamp hours on asset link (onboard event)
                    await session.commit()
                    try:
                        await asset_service.record_lamp_hours_background(new_device.id, 'onboard')
                    except Exception as lh_err:
                        logger.warning(f"Failed to record onboard lamp hours for {new_device.name}: {lh_err}")

        return {
            "id": str(new_device.id),
            "name": new_device.name,
            "device_type": new_device.device_type,
            "host": new_device.host,
            "port": new_device.port,
            "artwork_id": str(new_device.artwork_id),
            "enabled": new_device.enabled,
            "automation_enabled": new_device.automation_enabled,
            "asset_id": str(new_device.asset_id) if new_device.asset_id else None,
            "asset_number": asset_number,
            "resolved": new_device.resolved,
        }

    except Exception as e:
        logger.error(f"Error creating device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/devices/{device_id}")
async def update_device(
    device_id: str, device: DeviceUpdate, request: Request, session=Depends(get_session)
):
    """Update a device."""
    try:
        # First get the existing device to check for changes
        stmt = select(Device).where(Device.id == UUID(device_id))
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            raise HTTPException(status_code=404, detail="Device not found")

        values = {}
        for key, value in device.dict().items():
            if value is not None:
                if key == "artwork_id":
                    values[key] = UUID(value)
                else:
                    values[key] = value

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Check if host/port/device_type is changing for PJLink devices
        asset_service = getattr(request.app.state, 'asset_service', None)
        needs_asset_relink = (
            existing.device_type == 'pjlink' and
            asset_service and
            (
                ('host' in values and values['host'] != existing.host) or
                ('port' in values and values['port'] != existing.port) or
                ('device_type' in values and values['device_type'] != existing.device_type)
            )
        )

        # If re-linking needed and device has existing asset, record offboard first
        if needs_asset_relink and existing.asset_id:
            await asset_service.unlink_device_from_asset(existing.id, session)
            values['asset_id'] = None  # Clear the old asset link
            values['resolved'] = None  # Clear old DNS resolution
            values['resolved_at'] = None

        # Clear cached device info if device connection config changes
        cache_invalidating_fields = {'host', 'port', 'config'}
        if any(field in values for field in cache_invalidating_fields):
            values['cached_info'] = None
            values['cached_info_at'] = None
            logger.info(f"Clearing device cache for {existing.name} due to config change")

        # Perform the update
        stmt = (
            update(Device)
            .where(Device.id == UUID(device_id))
            .values(**values)
            .returning(Device)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        # If host changed for PJLink, re-link to new asset
        if needs_asset_relink and updated.device_type == 'pjlink':
            # Refresh device from session to get updated values
            await session.refresh(updated)
            asset = await asset_service.link_device_to_asset(updated, session)
            if asset:
                # Record onboard lamp hours for new asset
                await asset_service.record_lamp_hours(updated.id, 'onboard', session)

        return {
            "id": str(updated.id),
            "name": updated.name,
            "device_type": updated.device_type,
            "host": updated.host,
            "port": updated.port,
            "artwork_id": str(updated.artwork_id),
            "enabled": updated.enabled,
            "automation_enabled": updated.automation_enabled,
            "asset_id": str(updated.asset_id) if updated.asset_id else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: str, request: Request, session=Depends(get_session)):
    """Delete a device."""
    try:
        # First get the device to check if it's PJLink with asset
        stmt = select(Device).where(Device.id == UUID(device_id))
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        # For PJLink devices with asset, record offboard lamp hours before deletion
        if device.device_type == 'pjlink' and device.asset_id:
            asset_service = getattr(request.app.state, 'asset_service', None)
            if asset_service:
                await asset_service.unlink_device_from_asset(device.id, session)

        # Now delete the device
        stmt = delete(Device).where(Device.id == UUID(device_id))
        await session.execute(stmt)

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


# State change cleanup endpoint
@router.post("/state-changes/cleanup")
async def cleanup_state_changes(
    retention_days: int = 90, session=Depends(get_session)
):
    """Delete old state change logs.

    Args:
        retention_days: Keep logs from the last N days (default 90)

    Returns:
        Count of deleted records
    """
    from datetime import datetime, timedelta, timezone

    from mutech_control.database.models import StateChangeLog

    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        stmt = delete(StateChangeLog).where(StateChangeLog.timestamp < cutoff_date)
        result = await session.execute(stmt)
        deleted_count = result.rowcount

        logger.info(
            f"State change cleanup completed: deleted {deleted_count} records older than {retention_days} days"
        )

        return {
            "success": True,
            "deleted_count": deleted_count,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error cleaning up state changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic models for Credentials
class CredentialCreate(BaseModel):
    """Credential creation model."""

    name: str
    credential_type: str = "shell"  # shell, pjlink, netio, anel
    username: str | None = None
    password: str
    description: str | None = None


class CredentialUpdate(BaseModel):
    """Credential update model."""

    name: str | None = None
    credential_type: str | None = None
    username: str | None = None
    password: str | None = None
    description: str | None = None


# Credential endpoints
@router.get("/credentials")
async def list_credentials(credential_type: str | None = None, session=Depends(get_session)):
    """List all credentials (passwords masked). Optional filter by type."""
    try:
        stmt = select(Credential).order_by(Credential.credential_type, Credential.name)

        # Filter by type if specified
        if credential_type:
            stmt = stmt.where(Credential.credential_type == credential_type)

        result = await session.execute(stmt)
        credentials = result.scalars().all()

        # Build response with device usage info
        response = []

        # Get all devices once for shell placeholder checking
        all_devices_stmt = select(Device)
        all_devices_result = await session.execute(all_devices_stmt)
        all_devices = all_devices_result.scalars().all()

        for cred in credentials:
            cred_id = str(cred.id)
            cred_name = cred.name

            # Find devices using this credential by ID
            devices_by_id = [d for d in all_devices if d.config.get("credential_id") == cred_id]

            # Find shell devices using this credential by name in placeholders
            # Look for {{PASSWORD:name}} or {{USER:name}} patterns
            import re
            placeholder_pattern = re.compile(rf"\{{\{{(PASSWORD|USER):{re.escape(cred_name)}\}}\}}", re.IGNORECASE)
            devices_by_placeholder = []
            for device in all_devices:
                if device.device_type == "shell" and device.config.get("commands"):
                    commands = device.config["commands"]
                    # Check all command types (on, off, status, and custom actions)
                    if isinstance(commands, dict):
                        for cmd_key, cmd_data in commands.items():
                            if isinstance(cmd_data, dict) and cmd_data.get("cmd"):
                                if placeholder_pattern.search(cmd_data["cmd"]):
                                    if device not in devices_by_placeholder:
                                        devices_by_placeholder.append(device)
                                    break

            # Combine both lists, avoiding duplicates
            devices_using = list(devices_by_id)
            for d in devices_by_placeholder:
                if d not in devices_using:
                    devices_using.append(d)

            # Format used_by: show up to 3 device names, then "and X more"
            used_by = []
            if devices_using:
                device_names = [d.name for d in devices_using[:3]]
                used_by = device_names
                if len(devices_using) > 3:
                    used_by.append(f"and {len(devices_using) - 3} more")

            response.append({
                "id": cred_id,
                "name": cred.name,
                "credential_type": cred.credential_type,
                "username": cred.username,
                "password": "********",  # Masked
                "description": cred.description,
                "created_at": cred.created_at.isoformat(),
                "updated_at": cred.updated_at.isoformat(),
                "used_by": used_by,
                "used_by_count": len(devices_using),
            })

        return response

    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/credentials/{credential_id}")
async def get_credential(credential_id: str, session=Depends(get_session)):
    """Get a single credential by ID (password masked)."""
    try:
        stmt = select(Credential).where(Credential.id == UUID(credential_id))
        result = await session.execute(stmt)
        cred = result.scalar_one_or_none()

        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found")

        return {
            "id": str(cred.id),
            "name": cred.name,
            "credential_type": cred.credential_type,
            "username": cred.username,
            "password": "********",  # Masked
            "description": cred.description,
            "created_at": cred.created_at.isoformat(),
            "updated_at": cred.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/credentials", status_code=201)
async def create_credential(credential: CredentialCreate, session=Depends(get_session)):
    """Create a new credential."""
    try:
        new_credential = Credential(
            name=credential.name,
            credential_type=credential.credential_type,
            username=credential.username,
            password=credential.password,
            description=credential.description,
        )
        session.add(new_credential)
        await session.flush()

        # Reload credentials cache
        await load_credentials(session)

        return {
            "id": str(new_credential.id),
            "name": new_credential.name,
            "credential_type": new_credential.credential_type,
            "username": new_credential.username,
            "description": new_credential.description,
        }

    except Exception as e:
        logger.error(f"Error creating credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/credentials/{credential_id}")
async def update_credential(
    credential_id: str, credential: CredentialUpdate, session=Depends(get_session)
):
    """Update a credential."""
    try:
        values = {k: v for k, v in credential.dict().items() if v is not None}

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        stmt = (
            update(Credential)
            .where(Credential.id == UUID(credential_id))
            .values(**values)
            .returning(Credential)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        if not updated:
            raise HTTPException(status_code=404, detail="Credential not found")

        # Reload credentials cache
        await load_credentials(session)

        return {
            "id": str(updated.id),
            "name": updated.name,
            "credential_type": updated.credential_type,
            "username": updated.username,
            "description": updated.description,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/credentials/{credential_id}", status_code=204)
async def delete_credential(credential_id: str, session=Depends(get_session)):
    """Delete a credential."""
    import re
    try:
        # First get the credential to know its name (for shell placeholder check)
        cred_stmt = select(Credential).where(Credential.id == UUID(credential_id))
        cred_result = await session.execute(cred_stmt)
        credential = cred_result.scalar_one_or_none()

        if not credential:
            raise HTTPException(status_code=404, detail="Credential not found")

        cred_name = credential.name

        # Get all devices
        all_devices_stmt = select(Device)
        all_devices_result = await session.execute(all_devices_stmt)
        all_devices = all_devices_result.scalars().all()

        # Find devices using this credential by ID
        devices_by_id = [d for d in all_devices if d.config.get("credential_id") == credential_id]

        # Find shell devices using this credential by name in placeholders
        placeholder_pattern = re.compile(rf"\{{\{{(PASSWORD|USER):{re.escape(cred_name)}\}}\}}", re.IGNORECASE)
        devices_by_placeholder = []
        for device in all_devices:
            if device.device_type == "shell" and device.config.get("commands"):
                commands = device.config["commands"]
                if isinstance(commands, dict):
                    for cmd_key, cmd_data in commands.items():
                        if isinstance(cmd_data, dict) and cmd_data.get("cmd"):
                            if placeholder_pattern.search(cmd_data["cmd"]):
                                if device not in devices_by_placeholder:
                                    devices_by_placeholder.append(device)
                                break

        # Combine both lists
        devices_using = list(devices_by_id)
        for d in devices_by_placeholder:
            if d not in devices_using:
                devices_using.append(d)

        if devices_using:
            device_names = [d.name for d in devices_using[:5]]  # Show first 5
            count = len(devices_using)
            detail = f"Cannot delete: credential is used by {count} device(s): {', '.join(device_names)}"
            if count > 5:
                detail += f" and {count - 5} more"
            raise HTTPException(status_code=409, detail=detail)

        stmt = delete(Credential).where(Credential.id == UUID(credential_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Credential not found")

        # Reload credentials cache
        await load_credentials(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic models for Shell Templates
class ShellTemplateCreate(BaseModel):
    """Shell template creation model."""

    name: str
    description: str | None = None
    status_command: str | None = None
    status_on_pattern: str | None = None
    status_off_pattern: str | None = None
    on_command: str | None = None
    off_command: str | None = None
    actions: list[dict] | None = None  # Array of {name, cmd}
    onoff_mode: bool = True  # True=ON/OFF mode, False=Actions mode


class ShellTemplateUpdate(BaseModel):
    """Shell template update model."""

    name: str | None = None
    description: str | None = None
    status_command: str | None = None
    status_on_pattern: str | None = None
    status_off_pattern: str | None = None
    on_command: str | None = None
    off_command: str | None = None
    actions: list[dict] | None = None
    onoff_mode: bool | None = None


# Shell Template endpoints
@router.get("/shell-templates")
async def list_shell_templates(session=Depends(get_session)):
    """List all shell templates."""
    try:
        stmt = select(ShellTemplate).order_by(ShellTemplate.name)
        result = await session.execute(stmt)
        templates = result.scalars().all()

        return [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "status_command": t.status_command,
                "status_on_pattern": t.status_on_pattern,
                "status_off_pattern": t.status_off_pattern,
                "on_command": t.on_command,
                "off_command": t.off_command,
                "actions": t.actions or [],
                "onoff_mode": t.onoff_mode,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in templates
        ]

    except Exception as e:
        logger.error(f"Error listing shell templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shell-templates/{template_id}")
async def get_shell_template(template_id: str, session=Depends(get_session)):
    """Get a single shell template by ID."""
    try:
        stmt = select(ShellTemplate).where(ShellTemplate.id == UUID(template_id))
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            raise HTTPException(status_code=404, detail="Shell template not found")

        return {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "status_command": template.status_command,
            "status_on_pattern": template.status_on_pattern,
            "status_off_pattern": template.status_off_pattern,
            "on_command": template.on_command,
            "off_command": template.off_command,
            "actions": template.actions or [],
            "onoff_mode": template.onoff_mode,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shell template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shell-templates", status_code=201)
async def create_shell_template(template: ShellTemplateCreate, session=Depends(get_session)):
    """Create a new shell template."""
    try:
        new_template = ShellTemplate(
            name=template.name,
            description=template.description,
            status_command=template.status_command,
            status_on_pattern=template.status_on_pattern,
            status_off_pattern=template.status_off_pattern,
            on_command=template.on_command,
            off_command=template.off_command,
            actions=template.actions,
            onoff_mode=template.onoff_mode,
        )
        session.add(new_template)
        await session.flush()

        return {
            "id": str(new_template.id),
            "name": new_template.name,
            "description": new_template.description,
            "onoff_mode": new_template.onoff_mode,
        }

    except Exception as e:
        logger.error(f"Error creating shell template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/shell-templates/{template_id}")
async def update_shell_template(
    template_id: str, template: ShellTemplateUpdate, session=Depends(get_session)
):
    """Update a shell template."""
    try:
        values = {k: v for k, v in template.dict().items() if v is not None}

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        stmt = (
            update(ShellTemplate)
            .where(ShellTemplate.id == UUID(template_id))
            .values(**values)
            .returning(ShellTemplate)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()

        if not updated:
            raise HTTPException(status_code=404, detail="Shell template not found")

        return {
            "id": str(updated.id),
            "name": updated.name,
            "description": updated.description,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shell template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shell-templates/{template_id}", status_code=204)
async def delete_shell_template(template_id: str, session=Depends(get_session)):
    """Delete a shell template."""
    try:
        stmt = delete(ShellTemplate).where(ShellTemplate.id == UUID(template_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Shell template not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting shell template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/{device_id}/save-as-template", status_code=201)
async def save_device_as_template(
    device_id: str, name: str | None = None, session=Depends(get_session)
):
    """Save a shell device's config as a template."""
    try:
        stmt = select(Device).where(Device.id == UUID(device_id))
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if device.device_type != "shell":
            raise HTTPException(status_code=400, detail="Only shell devices can be saved as templates")

        commands = device.config.get("commands", {})

        # Get actions from new format first, then fall back to old format
        actions = device.config.get("actions", [])
        if not actions and isinstance(commands, dict):
            # Old format: extract custom commands that aren't on/off/status
            standard_commands = {"on", "off", "status"}
            actions = [
                {"name": name, "cmd": cfg.get("cmd")}
                for name, cfg in commands.items()
                if name not in standard_commands and isinstance(cfg, dict) and cfg.get("cmd")
            ]

        # Determine mode: if has on/off commands, it's onoff_mode=True
        has_onoff = bool(commands.get("on") or commands.get("off") or commands.get("status"))
        onoff_mode = has_onoff or not actions

        new_template = ShellTemplate(
            name=name or f"Template from {device.name}",
            description=f"Created from device: {device.name} ({device.host})",
            status_command=commands.get("status", {}).get("cmd"),
            status_on_pattern=commands.get("status", {}).get("onPattern"),
            status_off_pattern=commands.get("status", {}).get("offPattern"),
            on_command=commands.get("on", {}).get("cmd"),
            off_command=commands.get("off", {}).get("cmd"),
            actions=actions if actions else None,
            onoff_mode=onoff_mode,
        )
        session.add(new_template)
        await session.flush()

        return {
            "id": str(new_template.id),
            "name": new_template.name,
            "description": new_template.description,
            "onoff_mode": new_template.onoff_mode,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving device as template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Inventory export endpoint
@router.get("/inventory/export")
async def export_inventory(session=Depends(get_session)):
    """Generate device inventory as plain text (for email or display)."""
    from datetime import datetime, timezone

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

        lines = [
            "MuTech Device Inventory",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        device_type_names = {
            "pjlink": "Projector",
            "netio": "Power Strip",
            "anel": "Power Strip",
            "shell": "Shell",
        }

        for exhibition in exhibitions:
            lines.append(f"### {exhibition.name}")
            lines.append("")

            for artwork in sorted(exhibition.artworks, key=lambda a: a.name):
                lines.append(f"## {artwork.name}")

                for device in sorted(artwork.devices, key=lambda d: d.name):
                    device_type_display = device_type_names.get(device.device_type, device.device_type)

                    if device.device_type == "shell":
                        # For shell, show host or first command
                        if device.host and device.host != "#nohost":
                            lines.append(f"* {device_type_display}: {device.host}")
                        else:
                            lines.append(f"* {device_type_display}: {device.name}")
                    elif device.port is not None:
                        lines.append(f"* {device_type_display}: http://{device.host} Port: {device.port}")
                    else:
                        lines.append(f"* {device_type_display}: http://{device.host}")

                lines.append("")

        return {
            "content": "\n".join(lines),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "exhibition_count": len(exhibitions),
        }

    except Exception as e:
        logger.error(f"Error exporting inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic model for inventory email request
class InventoryEmailRequest(BaseModel):
    """Inventory email request model."""

    exhibition_ids: List[str] | None = None  # Optional filter
    include_disabled: bool = False  # Include disabled items


@router.get("/inventory/email-config")
async def get_email_config():
    """Get email configuration (recipients, subject, from address)."""
    from mutech_control.config import get_config

    config = get_config()

    return {
        "recipients": config.get("email.recipients", []),
        "subject": config.get("email.subject", "MuTech Device Inventory"),
        "from_address": config.get("email.from_address", ""),
        "smtp_configured": bool(config.get("email.smtp_host")),
    }


@router.post("/inventory/email")
async def send_inventory_email(
    request: InventoryEmailRequest, session=Depends(get_session)
):
    """Send device inventory via email.

    Recipients and subject are taken from config.

    Args:
        exhibition_ids: Optional list of exhibition IDs to include (default: all enabled)

    Returns:
        Success status and message
    """
    from mutech_control.config import get_config
    from mutech_control.services.inventory import send_inventory_email as send_email

    config = get_config()
    recipients = config.get("email.recipients", [])
    subject = config.get("email.subject", "MuTech Device Inventory")

    if not recipients:
        return {
            "success": False,
            "message": "No recipients configured in email.recipients",
        }

    try:
        # Build query for exhibitions
        stmt = (
            select(Exhibition)
            .options(
                selectinload(Exhibition.artworks).selectinload(Artwork.devices)
            )
            .order_by(Exhibition.name)
        )

        # Filter by enabled only (unless include_disabled)
        if not request.include_disabled:
            stmt = stmt.where(Exhibition.enabled == True)

        # Filter by exhibition IDs if provided
        if request.exhibition_ids:
            exhibition_uuids = [UUID(eid) for eid in request.exhibition_ids]
            stmt = stmt.where(Exhibition.id.in_(exhibition_uuids))

        result = await session.execute(stmt)
        exhibitions = result.scalars().all()

        # Convert to dict format for the generator
        exhibitions_data = []
        for ex in exhibitions:
            if not request.include_disabled and not ex.enabled:
                continue

            artworks_data = []
            for aw in ex.artworks:
                effective_aw_enabled = aw.enabled and ex.enabled
                if not request.include_disabled and not effective_aw_enabled:
                    continue

                devices_data = []
                for dev in aw.devices:
                    effective_dev_enabled = dev.enabled and effective_aw_enabled
                    if not request.include_disabled and not effective_dev_enabled:
                        continue
                    devices_data.append({
                        "id": str(dev.id),
                        "name": dev.name,
                        "device_type": dev.device_type,
                        "host": dev.host,
                        "port": dev.port,
                        "config": dev.config,
                        "effective_enabled": effective_dev_enabled,
                    })

                if devices_data:  # Only add artwork if it has devices
                    artworks_data.append({
                        "id": str(aw.id),
                        "name": aw.name,
                        "effective_enabled": effective_aw_enabled,
                        "devices": devices_data,
                    })

            if artworks_data:  # Only add exhibition if it has artworks
                exhibitions_data.append({
                    "id": str(ex.id),
                    "name": ex.name,
                    "effective_enabled": ex.enabled,
                    "artworks": artworks_data,
                })

        if not exhibitions_data:
            return {
                "success": False,
                "message": "No enabled devices found to export",
            }

        # Send email
        result = await send_email(
            recipients=recipients,
            subject=subject,
            exhibitions=exhibitions_data,
        )

        return result

    except Exception as e:
        logger.error(f"Error sending inventory email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inventory/preview")
async def preview_inventory(
    exhibition_ids: str | None = None,
    include_disabled: bool = False,
    session=Depends(get_session),
):
    """Preview the inventory text that would be sent in email.

    Args:
        exhibition_ids: Optional comma-separated list of exhibition IDs
        include_disabled: Include disabled exhibitions/artworks/devices

    Returns:
        The plain text content that would be sent
    """
    from mutech_control.services.inventory import generate_inventory_text

    try:
        # Build query for exhibitions
        stmt = (
            select(Exhibition)
            .options(
                selectinload(Exhibition.artworks).selectinload(Artwork.devices)
            )
            .order_by(Exhibition.name)
        )

        # Filter by enabled only (unless include_disabled)
        if not include_disabled:
            stmt = stmt.where(Exhibition.enabled == True)

        # Filter by exhibition IDs if provided
        if exhibition_ids:
            exhibition_uuids = [UUID(eid.strip()) for eid in exhibition_ids.split(",")]
            stmt = stmt.where(Exhibition.id.in_(exhibition_uuids))

        result = await session.execute(stmt)
        exhibitions = result.scalars().all()

        # Convert to dict format for the generator
        exhibitions_data = []
        for ex in exhibitions:
            if not include_disabled and not ex.enabled:
                continue

            artworks_data = []
            for aw in ex.artworks:
                effective_aw_enabled = aw.enabled and ex.enabled
                if not include_disabled and not effective_aw_enabled:
                    continue

                devices_data = []
                for dev in aw.devices:
                    effective_dev_enabled = dev.enabled and effective_aw_enabled
                    if not include_disabled and not effective_dev_enabled:
                        continue
                    devices_data.append({
                        "id": str(dev.id),
                        "name": dev.name,
                        "device_type": dev.device_type,
                        "host": dev.host,
                        "port": dev.port,
                        "config": dev.config,
                        "effective_enabled": effective_dev_enabled,
                    })

                if devices_data:
                    artworks_data.append({
                        "id": str(aw.id),
                        "name": aw.name,
                        "effective_enabled": effective_aw_enabled,
                        "devices": devices_data,
                    })

            if artworks_data:
                exhibitions_data.append({
                    "id": str(ex.id),
                    "name": ex.name,
                    "effective_enabled": ex.enabled,
                    "artworks": artworks_data,
                })

        # Generate plain text inventory
        inventory_text = generate_inventory_text(exhibitions_data)

        return {
            "content": inventory_text,
            "exhibition_count": len(exhibitions_data),
            "device_count": sum(
                len(d)
                for ex in exhibitions_data
                for aw in ex.get("artworks", [])
                for d in [aw.get("devices", [])]
            ),
        }

    except Exception as e:
        logger.error(f"Error previewing inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Shell Command Testing ==========


class ShellTestRequest(BaseModel):
    """Request model for testing shell commands."""

    command: str
    timeout: int = 5  # seconds (max 5 to prevent stale connections)
    credential_id: str | None = None  # Optional credential to replace {{user}}/{{password}}


class ShellTestResponse(BaseModel):
    """Response model for shell command test results."""

    success: bool
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    error: str | None = None


@router.post("/shell/test", response_model=ShellTestResponse)
async def test_shell_command(
    request: ShellTestRequest, db: AsyncSession = Depends(get_session)
):
    """Test a shell command and return stdout, stderr, and exit code.

    This endpoint is for testing shell commands before saving them to a device.
    Commands are executed with credential placeholders replaced.
    Max timeout is 5 seconds to prevent stale connections.
    """
    import asyncio
    import signal
    import time

    from mutech_control.devices.shell_manager import replace_credential_placeholders

    # Enforce max timeout of 5 seconds
    timeout = min(request.timeout, 5)

    cmd = request.command

    # If credential_id provided, replace simple {{user}} and {{password}} placeholders
    if request.credential_id:
        from sqlalchemy import select

        stmt = select(Credential).where(Credential.id == request.credential_id)
        result = await db.execute(stmt)
        cred = result.scalar_one_or_none()
        if cred:
            cmd = cmd.replace("{{user}}", cred.username or "")
            cmd = cmd.replace("{{password}}", cred.password or "")

    # Also replace named placeholders like {{PASSWORD:name}}
    cmd = replace_credential_placeholders(cmd)
    start_time = time.monotonic()
    proc = None

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # Create new process group for clean kill
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            # Kill entire process group to handle child processes
            try:
                import os
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return ShellTestResponse(
                success=False,
                exit_code=None,
                stdout="",
                stderr="",
                duration_ms=duration_ms,
                error=f"Command timed out after {timeout} seconds",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Truncate output to prevent huge responses
        max_output = 10000
        stdout_str = stdout.decode(errors="replace")[:max_output]
        stderr_str = stderr.decode(errors="replace")[:max_output]

        return ShellTestResponse(
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(f"Error testing shell command: {e}")
        # Ensure process is killed on error
        if proc and proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except Exception:
                pass
        return ShellTestResponse(
            success=False,
            exit_code=None,
            stdout="",
            stderr="",
            duration_ms=duration_ms,
            error=str(e),
        )


# Host reachability check
class HostCheckRequest(BaseModel):
    """Host check request model."""

    host: str
    port: int = 80  # Default port for basic TCP check
    device_type: str = "generic"  # pjlink, netio, anel, or generic


class HostCheckResponse(BaseModel):
    """Host check response model."""

    reachable: bool
    host: str
    port: int
    error: str | None = None
    duration_ms: int = 0


@router.post("/check-host")
async def check_host_reachability(request: HostCheckRequest) -> HostCheckResponse:
    """Check if a host is reachable via TCP connection.

    This performs a quick TCP connect test to verify the host is reachable.
    For device-specific ports:
    - pjlink: default port 4352
    - netio: default port 80 (HTTP API)
    - anel: default port 80 (HTTP API)
    """
    import socket
    import time

    # Use device-specific default ports if port is default
    port = request.port
    if request.device_type == "pjlink" and port == 80:
        port = 4352
    elif request.device_type in ("netio", "anel") and port == 80:
        port = 80  # HTTP API

    start_time = time.monotonic()

    try:
        # First resolve the hostname
        try:
            # Use getaddrinfo for proper DNS resolution
            loop = asyncio.get_event_loop()
            infos = await loop.getaddrinfo(
                request.host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            )
            if not infos:
                return HostCheckResponse(
                    reachable=False,
                    host=request.host,
                    port=port,
                    error=f"Could not resolve hostname: {request.host}",
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
        except socket.gaierror as e:
            return HostCheckResponse(
                reachable=False,
                host=request.host,
                port=port,
                error=f"DNS resolution failed: {e}",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Try to connect with a short timeout
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(request.host, port),
                timeout=3.0,  # 3 second timeout
            )
            writer.close()
            await writer.wait_closed()

            return HostCheckResponse(
                reachable=True,
                host=request.host,
                port=port,
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        except asyncio.TimeoutError:
            return HostCheckResponse(
                reachable=False,
                host=request.host,
                port=port,
                error="Connection timed out",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        except ConnectionRefusedError:
            return HostCheckResponse(
                reachable=False,
                host=request.host,
                port=port,
                error="Connection refused",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        except OSError as e:
            return HostCheckResponse(
                reachable=False,
                host=request.host,
                port=port,
                error=f"Connection failed: {e}",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

    except Exception as e:
        logger.error(f"Error checking host reachability: {e}")
        return HostCheckResponse(
            reachable=False,
            host=request.host,
            port=port,
            error=str(e),
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )


# ========== Scheduled Jobs (Cron) Endpoints ==========


class ScheduledJobCreate(BaseModel):
    """Create a new scheduled job (recurring or one-shot)."""

    name: str
    cron_expression: str | None = None  # Required for recurring, None for one-shot
    job_type: str = "device"  # 'system' or 'device'
    # One-shot support
    run_once: bool = False  # True for one-shot jobs
    run_at: datetime | None = None  # When to run (for one-shot jobs)
    # Target flexibility
    target_type: str = "device"  # 'device', 'artwork', or 'exhibition'
    target_id: str | None = None  # Generic UUID for artwork/exhibition
    # Device job fields (backward compat)
    target_device_id: str | None = None
    action_type: str | None = None  # 'on', 'off', 'action'
    action_name: str | None = None  # For shell actions
    # System job fields
    task_name: str | None = None
    task_config: dict | None = None
    enabled: bool = True


class ScheduledJobOnceCreate(BaseModel):
    """Create a one-shot scheduled job (simplified)."""

    name: str
    run_at: datetime  # When to execute
    target_type: str = "device"  # 'device', 'artwork', or 'exhibition'
    target_id: str  # Target UUID
    action_type: str  # 'on' or 'off'


class ScheduledJobUpdate(BaseModel):
    """Update a scheduled job."""

    name: str | None = None
    cron_expression: str | None = None
    target_device_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    action_type: str | None = None
    action_name: str | None = None
    task_config: dict | None = None
    enabled: bool | None = None


@router.get("/scheduled-jobs")
async def list_scheduled_jobs(
    job_type: str | None = None,
    device_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    target_device_id: str | None = None,
    session=Depends(get_session),
):
    """List all scheduled jobs.

    Args:
        job_type: Filter by 'system' or 'device'
        device_id: Filter by target device ID (deprecated, use target_device_id)
        target_type: Filter by target type ('device', 'artwork', 'exhibition', 'all')
        target_id: Filter by target ID (for artwork/exhibition)
        target_device_id: Filter by target device ID
    """
    try:
        stmt = select(ScheduledJob).options(selectinload(ScheduledJob.target_device))

        if job_type:
            stmt = stmt.where(ScheduledJob.job_type == job_type)

        # Support both old 'device_id' and new 'target_device_id' params
        effective_device_id = target_device_id or device_id
        if effective_device_id:
            stmt = stmt.where(ScheduledJob.target_device_id == UUID(effective_device_id))

        # Filter by target_type
        if target_type:
            stmt = stmt.where(ScheduledJob.target_type == target_type)

        # Filter by target_id (for artwork/exhibition targets)
        if target_id:
            stmt = stmt.where(ScheduledJob.target_id == UUID(target_id))

        stmt = stmt.order_by(ScheduledJob.job_type, ScheduledJob.name)
        result = await session.execute(stmt)
        jobs = result.scalars().all()

        return [
            {
                "id": str(job.id),
                "name": job.name,
                "job_type": job.job_type,
                "cron_expression": job.cron_expression,
                "run_once": job.run_once,
                "target_type": job.target_type,
                "target_id": str(job.target_id) if job.target_id else None,
                "target_device_id": str(job.target_device_id) if job.target_device_id else None,
                "target_device_name": job.target_device.name if job.target_device else None,
                "action_type": job.action_type,
                "action_name": job.action_name,
                "task_name": job.task_name,
                "task_config": job.task_config,
                "enabled": job.enabled,
                "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                "last_success": job.last_success,
                "last_error": job.last_error,
                "last_duration_ms": job.last_duration_ms,
                "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
                "executed_at": job.executed_at.isoformat() if job.executed_at else None,
                "fail_count": job.fail_count,
                "circuit_open": job.circuit_open,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
            }
            for job in jobs
        ]

    except Exception as e:
        logger.error(f"Error listing scheduled jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: Routes with static paths (/once, /cron/preview) must be defined
# BEFORE routes with path parameters ({job_id}) to avoid FastAPI matching issues.


@router.post("/scheduled-jobs/once", status_code=201)
async def create_one_shot_job(
    job: ScheduledJobOnceCreate, request: Request, session=Depends(get_session)
):
    """Create a one-shot scheduled job (simplified API).

    This is a convenience endpoint for scheduling one-time power on/off tasks
    for devices, artworks, exhibitions, or all devices.

    Example:
        POST /api/admin/scheduled-jobs/once
        {
            "name": "Turn off Grimonprez at 6pm",
            "target_type": "exhibition",
            "target_id": "uuid-here",
            "action_type": "off",
            "run_at": "2026-01-22T18:00:00"
        }
    """
    try:
        # Validate target_type
        if job.target_type not in ("device", "artwork", "exhibition", "all"):
            raise HTTPException(status_code=400, detail="target_type must be 'device', 'artwork', 'exhibition', or 'all'")

        # Validate action_type
        if job.action_type not in ("on", "off"):
            raise HTTPException(status_code=400, detail="action_type must be 'on' or 'off'")

        # Verify target exists (skip for "all" target type)
        if job.target_type != "all":
            if job.target_type == "device":
                target_stmt = select(Device).where(Device.id == UUID(job.target_id))
            elif job.target_type == "artwork":
                target_stmt = select(Artwork).where(Artwork.id == UUID(job.target_id))
            else:
                target_stmt = select(Exhibition).where(Exhibition.id == UUID(job.target_id))

            target_result = await session.execute(target_stmt)
            target = target_result.scalar_one_or_none()
            if not target:
                raise HTTPException(status_code=404, detail=f"Target {job.target_type} not found")

        # Strip timezone for DB compatibility
        next_run_at = job.run_at
        if next_run_at.tzinfo is not None:
            next_run_at = next_run_at.replace(tzinfo=None)

        # Create the one-shot job
        # For "all" target, target_id is empty string so we don't try to parse it as UUID
        new_job = ScheduledJob(
            name=job.name,
            job_type="device",
            run_once=True,
            target_type=job.target_type,
            target_id=UUID(job.target_id) if job.target_type in ("artwork", "exhibition") else None,
            target_device_id=UUID(job.target_id) if job.target_type == "device" else None,
            action_type=job.action_type,
            enabled=True,
            next_run_at=next_run_at,
        )
        session.add(new_job)
        await session.flush()

        # Build target_id for response
        response_target_id = None
        if new_job.target_id:
            response_target_id = str(new_job.target_id)
        elif new_job.target_device_id:
            response_target_id = str(new_job.target_device_id)

        return {
            "id": str(new_job.id),
            "name": new_job.name,
            "target_type": new_job.target_type,
            "target_id": response_target_id,
            "action_type": new_job.action_type,
            "run_at": new_job.next_run_at.isoformat() if new_job.next_run_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating one-shot job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs/cron/preview")
async def preview_cron_schedule(cron_expression: str, count: int = 10):
    """Preview the next run times for a cron expression.

    Args:
        cron_expression: Standard cron expression (minute hour day month weekday)
        count: Number of future runs to return (max 20)
    """
    from mutech_control.scheduler.cron_scheduler import CronScheduler

    try:
        # Validate cron expression
        is_valid, error = CronScheduler.validate_cron_expression(cron_expression)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")

        # Get next runs
        count = min(count, 20)  # Cap at 20
        next_runs = CronScheduler.get_next_runs(cron_expression, count=count)

        return {
            "cron_expression": cron_expression,
            "next_runs": [run.isoformat() for run in next_runs],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing cron schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs/{job_id}")
async def get_scheduled_job(job_id: str, session=Depends(get_session)):
    """Get a single scheduled job by ID."""
    try:
        stmt = (
            select(ScheduledJob)
            .where(ScheduledJob.id == UUID(job_id))
            .options(selectinload(ScheduledJob.target_device))
        )
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Scheduled job not found")

        return {
            "id": str(job.id),
            "name": job.name,
            "job_type": job.job_type,
            "cron_expression": job.cron_expression,
            "run_once": job.run_once,
            "target_type": job.target_type,
            "target_id": str(job.target_id) if job.target_id else None,
            "target_device_id": str(job.target_device_id) if job.target_device_id else None,
            "target_device_name": job.target_device.name if job.target_device else None,
            "action_type": job.action_type,
            "action_name": job.action_name,
            "task_name": job.task_name,
            "task_config": job.task_config,
            "enabled": job.enabled,
            "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
            "last_success": job.last_success,
            "last_error": job.last_error,
            "last_duration_ms": job.last_duration_ms,
            "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
            "executed_at": job.executed_at.isoformat() if job.executed_at else None,
            "fail_count": job.fail_count,
            "circuit_open": job.circuit_open,
            "backoff_until": job.backoff_until.isoformat() if job.backoff_until else None,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs", status_code=201)
async def create_scheduled_job(
    job: ScheduledJobCreate, request: Request, session=Depends(get_session)
):
    """Create a new scheduled job (recurring or one-shot).

    For recurring jobs, provide cron_expression.
    For one-shot jobs, set run_once=True and provide run_at.
    For device jobs, provide target_device_id (or target_id for artwork/exhibition) and action_type.
    For system jobs, provide task_name.
    """
    from mutech_control.scheduler.cron_scheduler import CronScheduler

    try:
        # Determine if this is a one-shot or recurring job
        is_one_shot = job.run_once

        if is_one_shot:
            # One-shot validation
            if not job.run_at:
                raise HTTPException(status_code=400, detail="run_at required for one-shot jobs")
            next_run_at = job.run_at
            # Strip timezone for DB compatibility
            if next_run_at.tzinfo is not None:
                next_run_at = next_run_at.replace(tzinfo=None)
        else:
            # Recurring validation
            if not job.cron_expression:
                raise HTTPException(status_code=400, detail="cron_expression required for recurring jobs")
            is_valid, error = CronScheduler.validate_cron_expression(job.cron_expression)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")
            # Calculate next run time (strip timezone for DB compatibility)
            next_runs = CronScheduler.get_next_runs(job.cron_expression, count=1)
            next_run_at = next_runs[0].replace(tzinfo=None) if next_runs else None

        # Validate target_type
        if job.target_type not in ("device", "artwork", "exhibition", "all"):
            raise HTTPException(status_code=400, detail="target_type must be 'device', 'artwork', 'exhibition', or 'all'")

        # Validate job type specific fields
        if job.job_type == "device":
            if not job.action_type:
                raise HTTPException(status_code=400, detail="action_type required for device jobs")
            if job.action_type not in ("on", "off", "action"):
                raise HTTPException(status_code=400, detail="action_type must be 'on', 'off', or 'action'")
            if job.action_type == "action" and not job.action_name:
                raise HTTPException(status_code=400, detail="action_name required for action type")

            # Validate target based on target_type (skip for "all")
            if job.target_type == "all":
                # "all" target doesn't need target_id or target_device_id
                pass
            elif job.target_type == "device":
                if not job.target_device_id:
                    raise HTTPException(status_code=400, detail="target_device_id required for device target")
                # Verify device exists
                device_stmt = select(Device).where(Device.id == UUID(job.target_device_id))
                device_result = await session.execute(device_stmt)
                device = device_result.scalar_one_or_none()
                if not device:
                    raise HTTPException(status_code=404, detail="Target device not found")
            else:
                # artwork or exhibition
                if not job.target_id:
                    raise HTTPException(status_code=400, detail=f"target_id required for {job.target_type} target")
                # Verify artwork/exhibition exists
                if job.target_type == "artwork":
                    target_stmt = select(Artwork).where(Artwork.id == UUID(job.target_id))
                else:
                    target_stmt = select(Exhibition).where(Exhibition.id == UUID(job.target_id))
                target_result = await session.execute(target_stmt)
                target = target_result.scalar_one_or_none()
                if not target:
                    raise HTTPException(status_code=404, detail=f"Target {job.target_type} not found")

        elif job.job_type == "system":
            if not job.task_name:
                raise HTTPException(status_code=400, detail="task_name required for system jobs")
        else:
            raise HTTPException(status_code=400, detail="job_type must be 'system' or 'device'")

        new_job = ScheduledJob(
            name=job.name,
            job_type=job.job_type,
            cron_expression=job.cron_expression if not is_one_shot else None,
            run_once=is_one_shot,
            target_type=job.target_type,
            target_id=UUID(job.target_id) if job.target_id else None,
            target_device_id=UUID(job.target_device_id) if job.target_device_id else None,
            action_type=job.action_type,
            action_name=job.action_name,
            task_name=job.task_name,
            task_config=job.task_config,
            enabled=job.enabled,
            next_run_at=next_run_at,
        )
        session.add(new_job)
        await session.flush()

        return {
            "id": str(new_job.id),
            "name": new_job.name,
            "job_type": new_job.job_type,
            "cron_expression": new_job.cron_expression,
            "run_once": new_job.run_once,
            "target_type": new_job.target_type,
            "next_run_at": new_job.next_run_at.isoformat() if new_job.next_run_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scheduled-jobs/{job_id}")
async def update_scheduled_job(
    job_id: str, job: ScheduledJobUpdate, session=Depends(get_session)
):
    """Update a scheduled job."""
    from mutech_control.scheduler.cron_scheduler import CronScheduler

    try:
        stmt = select(ScheduledJob).where(ScheduledJob.id == UUID(job_id))
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            raise HTTPException(status_code=404, detail="Scheduled job not found")

        # Build update values
        values = {}
        for key, value in job.dict().items():
            if value is not None:
                if key in ("target_device_id", "target_id"):
                    values[key] = UUID(value)
                else:
                    values[key] = value

        # Validate cron expression if being updated
        if "cron_expression" in values:
            is_valid, error = CronScheduler.validate_cron_expression(values["cron_expression"])
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")
            # Recalculate next run time (strip timezone for DB compatibility)
            next_runs = CronScheduler.get_next_runs(values["cron_expression"], count=1)
            values["next_run_at"] = next_runs[0].replace(tzinfo=None) if next_runs else None

        if not values:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Apply updates
        for key, value in values.items():
            setattr(existing, key, value)

        await session.flush()

        return {
            "id": str(existing.id),
            "name": existing.name,
            "enabled": existing.enabled,
            "next_run_at": existing.next_run_at.isoformat() if existing.next_run_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled-jobs/{job_id}", status_code=204)
async def delete_scheduled_job(job_id: str, session=Depends(get_session)):
    """Delete a scheduled job."""
    try:
        stmt = delete(ScheduledJob).where(ScheduledJob.id == UUID(job_id))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled job not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs/{job_id}/trigger")
async def trigger_scheduled_job(job_id: str, request: Request, session=Depends(get_session)):
    """Trigger immediate execution of a scheduled job.

    The job will run on the next scheduler check cycle.
    """
    cron_scheduler = getattr(request.app.state, "cron_scheduler", None)
    if not cron_scheduler:
        raise HTTPException(status_code=503, detail="Cron scheduler not available")

    try:
        success = await cron_scheduler.trigger_job(UUID(job_id))
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Job not found, circuit open, or already running",
            )

        return {"status": "triggered", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering scheduled job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-jobs/{job_id}/reset-circuit")
async def reset_scheduled_job_circuit(
    job_id: str, request: Request, session=Depends(get_session)
):
    """Reset circuit breaker for a scheduled job.

    After 5 consecutive failures, a job's circuit opens and it stops running.
    This endpoint resets the circuit, allowing the job to run again.
    """
    cron_scheduler = getattr(request.app.state, "cron_scheduler", None)
    if not cron_scheduler:
        raise HTTPException(status_code=503, detail="Cron scheduler not available")

    try:
        success = await cron_scheduler.reset_circuit(UUID(job_id))
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        return {"status": "reset", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting job circuit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs/{job_id}/logs")
async def get_scheduled_job_logs(
    job_id: str, limit: int = 50, session=Depends(get_session)
):
    """Get execution logs for a scheduled job."""
    try:
        stmt = (
            select(ScheduledJobLog)
            .where(ScheduledJobLog.job_id == UUID(job_id))
            .order_by(ScheduledJobLog.executed_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

        return [
            {
                "id": str(log.id),
                "scheduled_at": log.scheduled_at.isoformat(),
                "executed_at": log.executed_at.isoformat(),
                "success": log.success,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "result": log.result,
            }
            for log in logs
        ]

    except Exception as e:
        logger.error(f"Error getting scheduled job logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cron-scheduler/status")
async def get_cron_scheduler_status(request: Request):
    """Get unified cron scheduler status.

    Returns status of all scheduled jobs including system and device jobs.
    """
    cron_scheduler = getattr(request.app.state, "cron_scheduler", None)
    if not cron_scheduler:
        raise HTTPException(status_code=503, detail="Cron scheduler not available")

    try:
        return await cron_scheduler.get_status()
    except Exception as e:
        logger.error(f"Error getting cron scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
