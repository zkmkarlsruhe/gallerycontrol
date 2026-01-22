"""Unified cron scheduler for system tasks and device automation.

Replaces the old interval-based TaskScheduler with cron expressions.
Handles both maintenance tasks (asset_linker, log_cleanup) and device
automation (turn projector on at 9am).

Features:
- Cron expression parsing via croniter
- Exponential backoff on failure (capped at 1 hour)
- Circuit breaker (5 consecutive failures = pause until manual reset)
- Execution logging with result tracking
- Admin UI management via database
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from croniter import croniter
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from mutech_control.database.models import Device, ScheduledJob, ScheduledJobLog
from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)

# Type alias for system task functions
SystemTaskFunc = Callable[..., Any]


class CronScheduler:
    """Unified scheduler for cron-based job execution.

    Manages both system maintenance tasks and device automation jobs.
    All jobs are stored in the database and can be managed via Admin UI.
    """

    def __init__(
        self,
        db_manager,
        orchestrator=None,
        device_managers: Optional[Dict] = None,
        asset_service=None,
        config: Optional[dict] = None,
    ):
        """Initialize the scheduler.

        Args:
            db_manager: Database manager instance
            orchestrator: CommandOrchestrator for device commands
            device_managers: Dict of device type -> manager
            asset_service: AssetService for asset-related tasks
            config: Application configuration
        """
        self.db_manager = db_manager
        self.orchestrator = orchestrator
        self.device_managers = device_managers or {}
        self.asset_service = asset_service
        self.config = config or {}

        # Scheduler config
        scheduler_config = self.config.get("scheduler", {})
        self.enabled = scheduler_config.get("enabled", True)
        self.check_interval = scheduler_config.get("check_interval_seconds", 30)

        # Runtime state
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # System task registry - maps task_name to (function, default_config)
        self._system_tasks: Dict[str, tuple[SystemTaskFunc, dict]] = {}

    def register_system_task(
        self,
        task_name: str,
        func: SystemTaskFunc,
        default_config: Optional[dict] = None,
    ) -> None:
        """Register a system task handler.

        Args:
            task_name: Unique task identifier (e.g., 'asset_linker')
            func: Async function to execute
            default_config: Default task configuration
        """
        self._system_tasks[task_name] = (func, default_config or {})
        logger.debug("Registered system task", task_name=task_name)

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if not self.enabled:
            logger.info("Scheduler disabled in configuration")
            return

        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True

        # Seed default system jobs if missing
        await self._seed_system_jobs()

        # Update next_run_at for all enabled jobs
        await self._update_all_next_runs()

        # Start the background loop
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            "Cron scheduler started",
            check_interval=self.check_interval,
            system_tasks=list(self._system_tasks.keys()),
        )

    async def stop(self) -> None:
        """Stop the scheduler background loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Cron scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - checks for due jobs."""
        while self._running:
            try:
                await self._check_and_execute_jobs()
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))

            await asyncio.sleep(self.check_interval)

    async def _check_and_execute_jobs(self) -> None:
        """Check for due jobs and execute them."""
        now = datetime.now(timezone.utc)

        async with self.db_manager.session() as session:
            # Find enabled jobs that are due
            stmt = (
                select(ScheduledJob)
                .where(ScheduledJob.enabled == True)
                .where(ScheduledJob.next_run_at != None)
                .where(ScheduledJob.next_run_at <= now)
                .where(
                    # Skip jobs in backoff
                    (ScheduledJob.backoff_until == None)
                    | (ScheduledJob.backoff_until <= now)
                )
                .options(selectinload(ScheduledJob.target_device))
            )
            result = await session.execute(stmt)
            due_jobs = result.scalars().all()

            if not due_jobs:
                return

            logger.debug("Found due jobs", count=len(due_jobs))

        # Execute each job (outside the session to avoid long-running transactions)
        for job in due_jobs:
            # Skip if circuit is open
            if job.circuit_open:
                logger.debug(
                    "Skipping job - circuit open",
                    job=job.name,
                    fail_count=job.fail_count,
                )
                continue

            try:
                await self._execute_job(job)
            except Exception as e:
                logger.error("Error executing job", job=job.name, error=str(e))
                await self._record_failure(job.id, str(e))

    async def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single job."""
        scheduled_at = job.next_run_at
        start_time = asyncio.get_event_loop().time()

        logger.info(
            "Executing scheduled job",
            job=job.name,
            job_type=job.job_type,
            task_name=job.task_name if job.job_type == "system" else None,
            action_type=job.action_type if job.job_type == "device" else None,
        )

        success = False
        error_message = None
        result_data = None

        try:
            if job.job_type == "system":
                success, error_message, result_data = await self._execute_system_task(
                    job
                )
            elif job.job_type == "device":
                success, error_message = await self._execute_device_job(job)
            else:
                error_message = f"Unknown job type: {job.job_type}"

        except Exception as e:
            error_message = str(e)
            logger.error("Job execution failed", job=job.name, error=str(e))

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        # Log execution and update job state
        await self._record_execution(
            job_id=job.id,
            scheduled_at=scheduled_at,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            result=result_data,
        )

        if success:
            logger.info("Job completed successfully", job=job.name, duration_ms=duration_ms)
        else:
            logger.warning("Job failed", job=job.name, error=error_message)

    async def _execute_system_task(
        self, job: ScheduledJob
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """Execute a system maintenance task.

        Returns:
            Tuple of (success, error_message, result_data)
        """
        task_name = job.task_name
        if not task_name:
            return False, "No task_name specified for system job", None

        if task_name not in self._system_tasks:
            return False, f"Unknown system task: {task_name}", None

        func, default_config = self._system_tasks[task_name]

        # Merge default config with job-specific config
        task_config = {**default_config, **(job.task_config or {})}

        try:
            result = await func(**task_config)
            return True, None, result
        except Exception as e:
            return False, str(e), None

    async def _execute_device_job(
        self, job: ScheduledJob
    ) -> tuple[bool, Optional[str]]:
        """Execute a device automation job.

        Returns:
            Tuple of (success, error_message)
        """
        if not job.target_device_id:
            return False, "No target_device_id specified for device job"

        if not self.orchestrator:
            return False, "Orchestrator not available"

        action_type = job.action_type
        if action_type in ("on", "off"):
            # Use orchestrator for ON/OFF commands
            result = await self.orchestrator.execute_control_command(
                target_type="device",
                target_id=str(job.target_device_id),
                command=action_type,
                source="scheduler",
            )
            success = result.get("success", False)
            if not success:
                error = result.get("error", "Unknown error")
                results = result.get("results", [])
                if results and not results[0].get("success"):
                    error = results[0].get("error", error)
                return False, error
            return True, None

        elif action_type == "action":
            # Execute shell action
            if not job.action_name:
                return False, "No action_name specified for action job"
            return await self._execute_shell_action(
                job.target_device_id, job.action_name
            )

        else:
            return False, f"Unknown action_type: {action_type}"

    async def _execute_shell_action(
        self, device_id: UUID, action_name: str
    ) -> tuple[bool, Optional[str]]:
        """Execute a shell device action."""
        from mutech_control.devices.shell_manager import replace_credential_placeholders

        async with self.db_manager.session() as session:
            stmt = select(Device).where(Device.id == device_id)
            result = await session.execute(stmt)
            device = result.scalar_one_or_none()

            if not device:
                return False, f"Device not found: {device_id}"

            if device.device_type != "shell":
                return False, "Actions only available for shell devices"

            # Find action in config
            action = None

            # New format: config.actions array
            actions_array = device.config.get("actions", [])
            if actions_array:
                action = next(
                    (a for a in actions_array if a.get("name") == action_name), None
                )

            # Old format: commands dict
            if not action:
                commands = device.config.get("commands", {})
                if isinstance(commands, dict) and action_name in commands:
                    cmd_config = commands[action_name]
                    if isinstance(cmd_config, dict) and cmd_config.get("cmd"):
                        action = {"name": action_name, "cmd": cmd_config["cmd"]}

            if not action:
                return False, f"Action '{action_name}' not found"

            cmd = replace_credential_placeholders(action["cmd"])

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 0:
                return True, None
            else:
                error = stderr.decode()[:500] if stderr else "Command failed"
                return False, error

        except asyncio.TimeoutError:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)

    async def _record_execution(
        self,
        job_id: UUID,
        scheduled_at: datetime,
        success: bool,
        error_message: Optional[str],
        duration_ms: int,
        result: Optional[dict] = None,
    ) -> None:
        """Record job execution and update job state."""
        now = datetime.now(timezone.utc)

        try:
            async with self.db_manager.session() as session:
                # Get job for update
                stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
                db_result = await session.execute(stmt)
                job = db_result.scalar_one_or_none()

                if not job:
                    return

                # Update job state
                job.last_run_at = now
                job.last_success = success
                job.last_error = error_message if not success else None
                job.last_duration_ms = duration_ms

                if success:
                    # Reset failure tracking on success
                    job.fail_count = 0
                    job.backoff_until = None
                else:
                    # Increment failure count and calculate backoff
                    job.fail_count += 1
                    backoff_seconds = min(
                        self.check_interval * (2 ** job.fail_count),
                        3600,  # Cap at 1 hour
                    )
                    job.backoff_until = now + timedelta(seconds=backoff_seconds)

                # Calculate next run time
                job.next_run_at = self._calculate_next_run(job.cron_expression)

                # Create execution log
                log = ScheduledJobLog(
                    job_id=job_id,
                    scheduled_at=scheduled_at,
                    executed_at=now,
                    success=success,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    result=result,
                )
                session.add(log)

        except Exception as e:
            logger.error("Error recording job execution", job_id=str(job_id), error=str(e))

    async def _record_failure(self, job_id: UUID, error: str) -> None:
        """Record a job failure without full execution logging."""
        await self._record_execution(
            job_id=job_id,
            scheduled_at=datetime.now(timezone.utc),
            success=False,
            error_message=error,
            duration_ms=0,
        )

    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """Calculate the next run time for a cron expression.

        Args:
            cron_expression: Standard cron expression

        Returns:
            Next run time in UTC
        """
        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        next_run = cron.get_next(datetime)

        # croniter returns timezone-aware datetime if input was aware
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        return next_run

    async def _update_all_next_runs(self) -> None:
        """Update next_run_at for all enabled jobs on startup."""
        try:
            async with self.db_manager.session() as session:
                stmt = select(ScheduledJob).where(ScheduledJob.enabled == True)
                result = await session.execute(stmt)
                jobs = result.scalars().all()

                for job in jobs:
                    job.next_run_at = self._calculate_next_run(job.cron_expression)

                logger.info("Updated next_run_at for jobs", count=len(jobs))

        except Exception as e:
            logger.error("Error updating next runs", error=str(e))

    async def _seed_system_jobs(self) -> None:
        """Seed default system jobs if they don't exist."""
        default_jobs = [
            {
                "name": "Asset Linker",
                "task_name": "asset_linker",
                "cron_expression": "*/10 * * * *",  # Every 10 minutes
                "task_config": {"batch_size": 20},
            },
            {
                "name": "Log Cleanup",
                "task_name": "log_cleanup",
                "cron_expression": "0 3 * * *",  # Daily at 3 AM
                "task_config": {"retention_hours": 24},
            },
            {
                "name": "Device Info Cache",
                "task_name": "device_info_cache",
                "cron_expression": "*/30 * * * *",  # Every 30 minutes
                "task_config": {"max_concurrent": 5, "timeout_seconds": 10},
            },
            {
                "name": "Lamp Hours Check",
                "task_name": "lamp_hours_check",
                "cron_expression": "0 4 * * *",  # Daily at 4 AM
                "task_config": {"chunk_size": 10, "delay_between_chunks": 2.0},
            },
        ]

        try:
            async with self.db_manager.session() as session:
                for job_data in default_jobs:
                    # Check if job already exists
                    stmt = select(ScheduledJob).where(
                        ScheduledJob.task_name == job_data["task_name"]
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        continue

                    # Create new job
                    job = ScheduledJob(
                        name=job_data["name"],
                        job_type="system",
                        cron_expression=job_data["cron_expression"],
                        task_name=job_data["task_name"],
                        task_config=job_data["task_config"],
                        enabled=True,
                    )
                    session.add(job)
                    logger.info("Seeded system job", name=job_data["name"])

        except Exception as e:
            logger.error("Error seeding system jobs", error=str(e))

    # === Public API for Admin UI ===

    async def get_status(self) -> dict:
        """Get scheduler status for Admin API."""
        async with self.db_manager.session() as session:
            stmt = select(ScheduledJob)
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            jobs_status = []
            for job in jobs:
                jobs_status.append({
                    "id": str(job.id),
                    "name": job.name,
                    "job_type": job.job_type,
                    "cron_expression": job.cron_expression,
                    "task_name": job.task_name,
                    "action_type": job.action_type,
                    "enabled": job.enabled,
                    "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                    "last_success": job.last_success,
                    "last_error": job.last_error,
                    "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
                    "fail_count": job.fail_count,
                    "circuit_open": job.circuit_open,
                })

            return {
                "enabled": self.enabled,
                "running": self._running,
                "check_interval_seconds": self.check_interval,
                "jobs": jobs_status,
            }

    async def trigger_job(self, job_id: UUID) -> bool:
        """Trigger immediate execution of a job.

        Args:
            job_id: Job UUID to trigger

        Returns:
            True if triggered, False if not found or circuit open
        """
        async with self.db_manager.session() as session:
            stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                return False

            if job.circuit_open:
                return False

            # Set next_run_at to now to trigger on next check
            job.next_run_at = datetime.now(timezone.utc)
            return True

    async def reset_circuit(self, job_id: UUID) -> bool:
        """Reset circuit breaker for a job.

        Args:
            job_id: Job UUID to reset

        Returns:
            True if reset, False if not found
        """
        async with self.db_manager.session() as session:
            stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                return False

            job.fail_count = 0
            job.backoff_until = None
            job.next_run_at = datetime.now(timezone.utc)

            logger.info("Reset circuit breaker", job=job.name)
            return True

    @staticmethod
    def validate_cron_expression(cron_expression: str) -> tuple[bool, Optional[str]]:
        """Validate a cron expression.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            croniter(cron_expression)
            return True, None
        except (ValueError, KeyError) as e:
            return False, str(e)

    @staticmethod
    def get_next_runs(cron_expression: str, count: int = 5) -> list[datetime]:
        """Get the next N run times for a cron expression.

        Returns:
            List of next run times in UTC
        """
        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        runs = []

        for _ in range(count):
            next_run = cron.get_next(datetime)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            runs.append(next_run)

        return runs
