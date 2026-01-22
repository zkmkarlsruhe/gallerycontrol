"""Log cleanup task - prunes old operation logs and executed one-shot jobs.

This task runs periodically to delete:
- Operation logs older than the configured retention period (default 24 hours)
- Executed one-shot scheduled jobs older than 24 hours
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import and_, delete, select, func

from mutech_control.database.models import ScheduledJob
from mutech_control.database.operation_logger import cleanup_old_operation_logs
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


async def run_log_cleanup(
    db_manager,
    retention_hours: int = 24,
    one_shot_retention_hours: int = 24,
) -> Dict[str, Any]:
    """Delete operation logs and executed one-shot jobs older than retention period.

    Args:
        db_manager: Database manager instance
        retention_hours: How many hours of operation logs to keep
        one_shot_retention_hours: How many hours to keep executed one-shot jobs

    Returns:
        Dict with deleted counts
    """
    # Clean up operation logs
    deleted_logs = await cleanup_old_operation_logs(db_manager, retention_hours)

    # Clean up executed one-shot jobs
    deleted_one_shots = 0
    cutoff = datetime.utcnow() - timedelta(hours=one_shot_retention_hours)

    try:
        async with db_manager.session() as session:
            # Delete executed one-shot jobs older than cutoff
            stmt = delete(ScheduledJob).where(
                and_(
                    ScheduledJob.run_once == True,
                    ScheduledJob.executed_at != None,
                    ScheduledJob.executed_at < cutoff,
                )
            )
            result = await session.execute(stmt)
            deleted_one_shots = result.rowcount

            if deleted_one_shots > 0:
                logger.info(
                    "Cleaned up executed one-shot jobs",
                    deleted=deleted_one_shots,
                    cutoff=cutoff.isoformat(),
                )

    except Exception as e:
        logger.error("Error cleaning up one-shot jobs", error=str(e))

    return {
        "deleted_logs": deleted_logs,
        "deleted_one_shots": deleted_one_shots,
        "retention_hours": retention_hours,
        "one_shot_retention_hours": one_shot_retention_hours,
    }
