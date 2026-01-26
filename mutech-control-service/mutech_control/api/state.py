"""State API endpoints for querying device states."""

import json
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mutech_control.config import get_config
from mutech_control.database.connection import get_session
from mutech_control.database.models import Artwork, Device, Exhibition, LampHoursLog, Satellite
from mutech_control.devices.base import STATE_NAMES, state_to_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


def _get_shell_actions(device) -> list:
    """Extract action buttons from shell device config.

    For shell devices, actions are custom commands that are not on/off/status.
    These become clickable buttons in the UI.

    Supports two formats:
    1. New format: config.actions array of {name, cmd}
    2. Old format: commands in the commands dict that are not on/off/status
    """
    if device.device_type != "shell" or not device.config:
        return []

    actions = []

    # New format: check for actions array first
    if "actions" in device.config and isinstance(device.config["actions"], list):
        for action in device.config["actions"]:
            if isinstance(action, dict) and action.get("name") and action.get("cmd"):
                actions.append({"name": action["name"], "cmd": action["cmd"]})

    # If no actions found, fall back to old format (commands dict)
    if not actions:
        commands = device.config.get("commands", {})
        if commands:
            # Standard commands that are not shown as action buttons
            standard_commands = {"on", "off", "status"}

            # Handle dict format {"cmd_name": {"cmd": "..."}}
            if isinstance(commands, dict):
                for name, cfg in commands.items():
                    if name not in standard_commands and isinstance(cfg, dict) and cfg.get("cmd"):
                        actions.append({"name": name, "cmd": cfg["cmd"]})
            # Handle list format [{"name": "...", "cmd": "..."}]
            elif isinstance(commands, list):
                for cfg in commands:
                    if isinstance(cfg, dict):
                        name = cfg.get("name", "").lower()
                        if name not in standard_commands and cfg.get("cmd"):
                            actions.append({"name": cfg.get("name", "action"), "cmd": cfg["cmd"]})

    return actions


class DevicePollStatus(BaseModel):
    """Device polling status model."""

    is_verifying: bool = False
    poll_interval: int = 60
    last_polled_at: str | None = None
    seconds_until_next_poll: int = 0


class DeviceAction(BaseModel):
    """Device action model for shell commands."""

    name: str
    cmd: str


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
    schedules_enabled: bool = False  # Enable schedules feature
    last_checked_at: str | None
    next_check_allowed_at: str | None
    poll_status: DevicePollStatus | None = None
    actions: List[DeviceAction] = []
    config: dict | None = None  # Device-specific configuration
    resolved: str | None = None  # Resolved hostname/IP from DNS
    asset_id: str | None = None  # Linked asset ID (PJLink only)
    lamp_hours: int | None = None  # Last recorded lamp hours (PJLink only)

    class Config:
        from_attributes = True


class ArtworkState(BaseModel):
    """Artwork state with devices."""

    id: str
    name: str
    enabled: bool
    effective_enabled: bool  # Considers parent exhibition enabled status
    accepting_triggers: bool  # Gate for fast-lane API triggers
    protection_config: dict | None = None  # Time slice protection configuration
    timeslice_enabled: bool = False  # Enable time slice protection feature
    schedules_enabled: bool = False  # Enable schedules feature
    devices: List[DeviceState]

    class Config:
        from_attributes = True


class SatelliteInfo(BaseModel):
    """Satellite info for exhibition state."""

    id: str
    name: str
    is_connected: bool


class ExhibitionState(BaseModel):
    """Exhibition state with artworks and devices."""

    id: str
    name: str
    enabled: bool
    effective_enabled: bool  # For exhibitions, same as enabled
    schedules_enabled: bool = False  # Enable schedules feature
    satellite: SatelliteInfo | None = None  # Assigned satellite info
    artworks: List[ArtworkState]

    class Config:
        from_attributes = True


def _get_poll_status(request: Request, device_id: str) -> dict | None:
    """Get poll status for a device if state_monitor is available."""
    state_monitor = getattr(request.app.state, "state_monitor", None)
    if state_monitor:
        return state_monitor.get_device_poll_status(device_id)
    return None


async def _get_lamp_hours_map(session) -> dict[UUID, int]:
    """Get latest lamp hours for all assets, keyed by asset_id."""
    from sqlalchemy import func

    # Subquery to get the latest timestamp per asset
    latest_subq = (
        select(
            LampHoursLog.asset_id,
            func.max(LampHoursLog.timestamp).label("max_ts")
        )
        .group_by(LampHoursLog.asset_id)
        .subquery()
    )

    # Join to get the actual lamp_hours value for the latest timestamp
    stmt = (
        select(LampHoursLog.asset_id, LampHoursLog.lamp_hours)
        .join(
            latest_subq,
            (LampHoursLog.asset_id == latest_subq.c.asset_id) &
            (LampHoursLog.timestamp == latest_subq.c.max_ts)
        )
    )
    result = await session.execute(stmt)
    return {row.asset_id: row.lamp_hours for row in result}


