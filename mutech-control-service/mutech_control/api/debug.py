# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Debug API endpoints for viewing operation logs and debug data."""

import logging
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from mutech_control.database.connection import get_session
from mutech_control.database.models import (
    Artwork,
    Device,
    DeviceOperationLog,
    StateChangeLog,
)
from mutech_control.database.operation_logger import cleanup_old_operation_logs
from mutech_control.devices.base import STATE_NAMES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])


# Response models
class OperationLogEntry(BaseModel):
    """Operation log entry without raw data."""

    id: str
    device_id: str
    device_name: str | None
    device_type: str | None
    operation_type: str
    source: str
    success: bool
    state_before: int | None
    state_after: int | None
    error_message: str | None
    duration_ms: int | None
    timestamp: str
    has_raw_response: bool


class OperationLogDetail(OperationLogEntry):
    """Operation log entry with raw request/response data."""

    raw_request: str | None
    raw_response: str | None


class DeviceErrorSummary(BaseModel):
    """Device error summary."""

    device_id: str
    device_name: str
    device_type: str
    error_count: int


class RecentError(BaseModel):
    """Recent error entry."""

    device_name: str
    device_type: str
    operation_type: str
    error_message: str | None
    timestamp: str


class DebugSummary(BaseModel):
    """Debug summary for dashboard."""

    total_operations_24h: int
    successful_operations: int
    failed_operations: int
    errors_by_device: List[DeviceErrorSummary]
    recent_errors: List[RecentError]


class TimelineEntry(BaseModel):
    """Timeline entry for unified view."""

    type: str  # 'operation' or 'state_change'
    id: str
    device_id: str
    device_name: str
    device_type: str
    artwork_name: str | None = None
    timestamp: str
    # Operation fields
    operation_type: str | None = None
    source: str | None = None
    success: bool | None = None
    state_before: int | None = None
    state_after: int | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    # State change fields
    previous_state: int | None = None
    new_state: int | None = None
    trigger: str | None = None


class CleanupResult(BaseModel):
    """Cleanup operation result."""

    success: bool
    deleted_count: int
    retention_hours: int
    cutoff_time: str




