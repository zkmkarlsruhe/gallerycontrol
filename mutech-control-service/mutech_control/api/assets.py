# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Asset API endpoints for projector lamp hours tracking."""

import logging
from io import StringIO
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, desc
from sqlalchemy.orm import selectinload, aliased

from mutech_control.database.connection import get_session
from mutech_control.database.models import Asset, Artwork, Device, Exhibition, LampHoursLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])

# UUID regex pattern for path validation - ensures {asset_id} only matches UUIDs
UUID_PATTERN = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def parse_uuid(value: str, name: str = "id") -> UUID:
    """Parse a UUID string, raising HTTPException 400 if invalid."""
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name}: '{value}' is not a valid UUID"
        )


# Pydantic models
class AssetResponse(BaseModel):
    """Asset response model."""
    id: str
    asset_number: str
    hostname: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str
    current_device_id: Optional[str] = None
    current_device_name: Optional[str] = None
    last_lamp_hours: Optional[int] = None
    last_event_type: Optional[str] = None
    last_event_at: Optional[str] = None


class AssetUpdate(BaseModel):
    """Asset update model."""
    hostname: Optional[str] = None
    notes: Optional[str] = None


class LampHoursLogResponse(BaseModel):
    """Lamp hours log response model."""
    id: str
    asset_id: str
    device_id: Optional[str]
    lamp_hours: int
    event_type: str
    exhibition_name: Optional[str]
    artwork_name: Optional[str]
    device_name: Optional[str]
    timestamp: str


class ManualLampHoursRequest(BaseModel):
    """Request model for manual lamp hours entry."""
    lamp_hours: int
    device_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("/exhibitions")