def _build_device_state(
    device,
    request: Request,
    effective_enabled: bool,
    lamp_hours: int | None = None,
) -> dict:
    """Build device state dictionary.

    Args:
        device: Device model instance
        request: FastAPI request for poll status
        effective_enabled: Computed enabled state considering parent chain
        lamp_hours: Optional lamp hours from asset

    Returns:
        Device state dictionary matching DeviceState schema
    """
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
        "schedules_enabled": device.schedules_enabled,
        "last_checked_at": device.last_checked_at.isoformat() if device.last_checked_at else None,
        "next_check_allowed_at": device.next_check_allowed_at.isoformat() if device.next_check_allowed_at else None,
        "poll_status": _get_poll_status(request, str(device.id)),
        "actions": _get_shell_actions(device),
        "config": device.config,
        "resolved": device.resolved,
        "asset_id": str(device.asset_id) if device.asset_id else None,
        "lamp_hours": lamp_hours,
    }


def _get_satellite_info(exhibition, satellite_manager) -> dict | None:
    """Build satellite info for an exhibition if one is assigned."""
    if not exhibition.satellite_id or not exhibition.satellite:
        return None

    is_connected = False
    if satellite_manager:
        is_connected = satellite_manager.is_connected(exhibition.satellite_id)

    return {
        "id": str(exhibition.satellite.id),
        "name": exhibition.satellite.name,
        "is_connected": is_connected,
    }


