"""Log cleanup task - prunes old operation logs.

This task runs periodically to delete operation logs older than the
configured retention period (default 24 hours).
"""

from typing import Any, Dict

from mutech_control.database.operation_logger import cleanup_old_operation_logs
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


async def run_log_cleanup(
    db_manager,
    retention_hours: int = 24,
) -> Dict[str, Any]:
    """Delete operation logs older than retention period.

    Args:
        db_manager: Database manager instance
        retention_hours: How many hours of logs to keep

    Returns:
        Dict with deleted count
    """
    deleted = await cleanup_old_operation_logs(db_manager, retention_hours)

    return {
        "deleted": deleted,
        "retention_hours": retention_hours,
    }