@router.get("/summary", response_model=DebugSummary)
async def get_debug_summary(session=Depends(get_session)):
    """Get debug summary for last 24 hours.

    Returns:
    - Total operations count
    - Successful vs failed operations
    - Top 10 devices with most errors
    - Last 10 errors
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)

    try:
        # Total operations in last 24h
        total_stmt = select(func.count(DeviceOperationLog.id)).where(
            DeviceOperationLog.timestamp >= cutoff
        )
        total = (await session.execute(total_stmt)).scalar() or 0

        # Successful operations
        success_stmt = select(func.count(DeviceOperationLog.id)).where(
            DeviceOperationLog.timestamp >= cutoff,
            DeviceOperationLog.success == True,  # noqa: E712
        )
        successful = (await session.execute(success_stmt)).scalar() or 0

        # Errors by device (top 10)
        errors_stmt = (
            select(
                Device.id,
                Device.name,
                Device.device_type,
                func.count(DeviceOperationLog.id).label("error_count"),
            )
            .join(Device, DeviceOperationLog.device_id == Device.id)
            .where(
                DeviceOperationLog.timestamp >= cutoff,
                DeviceOperationLog.success == False,  # noqa: E712
            )
            .group_by(Device.id, Device.name, Device.device_type)
            .order_by(func.count(DeviceOperationLog.id).desc())
            .limit(10)
        )
        errors_result = await session.execute(errors_stmt)
        errors_by_device = [
            DeviceErrorSummary(
                device_id=str(row.id),
                device_name=row.name,
                device_type=row.device_type,
                error_count=row.error_count,
            )
            for row in errors_result
        ]

        # Recent errors (last 10)
        recent_stmt = (
            select(
                DeviceOperationLog.operation_type,
                DeviceOperationLog.error_message,
                DeviceOperationLog.timestamp,
                Device.name,
                Device.device_type,
            )
            .join(Device, DeviceOperationLog.device_id == Device.id)
            .where(DeviceOperationLog.success == False)  # noqa: E712
            .order_by(DeviceOperationLog.timestamp.desc())
            .limit(10)
        )
        recent_result = await session.execute(recent_stmt)
        recent_errors = [
            RecentError(
                device_name=row.name,
                device_type=row.device_type,
                operation_type=row.operation_type,
                error_message=row.error_message,
                timestamp=row.timestamp.isoformat(),
            )
            for row in recent_result
        ]

        return DebugSummary(
            total_operations_24h=total,
            successful_operations=successful,
            failed_operations=total - successful,
            errors_by_device=errors_by_device,
            recent_errors=recent_errors,
        )

    except Exception as e:
        logger.error(f"Error getting debug summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations", response_model=List[OperationLogEntry])
async def list_operations(
    device_id: str | None = None,
    exhibition_id: str | None = None,
    operation_type: str | None = None,
    success: bool | None = None,
    hours: int = Query(default=24, le=168),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    session=Depends(get_session),
):
    """List operation logs with filters.

    Query parameters:
    - device_id: Filter by specific device
    - exhibition_id: Filter by exhibition (all devices in exhibition)
    - operation_type: Filter by operation type (state_query, power_on, power_off, action)
    - success: Filter by success status (true/false)
    - hours: Time window in hours (default 24, max 168 = 7 days)
    - limit: Max results (default 100, max 500)
    - offset: Pagination offset
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    try:
        stmt = (
            select(
                DeviceOperationLog,
                Device.name.label("device_name"),
                Device.device_type,
            )
            .join(Device, DeviceOperationLog.device_id == Device.id)
            .where(DeviceOperationLog.timestamp >= cutoff)
            .order_by(DeviceOperationLog.timestamp.desc())
        )

        if device_id:
            stmt = stmt.where(DeviceOperationLog.device_id == UUID(device_id))

        if exhibition_id:
            stmt = stmt.join(Artwork, Device.artwork_id == Artwork.id).where(
                Artwork.exhibition_id == UUID(exhibition_id)
            )

        if operation_type:
            stmt = stmt.where(DeviceOperationLog.operation_type == operation_type)

        if success is not None:
            stmt = stmt.where(DeviceOperationLog.success == success)

        stmt = stmt.offset(offset).limit(limit)

        result = await session.execute(stmt)

        return [
            OperationLogEntry(
                id=str(row[0].id),
                device_id=str(row[0].device_id),
                device_name=row.device_name,
                device_type=row.device_type,
                operation_type=row[0].operation_type,
                source=row[0].source,
                success=row[0].success,
                state_before=row[0].state_before,
                state_after=row[0].state_after,
                error_message=row[0].error_message,
                duration_ms=row[0].duration_ms,
                timestamp=row[0].timestamp.isoformat(),
                has_raw_response=row[0].raw_response is not None,
            )
            for row in result
        ]

    except Exception as e:
        logger.error(f"Error listing operations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/{operation_id}", response_model=OperationLogDetail)