@router.get("/exhibitions", response_model=List[ExhibitionState])
async def list_all_exhibitions(request: Request, session=Depends(get_session)):
    """List all exhibitions with full state tree."""
    try:
        stmt = (
            select(Exhibition)
            .options(
                selectinload(Exhibition.artworks).selectinload(Artwork.devices),
                selectinload(Exhibition.satellite),
            )
            .order_by(Exhibition.name)
        )
        result = await session.execute(stmt)
        exhibitions = result.scalars().all()

        # Get lamp hours for all assets in one query
        lamp_hours_map = await _get_lamp_hours_map(session)

        # Get protection service for config lookup
        protection_service = getattr(request.app.state, "protection_service", None)

        # Get satellite manager for connection status
        satellite_manager = getattr(request.app.state, "satellite_manager", None)

        def get_protection_config(artwork_id, db_config):
            """Get protection config from service (YAML files) or fall back to DB."""
            if protection_service:
                config = protection_service.get_config(artwork_id)
                if config:
                    return config
            return db_config

        return [
            {
                "id": str(ex.id),
                "name": ex.name,
                "enabled": ex.enabled,
                "effective_enabled": ex.enabled,
                "schedules_enabled": ex.schedules_enabled,
                "satellite": _get_satellite_info(ex, satellite_manager),
                "artworks": [
                    {
                        "id": str(aw.id),
                        "name": aw.name,
                        "enabled": aw.enabled,
                        "effective_enabled": aw.enabled and ex.enabled,
                        "accepting_triggers": aw.accepting_triggers,
                        "protection_config": get_protection_config(aw.id, aw.protection_config),
                        "timeslice_enabled": aw.timeslice_enabled,
                        "schedules_enabled": aw.schedules_enabled,
                        "devices": [
                            _build_device_state(
                                dev,
                                request,
                                dev.enabled and aw.enabled and ex.enabled,
                                lamp_hours_map.get(dev.asset_id) if dev.asset_id else None,
                            )
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
                selectinload(Exhibition.artworks).selectinload(Artwork.devices),
                selectinload(Exhibition.satellite),
            )
        )
        result = await session.execute(stmt)
        exhibition = result.scalar_one_or_none()

        if not exhibition:
            raise HTTPException(status_code=404, detail="Exhibition not found")

        # Get protection service for config lookup
        protection_service = getattr(request.app.state, "protection_service", None)

        # Get satellite manager for connection status
        satellite_manager = getattr(request.app.state, "satellite_manager", None)

        def get_protection_config(artwork_id, db_config):
            """Get protection config from service (YAML files) or fall back to DB."""
            if protection_service:
                config = protection_service.get_config(artwork_id)
                if config:
                    return config
            return db_config

        return {
            "id": str(exhibition.id),
            "name": exhibition.name,
            "enabled": exhibition.enabled,
            "effective_enabled": exhibition.enabled,
            "schedules_enabled": exhibition.schedules_enabled,
            "satellite": _get_satellite_info(exhibition, satellite_manager),
            "artworks": [
                {
                    "id": str(aw.id),
                    "name": aw.name,
                    "enabled": aw.enabled,
                    "effective_enabled": aw.enabled and exhibition.enabled,
                    "accepting_triggers": aw.accepting_triggers,
                    "protection_config": get_protection_config(aw.id, aw.protection_config),
                    "timeslice_enabled": aw.timeslice_enabled,
                    "schedules_enabled": aw.schedules_enabled,
                    "devices": [
                        _build_device_state(
                            dev,
                            request,
                            dev.enabled and aw.enabled and exhibition.enabled,
                        )
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

        return _build_device_state(device, request, effective_enabled)

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


@router.get("/stream")
async def stream_poll_events(request: Request):
    """SSE endpoint for real-time poll status updates.

    Streams events for:
    - poll_complete: When a device poll finishes
    - config_change: When monitoring config changes
    - verification_start/end: When device enters/exits fast polling
    - heartbeat: Periodic keepalive

    Frontend can use EventSource to subscribe:
        const es = new EventSource('/api/state/stream');
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    sse_broadcaster = getattr(request.app.state, "sse_broadcaster", None)
    if not sse_broadcaster:
        raise HTTPException(
            status_code=503,
            detail="SSE broadcaster not initialized"
        )

    async def event_generator():
        # Send initial connection event with current config
        config = get_config()
        monitoring_config = {
            "poll_interval_seconds": config.get("monitoring.poll_interval_seconds", 60),
            "fast_poll_interval_seconds": config.get("monitoring.fast_poll_interval_seconds", 30),
            "batch_size": config.get("monitoring.batch_size", 30),
            "device_timeout_seconds": config.get("monitoring.device_timeout_seconds", 5),
        }
        yield await sse_broadcaster.send_initial_state(monitoring_config)

        # Stream events from broadcaster
        async for event in sse_broadcaster.subscribe():
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/changes")
async def list_state_changes(
    device_id: str | None = None,
    artwork_id: str | None = None,
    exhibition_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    new_state: int | None = None,
    limit: int = 100,
    offset: int = 0,
    session=Depends(get_session),
):
    """List device state changes with optional filters.

    Query parameters:
    - device_id: Filter by specific device
    - artwork_id: Filter by artwork (all devices in artwork)
    - exhibition_id: Filter by exhibition (all devices in exhibition)
    - from_date: Filter changes after this date (ISO format)
    - to_date: Filter changes before this date (ISO format)
    - new_state: Filter by new state value (-1=error, 0=off, 1=on, 2=cooling, 3=warming)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    from datetime import datetime

    from mutech_control.database.models import StateChangeLog

    try:
        stmt = (
            select(StateChangeLog, Device.name.label("device_name"), Device.device_type.label("device_type"))
            .join(Device, StateChangeLog.device_id == Device.id)
            .join(Artwork, Device.artwork_id == Artwork.id)
            .order_by(StateChangeLog.timestamp.desc())
        )

        # Apply filters
        if device_id:
            stmt = stmt.where(StateChangeLog.device_id == UUID(device_id))

        if artwork_id:
            stmt = stmt.where(Device.artwork_id == UUID(artwork_id))

        if exhibition_id:
            stmt = stmt.where(Artwork.exhibition_id == UUID(exhibition_id))

        if from_date:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            # Strip timezone info to match naive datetimes in database
            if from_dt.tzinfo is not None:
                from_dt = from_dt.replace(tzinfo=None)
            stmt = stmt.where(StateChangeLog.timestamp >= from_dt)

        if to_date:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            # Strip timezone info to match naive datetimes in database
            if to_dt.tzinfo is not None:
                to_dt = to_dt.replace(tzinfo=None)
            stmt = stmt.where(StateChangeLog.timestamp <= to_dt)

        if new_state is not None:
            stmt = stmt.where(StateChangeLog.new_state == new_state)

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(row[0].id),
                "device_id": str(row[0].device_id),
                "device_name": row[1],
                "device_type": row[2],
                "previous_state": row[0].previous_state,
                "previous_state_name": state_to_name(row[0].previous_state),
                "new_state": row[0].new_state,
                "new_state_name": state_to_name(row[0].new_state),
                "trigger": row[0].trigger,
                "timestamp": row[0].timestamp.isoformat(),
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error listing state changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/changes/export")
async def export_state_changes(
    device_id: str | None = None,
    artwork_id: str | None = None,
    exhibition_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    session=Depends(get_session),
):
    """Export state changes as CSV.

    Same filters as /changes endpoint but returns CSV format.
    """
    from datetime import datetime
    from io import StringIO

    from fastapi.responses import StreamingResponse

    from mutech_control.database.models import StateChangeLog

    try:
        stmt = (
            select(StateChangeLog, Device.name.label("device_name"))
            .join(Device, StateChangeLog.device_id == Device.id)
            .join(Artwork, Device.artwork_id == Artwork.id)
            .order_by(StateChangeLog.timestamp.desc())
        )

        # Apply filters
        if device_id:
            stmt = stmt.where(StateChangeLog.device_id == UUID(device_id))

        if artwork_id:
            stmt = stmt.where(Device.artwork_id == UUID(artwork_id))

        if exhibition_id:
            stmt = stmt.where(Artwork.exhibition_id == UUID(exhibition_id))

        if from_date:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            # Strip timezone info to match naive datetimes in database
            if from_dt.tzinfo is not None:
                from_dt = from_dt.replace(tzinfo=None)
            stmt = stmt.where(StateChangeLog.timestamp >= from_dt)

        if to_date:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            # Strip timezone info to match naive datetimes in database
            if to_dt.tzinfo is not None:
                to_dt = to_dt.replace(tzinfo=None)
            stmt = stmt.where(StateChangeLog.timestamp <= to_dt)

        result = await session.execute(stmt)
        rows = result.all()

        # Build CSV
        output = StringIO()
        output.write("timestamp,device_id,device_name,previous_state,new_state,trigger\n")

        for row in rows:
            change = row[0]
            device_name = row[1]
            output.write(
                f"{change.timestamp.isoformat()},"
                f"{change.device_id},"
                f"\"{device_name}\","
                f"{state_to_name(change.previous_state)},"
                f"{state_to_name(change.new_state)},"
                f"{change.trigger}\n"
            )

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=state_changes.csv"},
        )

    except Exception as e:
        logger.error(f"Error exporting state changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Service Health ==========


class ServiceHealthResponse(BaseModel):
    """Response model for service health."""
    service_id: str
    name: str
    description: str
    status: str
    last_check: str | None
    last_seen: str | None
    error: str | None
    response_time_ms: int | None
    affects_device_types: list[str]
    consecutive_failures: int


@router.get("/services", response_model=list[ServiceHealthResponse])
async def get_services_health(request: Request):
    """Get health status of all external services/runners.

    Returns status of services that the backend depends on (e.g., ANEL runner).
    Use this to show users when a service is down instead of individual device errors.
    """
    try:
        service_monitor = getattr(request.app.state, "service_monitor", None)
        if not service_monitor:
            return []

        services = service_monitor.get_all_services()
        return [service.to_dict() for service in services.values()]

    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{service_id}", response_model=ServiceHealthResponse)
async def get_service_health(request: Request, service_id: str):
    """Get health status of a specific service."""
    try:
        service_monitor = getattr(request.app.state, "service_monitor", None)
        if not service_monitor:
            raise HTTPException(status_code=404, detail="Service monitor not available")

        service = service_monitor.get_service_health(service_id)
        if not service:
            raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

        return service.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_id}/check")
async def check_service_now(request: Request, service_id: str):
    """Trigger immediate health check for a service."""
    try:
        service_monitor = getattr(request.app.state, "service_monitor", None)
        if not service_monitor:
            raise HTTPException(status_code=404, detail="Service monitor not available")

        service = await service_monitor.check_now(service_id)
        if not service:
            raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

        return service.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Artwork Protection ==========


@router.get("/artworks/{artwork_id}/protection-status")
async def get_protection_status(request: Request, artwork_id: str, session=Depends(get_session)):
    """Get protection status for an artwork.

    Returns the protection configuration and current state including:
    - accepting_triggers: Whether artwork accepts fast-lane API triggers
    - Whether protection is enabled
    - Current runtime if running
    - Cooldown status
    - Time slice budget usage and remaining
    - Whether artwork can start

    Returns {"protected": false} if artwork has no protection config.
    """
    try:
        # Get artwork to include accepting_triggers
        stmt = select(Artwork).where(Artwork.id == UUID(artwork_id))
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

        protection_service = getattr(request.app.state, "protection_service", None)
        if not protection_service:
            return {
                "accepting_triggers": artwork.accepting_triggers,
                "protected": False,
                "message": "Protection service not initialized",
            }

        status = await protection_service.get_protection_status(UUID(artwork_id))
        # Add accepting_triggers to response
        status["accepting_triggers"] = artwork.accepting_triggers
        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting protection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
