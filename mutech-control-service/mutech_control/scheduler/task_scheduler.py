"""Task scheduler for periodic maintenance tasks.

Separate from real-time device polling in StateMonitor - this handles:
- Asset linking for PJLink devices
- Operation log cleanup
- Future maintenance tasks

Features:
- Function-based tasks (no ABC hierarchy)
- In-memory state with jitter on restart
- Exponential backoff on failures
- Circuit breaker (5 consecutive failures = skip until restart)
"""

import asyncio
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskState:
    """Runtime state for a scheduled task."""

    last_run_at: Optional[datetime] = None
    next_run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fail_count: int = 0
    is_running: bool = False
    last_error: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None

    @property
    def circuit_open(self) -> bool:
        """Circuit is open after 5 consecutive failures."""
        return self.fail_count >= 5


@dataclass
class TaskConfig:
    """Configuration for a scheduled task."""

    name: str
    func: Callable[[], Awaitable[Dict[str, Any]]]
    interval_seconds: float
    enabled: bool = True


class TaskScheduler:
    """Scheduler for periodic maintenance tasks.

    Features:
    - Jitter on startup to avoid thundering herd
    - Exponential backoff on failures (capped at 1 hour)
    - Circuit breaker after 5 consecutive failures
    - Hot-reload support via refresh_from_config()
    """

    def __init__(self, db_manager, config: dict, asset_service=None):
        """Initialize the task scheduler.

        Args:
            db_manager: Database manager instance
            config: Full application config dict
            asset_service: AssetService instance for asset linking tasks
        """
        self.db_manager = db_manager
        self.config = config
        self.asset_service = asset_service

        self._tasks: Dict[str, TaskConfig] = {}
        self._state: Dict[str, TaskState] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Get scheduler config
        scheduler_config = config.get("scheduler", {})
        self.enabled = scheduler_config.get("enabled", True)
        self.check_interval = scheduler_config.get("check_interval_seconds", 60)

        # Register tasks from config
        self._register_tasks_from_config(scheduler_config)

    def _register_tasks_from_config(self, scheduler_config: dict) -> None:
        """Register tasks based on configuration."""
        from mutech_control.scheduler.tasks import run_asset_linker, run_log_cleanup

        tasks_config = scheduler_config.get("tasks", {})

        # Asset linker task
        asset_linker_config = tasks_config.get("asset_linker", {})
        if asset_linker_config.get("enabled", True) and self.asset_service:
            batch_size = asset_linker_config.get("batch_size", 20)
            self._tasks["asset_linker"] = TaskConfig(
                name="asset_linker",
                func=lambda: run_asset_linker(
                    self.db_manager, self.asset_service, batch_size
                ),
                interval_seconds=asset_linker_config.get("interval_minutes", 10) * 60,
                enabled=True,
            )

        # Log cleanup task
        log_cleanup_config = tasks_config.get("log_cleanup", {})
        if log_cleanup_config.get("enabled", True):
            retention_hours = log_cleanup_config.get("retention_hours", 24)
            self._tasks["log_cleanup"] = TaskConfig(
                name="log_cleanup",
                func=lambda rh=retention_hours: run_log_cleanup(
                    self.db_manager, rh
                ),
                interval_seconds=log_cleanup_config.get("interval_minutes", 60) * 60,
                enabled=True,
            )

    def _initialize_task_states(self) -> None:
        """Initialize task states with jitter on startup."""
        for name, config in self._tasks.items():
            if not config.enabled:
                continue

            # Jitter: random delay 0-50% of interval on startup
            jitter = random.uniform(0, config.interval_seconds * 0.5)
            self._state[name] = TaskState(
                next_run_at=datetime.now(timezone.utc) + timedelta(seconds=jitter)
            )
            logger.debug(
                "Task initialized with jitter",
                task=name,
                jitter_seconds=round(jitter, 1),
                next_run_at=self._state[name].next_run_at.isoformat(),
            )

    async def start(self) -> None:
        """Start the task scheduler."""
        if not self.enabled:
            logger.info("Task scheduler disabled in configuration")
            return

        if self._running:
            logger.warning("Task scheduler already running")
            return

        if not self._tasks:
            logger.info("No tasks configured, scheduler not starting")
            return

        self._running = True
        self._initialize_task_states()
        self._task = asyncio.create_task(self._scheduler_loop())

        logger.info(
            "Task scheduler started",
            tasks=list(self._tasks.keys()),
            check_interval=self.check_interval,
        )

    async def stop(self) -> None:
        """Stop the task scheduler."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - checks for tasks due for execution."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)

                for name, config in self._tasks.items():
                    if not config.enabled:
                        continue

                    state = self._state.get(name)
                    if not state:
                        continue

                    # Skip if circuit is open
                    if state.circuit_open:
                        continue

                    # Skip if already running
                    if state.is_running:
                        continue

                    # Check if due for execution
                    if now >= state.next_run_at:
                        asyncio.create_task(self._execute_task(name, config))

            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))

            await asyncio.sleep(self.check_interval)

    async def _execute_task(self, name: str, config: TaskConfig) -> None:
        """Execute a single task with error handling and backoff."""
        state = self._state[name]

        # Double-check not already running
        if state.is_running:
            return

        state.is_running = True
        start_time = datetime.now(timezone.utc)

        try:
            logger.debug("Executing scheduled task", task=name)
            result = await config.func()

            # Success - reset fail count and schedule next run
            state.fail_count = 0
            state.last_error = None
            state.last_result = result
            state.next_run_at = datetime.now(timezone.utc) + timedelta(
                seconds=config.interval_seconds
            )

            logger.info(
                "Scheduled task completed",
                task=name,
                result=result,
                next_run_at=state.next_run_at.isoformat(),
            )

        except Exception as e:
            state.fail_count += 1
            state.last_error = str(e)

            # Exponential backoff: base_interval * (2 ^ fail_count), capped at 1 hour
            backoff = min(
                config.interval_seconds * (2 ** state.fail_count),
                3600,
            )
            state.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)

            if state.circuit_open:
                logger.error(
                    "Task circuit open after 5 failures",
                    task=name,
                    error=str(e),
                )
            else:
                logger.warning(
                    "Scheduled task failed",
                    task=name,
                    fail_count=state.fail_count,
                    backoff_seconds=backoff,
                    error=str(e),
                )

        finally:
            state.is_running = False
            state.last_run_at = start_time

    def refresh_from_config(self, config: dict) -> None:
        """Update task configuration from new config.

        Updates intervals and enabled states, but does NOT reset
        fail_count or next_run_at to preserve circuit breaker state.
        """
        scheduler_config = config.get("scheduler", {})
        self.enabled = scheduler_config.get("enabled", True)
        self.check_interval = scheduler_config.get("check_interval_seconds", 60)

        tasks_config = scheduler_config.get("tasks", {})

        for name, task_config in self._tasks.items():
            task_settings = tasks_config.get(name, {})

            # Update enabled state
            task_config.enabled = task_settings.get("enabled", True)

            # Update interval
            if "interval_minutes" in task_settings:
                task_config.interval_seconds = task_settings["interval_minutes"] * 60

        logger.info("Task scheduler config refreshed")

    def reset_circuit(self, task_name: str) -> bool:
        """Manually reset circuit breaker for a task.

        Args:
            task_name: Name of the task to reset

        Returns:
            True if reset was successful, False if task not found
        """
        if task_name not in self._state:
            return False

        state = self._state[task_name]
        state.fail_count = 0
        state.last_error = None
        state.next_run_at = datetime.now(timezone.utc)

        logger.info("Task circuit reset", task=task_name)
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status for API endpoint.

        Returns:
            Dict with scheduler state and per-task status
        """
        tasks_status = {}
        for name, state in self._state.items():
            config = self._tasks.get(name)
            tasks_status[name] = {
                "enabled": config.enabled if config else False,
                "interval_seconds": config.interval_seconds if config else 0,
                "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
                "next_run_at": state.next_run_at.isoformat(),
                "fail_count": state.fail_count,
                "circuit_open": state.circuit_open,
                "is_running": state.is_running,
                "last_error": state.last_error,
                "last_result": state.last_result,
            }

        return {
            "enabled": self.enabled,
            "running": self._running,
            "check_interval_seconds": self.check_interval,
            "tasks": tasks_status,
        }

    def trigger_task(self, task_name: str) -> bool:
        """Trigger immediate execution of a task.

        Args:
            task_name: Name of the task to trigger

        Returns:
            True if task was triggered, False if not found or already running
        """
        if task_name not in self._state:
            return False

        state = self._state[task_name]
        if state.is_running:
            return False

        if state.circuit_open:
            return False

        # Set next_run_at to now to trigger on next check
        state.next_run_at = datetime.now(timezone.utc)
        return True