async def get_operation_detail(operation_id: str, session=Depends(get_session)):
    """Get full operation details including raw request/response."""
    try:
        stmt = (
            select(
                DeviceOperationLog,
                Device.name.label("device_name"),
                Device.device_type,
            )
            .join(Device, DeviceOperationLog.device_id == Device.id)
            .where(DeviceOperationLog.id == UUID(operation_id))
        )

        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Operation log not found")

        return OperationLogDetail(
            id=str(row[0].id),
            device_id=str(row[0].device_id),
            device_name=row.device_name,
            device_type=row.device_type,
            operation_type=row[0].operation_type,
            source=row[0].source,
            success=row[0].success,
            state_before=row[0].state_before,
            state_after=row[0].state_after,
            error_message=row[0].error_message,
            duration_ms=row[0].duration_ms,
            timestamp=row[0].timestamp.isoformat(),
            has_raw_response=row[0].raw_response is not None,
            raw_request=row[0].raw_request,
            raw_response=row[0].raw_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline", response_model=List[TimelineEntry])
async def get_debug_timeline(
    device_id: str | None = None,
    exhibition_id: str | None = None,
    hours: int = Query(default=24, le=168),
    limit: int = Query(default=100, le=500),
    session=Depends(get_session),
):
    """Get unified timeline of operations and state changes.

    Combines operation logs and state change logs into a single
    chronological timeline for comprehensive debugging.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    try:
        # Query operation logs
        # Join Device/Artwork for device_name and artwork_name (fallback for older records)
        ops_stmt = (
            select(
                DeviceOperationLog.id,
                DeviceOperationLog.device_id,
                DeviceOperationLog.exhibition_id,  # Stored exhibition for filtering
                DeviceOperationLog.operation_type,
                DeviceOperationLog.source,
                DeviceOperationLog.success,
                DeviceOperationLog.state_before,
                DeviceOperationLog.state_after,
                DeviceOperationLog.error_message,
                DeviceOperationLog.duration_ms,
                DeviceOperationLog.timestamp,
                Device.name.label("device_name"),
                Device.device_type,
                Artwork.name.label("artwork_name"),
            )
            .join(Device, DeviceOperationLog.device_id == Device.id)
            .join(Artwork, Device.artwork_id == Artwork.id)
            .where(DeviceOperationLog.timestamp >= cutoff)
        )

        # Query state changes
        changes_stmt = (
            select(
                StateChangeLog.id,
                StateChangeLog.device_id,
                StateChangeLog.exhibition_id,  # Stored exhibition for filtering
                StateChangeLog.previous_state,
                StateChangeLog.new_state,
                StateChangeLog.trigger,
                StateChangeLog.timestamp,
                Device.name.label("device_name"),
                Device.device_type,
                Artwork.name.label("artwork_name"),
            )
            .join(Device, StateChangeLog.device_id == Device.id)
            .join(Artwork, Device.artwork_id == Artwork.id)
            .where(StateChangeLog.timestamp >= cutoff)
        )

        # Apply filters with UUID validation
        if device_id:
            try:
                device_uuid = UUID(device_id)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid device_id UUID: {device_id}")
            ops_stmt = ops_stmt.where(DeviceOperationLog.device_id == device_uuid)
            changes_stmt = changes_stmt.where(StateChangeLog.device_id == device_uuid)

        if exhibition_id:
            try:
                exhibition_uuid = UUID(exhibition_id)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid exhibition_id UUID: {exhibition_id}")
            # Use stored exhibition_id (denormalized) for accurate historical filtering
            # Fall back to current device's exhibition for older records without stored value
            from sqlalchemy import or_
            ops_stmt = ops_stmt.where(
                or_(
                    DeviceOperationLog.exhibition_id == exhibition_uuid,
                    # Fallback: if no stored exhibition_id, use current device assignment
                    (DeviceOperationLog.exhibition_id.is_(None)) & (Artwork.exhibition_id == exhibition_uuid)
                )
            )
            changes_stmt = changes_stmt.where(
                or_(
                    StateChangeLog.exhibition_id == exhibition_uuid,
                    (StateChangeLog.exhibition_id.is_(None)) & (Artwork.exhibition_id == exhibition_uuid)
                )
            )

        # Order by timestamp DESC - limit applied AFTER merging to ensure fair representation
        ops_stmt = ops_stmt.order_by(DeviceOperationLog.timestamp.desc())
        changes_stmt = changes_stmt.order_by(StateChangeLog.timestamp.desc())

        # Use higher internal limit to get fair representation from all exhibitions
        # Final limit is applied after merging and sorting
        internal_limit = max(limit * 5, 1000)  # Fetch enough to represent all exhibitions
        ops_result = await session.execute(ops_stmt.limit(internal_limit))
        changes_result = await session.execute(changes_stmt.limit(internal_limit))

        # Build timeline entries
        timeline = []

        for row in ops_result:
            timeline.append(
                TimelineEntry(
                    type="operation",
                    id=str(row.id),
                    device_id=str(row.device_id),
                    device_name=row.device_name,
                    device_type=row.device_type,
                    artwork_name=row.artwork_name,
                    operation_type=row.operation_type,
                    source=row.source,
                    success=row.success,
                    state_before=row.state_before,
                    state_after=row.state_after,
                    error_message=row.error_message,
                    duration_ms=row.duration_ms,
                    timestamp=row.timestamp.isoformat(),
                )
            )

        for row in changes_result:
            timeline.append(
                TimelineEntry(
                    type="state_change",
                    id=str(row.id),
                    device_id=str(row.device_id),
                    device_name=row.device_name,
                    device_type=row.device_type,
                    artwork_name=row.artwork_name,
                    previous_state=row.previous_state,
                    new_state=row.new_state,
                    trigger=row.trigger,
                    timestamp=row.timestamp.isoformat(),
                )
            )

        # Sort by timestamp descending
        timeline.sort(key=lambda x: x.timestamp, reverse=True)

        return timeline[:limit]

    except Exception as e:
        logger.error(f"Error getting debug timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup_old_logs(
    request: Request,
    retention_hours: int = Query(default=24, le=168),
):
    """Delete operation logs older than retention period.

    This is a manual cleanup endpoint. Automatic cleanup runs hourly
    via the state monitor.

    Args:
        retention_hours: Hours of logs to keep (default 24, max 168 = 7 days)
    """
    db_manager = request.app.state.db_manager

    try:
        deleted_count = await cleanup_old_operation_logs(db_manager, retention_hours)
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)

        return CleanupResult(
            success=True,
            deleted_count=deleted_count,
            retention_hours=retention_hours,
            cutoff_time=cutoff.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeviceInfoResponse(BaseModel):
    """Device information response - fields vary by device type."""

    device_id: str
    device_name: str
    device_type: str
    host: str
    info: dict  # Raw info from device
    error: str | None = None
    cached_at: str | None = None  # ISO timestamp when cache was last updated
    is_stale: bool = False  # True if data is from stale cache (live fetch failed)


@router.get("/device/{device_id}/info", response_model=DeviceInfoResponse)
async def get_device_info(
    device_id: str,
    request: Request,
    session=Depends(get_session),
):
    """Get detailed device information.

    Returns cached device info if available and fresh (< 24 hours).
    Falls back to live query on cache miss or stale cache.
    If live query fails, returns stale cached data with is_stale=True.

    Supported device types: pjlink, netio, anel
    """
    from mutech_control.services.device_cache import extract_core_info, update_device_cache

    try:
        device_uuid = UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid device_id UUID: {device_id}")

    # Get device from database
    result = await session.execute(
        select(Device).where(Device.id == device_uuid)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    supported_types = ["pjlink", "netio", "anel"]
    if device.device_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"Device info not available for {device.device_type}. Supported: {supported_types}"
        )

    # Check cache freshness
    now = datetime.utcnow()
    has_cache = device.cached_info is not None
    # 24 hour TTL for static metadata
    is_fresh = has_cache and device.cached_info_at and (now - device.cached_info_at).total_seconds() < 86400

    # Fresh cache: return directly
    if is_fresh:
        return DeviceInfoResponse(
            device_id=str(device.id),
            device_name=device.name,
            device_type=device.device_type,
            host=device.host,
            info=device.cached_info,
            cached_at=device.cached_info_at.isoformat() if device.cached_info_at else None,
            is_stale=False,
        )

    # Get the appropriate manager from app state
    orchestrator = request.app.state.orchestrator
    manager = orchestrator.device_managers.get(device.device_type)

    if not manager:
        raise HTTPException(status_code=500, detail=f"{device.device_type} manager not available")

    # Check if manager supports get_device_info
    if not hasattr(manager, 'get_device_info'):
        raise HTTPException(status_code=500, detail=f"{device.device_type} manager does not support device info")

    # Cache miss or stale: attempt live fetch
    try:
        info = await manager.get_device_info(device)

        # Check for error in response
        if info.get("error"):
            # Live fetch returned error - fall back to stale cache if available
            if has_cache:
                return DeviceInfoResponse(
                    device_id=str(device.id),
                    device_name=device.name,
                    device_type=device.device_type,
                    host=device.host,
                    info=device.cached_info,
                    cached_at=device.cached_info_at.isoformat() if device.cached_info_at else None,
                    is_stale=True,
                    error=info.get("error"),
                )
            # No cache - return error
            return DeviceInfoResponse(
                device_id=str(device.id),
                device_name=device.name,
                device_type=device.device_type,
                host=device.host,
                info={},
                error=info.get("error"),
            )

        # Extract core info for cache and update database
        core_info = extract_core_info(info, device.device_type)
        if core_info:
            await update_device_cache(session, device.id, core_info, now)
            await session.commit()

        return DeviceInfoResponse(
            device_id=str(device.id),
            device_name=device.name,
            device_type=device.device_type,
            host=device.host,
            info=info,
            cached_at=now.isoformat(),
            is_stale=False,
        )

    except Exception as e:
        # Live fetch failed - fall back to stale cache or return error
        logger.warning(f"Live device info fetch failed for {device.name}: {e}")

        if has_cache:
            return DeviceInfoResponse(
                device_id=str(device.id),
                device_name=device.name,
                device_type=device.device_type,
                host=device.host,
                info=device.cached_info,
                cached_at=device.cached_info_at.isoformat() if device.cached_info_at else None,
                is_stale=True,
            )

        # No cache - return 200 with error field (backward compatible)
        return DeviceInfoResponse(
            device_id=str(device.id),
            device_name=device.name,
            device_type=device.device_type,
            host=device.host,
            info={},
            error=f"Device unreachable: {e}",
        )


@router.get("/devices/info", response_model=List[DeviceInfoResponse])
async def get_all_device_info(
    request: Request,
    device_type: str | None = Query(default=None, description="Filter by device type (pjlink, netio, anel)"),
    session=Depends(get_session),
):
    """Get device information for all devices that support it.

    Queries all enabled devices of supported types (pjlink, netio, anel).
    This can take a while if there are many devices.

    Args:
        device_type: Optional filter by device type
    """
    supported_types = ["pjlink", "netio", "anel"]

    if device_type and device_type not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported device type: {device_type}. Supported: {supported_types}"
        )

    # Build query
    query = select(Device).where(Device.enabled == True)
    if device_type:
        query = query.where(Device.device_type == device_type)
    else:
        query = query.where(Device.device_type.in_(supported_types))

    result = await session.execute(query)
    devices = result.scalars().all()

    if not devices:
        return []

    orchestrator = request.app.state.orchestrator

    # Query info for each device
    responses = []
    for device in devices:
        manager = orchestrator.device_managers.get(device.device_type)
        if not manager or not hasattr(manager, 'get_device_info'):
            continue

        try:
            info = await manager.get_device_info(device)
            responses.append(DeviceInfoResponse(
                device_id=str(device.id),
                device_name=device.name,
                device_type=device.device_type,
                host=device.host,
                info=info,
                error=info.get("error"),
            ))
        except Exception as e:
            responses.append(DeviceInfoResponse(
                device_id=str(device.id),
                device_name=device.name,
                device_type=device.device_type,
                host=device.host,
                info={},
                error=str(e),
            ))

    return responses
