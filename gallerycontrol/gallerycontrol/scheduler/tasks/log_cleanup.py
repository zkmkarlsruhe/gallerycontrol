# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Log cleanup task - prunes old logs and executed one-shot jobs.

This task runs periodically to delete:
- Operation logs older than the configured retention period (default 24 hours)
- Command logs older than the configured retention period (default 24 hours)
- Scheduled job logs older than the configured retention period (default 24 hours)
- Executed one-shot scheduled jobs older than 24 hours
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import and_, delete, select, func

from gallerycontrol.database.models import CommandLog, ScheduledJob, ScheduledJobLog
from gallerycontrol.database.operation_logger import cleanup_old_operation_logs
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)


async def run_log_cleanup(
    db_manager,
    retention_hours: int = 24,
    one_shot_retention_hours: int = 24,
    command_log_retention_hours: int = 168,  # 7 days default for command logs
) -> Dict[str, Any]:
    """Delete old logs and executed one-shot jobs older than retention period.

    Args:
        db_manager: Database manager instance
        retention_hours: How many hours of operation logs to keep
        one_shot_retention_hours: How many hours to keep executed one-shot jobs
        command_log_retention_hours: How many hours of command logs to keep

    Returns:
        Dict with deleted counts
    """
    # Clean up operation logs
    deleted_logs = await cleanup_old_operation_logs(db_manager, retention_hours)

    # Clean up executed one-shot jobs and other logs
    deleted_one_shots = 0
    deleted_command_logs = 0
    deleted_job_logs = 0
    cutoff = datetime.utcnow() - timedelta(hours=one_shot_retention_hours)
    command_log_cutoff = datetime.utcnow() - timedelta(hours=command_log_retention_hours)

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

            # Delete old command logs
            stmt = delete(CommandLog).where(CommandLog.timestamp < command_log_cutoff)
            result = await session.execute(stmt)
            deleted_command_logs = result.rowcount

            if deleted_command_logs > 0:
                logger.info(
                    "Cleaned up old command logs",
                    deleted=deleted_command_logs,
                    cutoff=command_log_cutoff.isoformat(),
                )

            # Delete old scheduled job logs
            stmt = delete(ScheduledJobLog).where(ScheduledJobLog.executed_at < cutoff)
            result = await session.execute(stmt)
            deleted_job_logs = result.rowcount

            if deleted_job_logs > 0:
                logger.info(
                    "Cleaned up old scheduled job logs",
                    deleted=deleted_job_logs,
                    cutoff=cutoff.isoformat(),
                )

    except Exception as e:
        logger.error("Error cleaning up logs", error=str(e))

    return {
        "deleted_logs": deleted_logs,
        "deleted_command_logs": deleted_command_logs,
        "deleted_job_logs": deleted_job_logs,
        "deleted_one_shots": deleted_one_shots,
        "retention_hours": retention_hours,
        "command_log_retention_hours": command_log_retention_hours,
        "one_shot_retention_hours": one_shot_retention_hours,
    }
