# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Device operation logging for debug data with raw responses."""

from datetime import datetime, timedelta

from gallerycontrol.utils.datetime_utils import utc_now
from uuid import UUID

from sqlalchemy import delete, select

from gallerycontrol.database.models import Artwork, Device, DeviceOperationLog
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum length for raw response to prevent DB bloat
MAX_RAW_RESPONSE_LENGTH = 10000


async def log_device_operation(
    db_manager,
    device_id: UUID,
    operation_type: str,
    source: str,
    success: bool,
    state_before: int | None = None,
    state_after: int | None = None,
    raw_request: str | None = None,
    raw_response: str | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    artwork_id: UUID | None = None,
    exhibition_id: UUID | None = None,
) -> None:
    """Log a device operation with full debug details.

    Args:
        db_manager: Database manager instance
        device_id: UUID of the device
        operation_type: Type of operation ('state_query', 'power_on', 'power_off', 'action')
        source: What triggered the operation ('polling', 'web', 'fast', 'verification')
        success: Whether the operation succeeded
        state_before: Device state before operation
        state_after: Device state after operation
        raw_request: Raw request data sent to device (optional)
        raw_response: Raw response received from device (optional)
        error_message: Error message if operation failed
        duration_ms: Operation duration in milliseconds
        artwork_id: Artwork ID at time of operation (looked up if not provided)
        exhibition_id: Exhibition ID at time of operation (looked up if not provided)
    """
    try:
        # Truncate raw response if too long
        if raw_response and len(raw_response) > MAX_RAW_RESPONSE_LENGTH:
            raw_response = raw_response[:MAX_RAW_RESPONSE_LENGTH] + "\n... (truncated)"

        if raw_request and len(raw_request) > MAX_RAW_RESPONSE_LENGTH:
            raw_request = raw_request[:MAX_RAW_RESPONSE_LENGTH] + "\n... (truncated)"

        async with db_manager.session() as session:
            # Look up artwork_id and exhibition_id if not provided
            if artwork_id is None or exhibition_id is None:
                stmt = (
                    select(Device.artwork_id, Artwork.exhibition_id)
                    .join(Artwork, Device.artwork_id == Artwork.id)
                    .where(Device.id == device_id)
                )
                result = await session.execute(stmt)
                row = result.first()
                if row:
                    artwork_id = artwork_id or row.artwork_id
                    exhibition_id = exhibition_id or row.exhibition_id

            log_entry = DeviceOperationLog(
                device_id=device_id,
                artwork_id=artwork_id,
                exhibition_id=exhibition_id,
                operation_type=operation_type,
                source=source,
                success=success,
                state_before=state_before,
                state_after=state_after,
                raw_request=raw_request,
                raw_response=raw_response,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            session.add(log_entry)

    except Exception as e:
        # Don't let logging failures affect main operation
        logger.error(
            "Error logging device operation",
            device_id=str(device_id)[:8],
            operation_type=operation_type,
            error=str(e),
        )


async def cleanup_old_operation_logs(
    db_manager,
    retention_hours: int = 24,
) -> int:
    """Delete operation logs older than retention period.

    Args:
        db_manager: Database manager instance
        retention_hours: How many hours of logs to keep (default 24)

    Returns:
        Number of deleted records
    """
    try:
        cutoff = utc_now() - timedelta(hours=retention_hours)

        async with db_manager.session() as session:
            stmt = delete(DeviceOperationLog).where(
                DeviceOperationLog.timestamp < cutoff
            )
            result = await session.execute(stmt)
            deleted_count = result.rowcount

            if deleted_count > 0:
                logger.info(
                    "Cleaned up old operation logs",
                    deleted_count=deleted_count,
                    retention_hours=retention_hours,
                )

            return deleted_count

    except Exception as e:
        logger.error("Error cleaning up operation logs", error=str(e))
        return 0