async def list_exhibitions_for_filter(session=Depends(get_session)):
    """Get exhibition list for asset filter dropdown.

    Returns exhibitions that have at least one device with an asset.
    """
    try:
        stmt = (
            select(Exhibition.id, Exhibition.name)
            .join(Artwork, Artwork.exhibition_id == Exhibition.id)
            .join(Device, Device.artwork_id == Artwork.id)
            .where(Device.asset_id.isnot(None))
            .distinct()
            .order_by(Exhibition.name)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {"id": str(row.id), "name": row.name}
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error listing exhibitions for filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_assets(
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None,
    exhibition_id: Optional[str] = None,
    session=Depends(get_session),
):
    """List all assets with pagination and optional search.

    Args:
        page: Page number (default 1)
        per_page: Items per page (default 50, max 100)
        search: Optional search term for asset_number or hostname
        exhibition_id: Optional filter by exhibition UUID
    """
    try:
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page

        # Build search filter
        search_filter = None
        if search:
            search_term = f"%{search}%"
            search_filter = (
                (Asset.asset_number.ilike(search_term)) |
                (Asset.hostname.ilike(search_term))
            )

        # Parse exhibition_id filter
        exhibition_uuid = None
        if exhibition_id:
            exhibition_uuid = parse_uuid(exhibition_id, "exhibition_id")

        # Get total count (needs join for exhibition filter)
        if exhibition_uuid:
            count_stmt = (
                select(func.count(func.distinct(Asset.id)))
                .select_from(Asset)
                .join(Device, Device.asset_id == Asset.id)
                .join(Artwork, Device.artwork_id == Artwork.id)
                .where(Artwork.exhibition_id == exhibition_uuid)
            )
        else:
            count_stmt = select(func.count()).select_from(Asset)

        if search_filter is not None:
            count_stmt = count_stmt.where(search_filter)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar()

        # Subquery to get the latest lamp log timestamp per asset
        latest_log_subq = (
            select(
                LampHoursLog.asset_id,
                func.max(LampHoursLog.timestamp).label("max_timestamp")
            )
            .group_by(LampHoursLog.asset_id)
            .subquery()
        )

        # Alias for joining lamp logs
        LatestLog = aliased(LampHoursLog)

        # Main query: Asset + current device + artwork/exhibition + latest lamp log
        stmt = (
            select(
                Asset,
                Device.id.label("device_id"),
                Device.name.label("device_name"),
                Device.state.label("device_state"),
                Artwork.name.label("artwork_name"),
                Exhibition.name.label("exhibition_name"),
                LatestLog.lamp_hours.label("last_lamp_hours"),
                LatestLog.event_type.label("last_event_type"),
                LatestLog.timestamp.label("last_event_at"),
            )
            .outerjoin(Device, Device.asset_id == Asset.id)
            .outerjoin(Artwork, Device.artwork_id == Artwork.id)
            .outerjoin(Exhibition, Artwork.exhibition_id == Exhibition.id)
            .outerjoin(
                latest_log_subq,
                latest_log_subq.c.asset_id == Asset.id
            )
            .outerjoin(
                LatestLog,
                (LatestLog.asset_id == Asset.id) &
                (LatestLog.timestamp == latest_log_subq.c.max_timestamp)
            )
            .order_by(Asset.asset_number)
        )

        # Apply search filter
        if search_filter is not None:
            stmt = stmt.where(search_filter)

        # Apply exhibition filter
        if exhibition_uuid:
            stmt = stmt.where(Exhibition.id == exhibition_uuid)

        # Apply pagination
        stmt = stmt.offset(offset).limit(per_page)
        result = await session.execute(stmt)
        rows = result.all()

        # Build response
        asset_list = []
        for row in rows:
            asset = row.Asset
            asset_list.append({
                "id": str(asset.id),
                "asset_number": asset.asset_number,
                "hostname": asset.hostname,
                "notes": asset.notes,
                "created_at": asset.created_at.isoformat(),
                "updated_at": asset.updated_at.isoformat(),
                "current_device_id": str(row.device_id) if row.device_id else None,
                "current_device_name": row.device_name,
                "device_state": row.device_state,
                "artwork_name": row.artwork_name,
                "exhibition_name": row.exhibition_name,
                "last_lamp_hours": row.last_lamp_hours,
                "last_event_type": row.last_event_type,
                "last_event_at": row.last_event_at.isoformat() if row.last_event_at else None,
            })

        return {
            "items": asset_list,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "pages": (total_count + per_page - 1) // per_page,
        }

    except Exception as e:
        logger.error(f"Error listing assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}")
async def get_asset(asset_id: str = Path(pattern=UUID_PATTERN), session=Depends(get_session)):
    """Get asset with recent lamp history."""
    try:
        stmt = (
            select(Asset)
            .where(Asset.id == parse_uuid(asset_id, "asset_id"))
            .options(selectinload(Asset.devices), selectinload(Asset.lamp_history))
        )
        result = await session.execute(stmt)
        asset = result.scalar_one_or_none()

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get current linked device
        current_device = next(
            (d for d in asset.devices if d.asset_id == asset.id),
            None
        )

        # Get recent lamp hours (last 10)
        recent_logs = sorted(
            asset.lamp_history,
            key=lambda l: l.timestamp,
            reverse=True
        )[:10]

        return {
            "id": str(asset.id),
            "asset_number": asset.asset_number,
            "hostname": asset.hostname,
            "notes": asset.notes,
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
            "current_device_id": str(current_device.id) if current_device else None,
            "current_device_name": current_device.name if current_device else None,
            "recent_lamp_history": [
                {
                    "id": str(log.id),
                    "lamp_hours": log.lamp_hours,
                    "event_type": log.event_type,
                    "exhibition_name": log.exhibition_name,
                    "artwork_name": log.artwork_name,
                    "device_name": log.device_name,
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in recent_logs
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/lamp-history")
async def get_lamp_history(
    asset_id: str = Path(pattern=UUID_PATTERN),
    page: int = 1,
    per_page: int = 50,
    event_type: Optional[str] = None,
    session=Depends(get_session),
):
    """Get full lamp history for an asset with pagination.

    Args:
        asset_id: Asset UUID
        page: Page number (default 1)
        per_page: Items per page (default 50, max 100)
        event_type: Optional filter by event type
    """
    try:
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page

        # Base query
        stmt = (
            select(LampHoursLog)
            .where(LampHoursLog.asset_id == parse_uuid(asset_id, "asset_id"))
            .order_by(LampHoursLog.timestamp.desc())
        )

        # Apply event type filter
        if event_type:
            stmt = stmt.where(LampHoursLog.event_type == event_type)

        # Get total count
        count_stmt = select(func.count()).select_from(LampHoursLog).where(
            LampHoursLog.asset_id == parse_uuid(asset_id, "asset_id")
        )
        if event_type:
            count_stmt = count_stmt.where(LampHoursLog.event_type == event_type)
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar()

        # Apply pagination
        stmt = stmt.offset(offset).limit(per_page)
        result = await session.execute(stmt)
        logs = result.scalars().all()

        return {
            "items": [
                {
                    "id": str(log.id),
                    "asset_id": str(log.asset_id),
                    "device_id": str(log.device_id) if log.device_id else None,
                    "lamp_hours": log.lamp_hours,
                    "event_type": log.event_type,
                    "exhibition_name": log.exhibition_name,
                    "artwork_name": log.artwork_name,
                    "device_name": log.device_name,
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in logs
            ],
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "pages": (total_count + per_page - 1) // per_page,
        }

    except Exception as e:
        logger.error(f"Error getting lamp history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/lamp-history/csv")
async def export_lamp_history_csv(
    asset_id: str = Path(pattern=UUID_PATTERN),
    limit: int = 10000,
    session=Depends(get_session),
):
    """Export lamp history as CSV.

    Args:
        asset_id: Asset UUID
        limit: Max rows (default 10000)
    """
    try:
        # Get asset for filename
        asset_stmt = select(Asset).where(Asset.id == parse_uuid(asset_id, "asset_id"))
        asset_result = await session.execute(asset_stmt)
        asset = asset_result.scalar_one_or_none()

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get lamp history
        stmt = (
            select(LampHoursLog)
            .where(LampHoursLog.asset_id == parse_uuid(asset_id, "asset_id"))
            .order_by(LampHoursLog.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

        # Build CSV
        output = StringIO()
        output.write("asset_number,timestamp,lamp_hours,event_type,device_name,artwork_name,exhibition_name\n")

        for log in logs:
            output.write(
                f"\"{asset.asset_number}\","
                f"{log.timestamp.isoformat()},"
                f"{log.lamp_hours},"
                f"{log.event_type},"
                f"\"{log.device_name or ''}\","
                f"\"{log.artwork_name or ''}\","
                f"\"{log.exhibition_name or ''}\"\n"
            )

        output.seek(0)
        filename = f"lamp_history_{asset.asset_number}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting lamp history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lamp-history/csv")
async def export_bulk_lamp_history_csv(
    asset_ids: List[str],
    session=Depends(get_session),
):
    """Export lamp history for multiple assets as CSV.

    Args:
        asset_ids: List of asset UUIDs
    """
    try:
        if not asset_ids:
            raise HTTPException(status_code=400, detail="No asset IDs provided")

        # Parse and validate all UUIDs
        asset_uuids = [parse_uuid(aid, "asset_id") for aid in asset_ids]

        # Get asset numbers for the filename and CSV
        asset_stmt = select(Asset).where(Asset.id.in_(asset_uuids))
        asset_result = await session.execute(asset_stmt)
        assets = {str(a.id): a.asset_number for a in asset_result.scalars().all()}

        if not assets:
            raise HTTPException(status_code=404, detail="No assets found")

        # Get lamp history for all assets
        stmt = (
            select(LampHoursLog)
            .where(LampHoursLog.asset_id.in_(asset_uuids))
            .order_by(LampHoursLog.timestamp.desc())
            .limit(50000)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

        # Build CSV with asset_number column
        output = StringIO()
        output.write("asset_number,timestamp,lamp_hours,event_type,device_name,artwork_name,exhibition_name\n")

        for log in logs:
            asset_number = assets.get(str(log.asset_id), "unknown")
            output.write(
                f"\"{asset_number}\","
                f"{log.timestamp.isoformat()},"
                f"{log.lamp_hours},"
                f"{log.event_type},"
                f"\"{log.device_name or ''}\","
                f"\"{log.artwork_name or ''}\","
                f"\"{log.exhibition_name or ''}\"\n"
            )

        output.seek(0)
        filename = f"lamp_history_{len(asset_ids)}_assets.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting bulk lamp history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{asset_id}")
async def update_asset(
    asset_id: str = Path(pattern=UUID_PATTERN),
    asset_update: AssetUpdate = ...,
    session=Depends(get_session),
):
    """Update asset (notes, hostname override)."""
    try:
        stmt = select(Asset).where(Asset.id == parse_uuid(asset_id, "asset_id"))
        result = await session.execute(stmt)
        asset = result.scalar_one_or_none()

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        if asset_update.hostname is not None:
            asset.hostname = asset_update.hostname if asset_update.hostname else None
            # Mark as manually set if user provides a hostname, clear flag if they clear it
            asset.hostname_manual = bool(asset_update.hostname)
        if asset_update.notes is not None:
            asset.notes = asset_update.notes

        await session.flush()

        return {
            "id": str(asset.id),
            "asset_number": asset.asset_number,
            "hostname": asset.hostname,
            "hostname_manual": asset.hostname_manual,
            "notes": asset.notes,
            "updated_at": asset.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(asset_id: str = Path(pattern=UUID_PATTERN), session=Depends(get_session)):
    """Delete asset (cascades to lamp history).

    WARNING: This will delete all lamp hours history for this asset.
    """
    try:
        from sqlalchemy import delete

        # First unlink any devices
        device_stmt = (
            select(Device)
            .where(Device.asset_id == parse_uuid(asset_id, "asset_id"))
        )
        device_result = await session.execute(device_stmt)
        devices = device_result.scalars().all()

        for device in devices:
            device.asset_id = None

        # Delete asset (cascades to lamp_hours_logs)
        stmt = delete(Asset).where(Asset.id == parse_uuid(asset_id, "asset_id"))
        result = await session.execute(stmt)

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Asset not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resolve/{device_id}")
async def resolve_device_dns(device_id: str, request: Request):
    """Trigger manual DNS resolution for a device.

    Returns the resolved hostname/IP.
    """
    try:
        asset_service = getattr(request.app.state, 'asset_service', None)
        if not asset_service:
            raise HTTPException(status_code=503, detail="Asset service not available")

        resolved = await asset_service.update_device_dns(parse_uuid(device_id, "device_id"))

        return {
            "device_id": device_id,
            "resolved": resolved,
            "success": resolved is not None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving DNS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{asset_id}/lamp-hours")
async def add_manual_lamp_hours(
    request: Request,
    asset_id: str = Path(pattern=UUID_PATTERN),
    entry: ManualLampHoursRequest = ...,
):
    """Add manual lamp hours entry."""
    try:
        asset_service = getattr(request.app.state, 'asset_service', None)
        if not asset_service:
            raise HTTPException(status_code=503, detail="Asset service not available")

        log = await asset_service.add_manual_lamp_hours(
            asset_id=parse_uuid(asset_id, "asset_id"),
            lamp_hours=entry.lamp_hours,
            device_id=parse_uuid(entry.device_id, "device_id") if entry.device_id else None,
            notes=entry.notes,
        )

        return {
            "id": str(log.id),
            "asset_id": str(log.asset_id),
            "lamp_hours": log.lamp_hours,
            "event_type": log.event_type,
            "timestamp": log.timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding manual lamp hours: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill")
async def backfill_assets(request: Request):
    """Backfill assets for existing PJLink devices.

    Creates assets and records onboard lamp hours for all PJLink devices
    that don't have an asset linked yet.

    Returns progress report when done.
    """
    try:
        asset_service = getattr(request.app.state, 'asset_service', None)
        if not asset_service:
            raise HTTPException(status_code=503, detail="Asset service not available")

        results = await asset_service.backfill_assets()
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-initial-lamp-hours")
async def record_initial_lamp_hours(request: Request):
    """Record initial lamp hours for linked devices without history.

    Queries current lamp hours from projectors that are linked to assets
    but have no lamp hours history recorded yet.

    This is useful for devices that were linked before lamp tracking was
    implemented.

    Returns progress report when done.
    """
    try:
        asset_service = getattr(request.app.state, 'asset_service', None)
        if not asset_service:
            raise HTTPException(status_code=503, detail="Asset service not available")

        results = await asset_service.record_initial_lamp_hours()
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording initial lamp hours: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-lamp-hours")
async def record_lamp_hours_for_assets(
    asset_ids: List[str],
    request: Request,
    session=Depends(get_session),
):
    """Record current lamp hours for selected assets.

    Queries current lamp hours from projectors linked to the specified assets.
    Unlike record-initial-lamp-hours, this records for ALL specified assets
    regardless of whether they already have lamp history.

    Args:
        asset_ids: List of asset UUIDs to record lamp hours for

    Returns:
        Progress report with recorded, skipped, and failed counts
    """
    try:
        if not asset_ids:
            raise HTTPException(status_code=400, detail="No asset IDs provided")

        asset_service = getattr(request.app.state, 'asset_service', None)
        if not asset_service:
            raise HTTPException(status_code=503, detail="Asset service not available")

        # Parse UUIDs
        asset_uuids = [parse_uuid(aid, "asset_id") for aid in asset_ids]

        results = await asset_service.record_lamp_hours_for_assets(asset_uuids, session)
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording lamp hours: {e}")
        raise HTTPException(status_code=500, detail=str(e))
