# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Unified cron scheduler for system tasks and device automation.

Replaces the old interval-based TaskScheduler with cron expressions.
Handles both maintenance tasks (asset_linker, log_cleanup) and device
automation (turn projector on at 9am, or one-shot scheduled tasks).

Features:
- Cron expression parsing via croniter for recurring jobs
- One-shot scheduled tasks (run once at specified time)
- Exponential backoff on failure (capped at 1 hour)
- Circuit breaker (5 consecutive failures = pause until manual reset)
- Execution logging with result tracking
- Admin UI management via database
- Target flexibility: device, artwork, or exhibition
"""

import asyncio
from datetime import datetime, timedelta, timezone

from gallerycontrol.utils.datetime_utils import utc_now
from typing import Any, Callable, Dict, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from croniter import croniter

# Default timezone for naive datetime inputs (user's local time)
LOCAL_TZ = ZoneInfo("Europe/Berlin")
from sqlalchemy import and_, select, update
from sqlalchemy.orm import selectinload

from gallerycontrol.database.models import Artwork, Device, Exhibition, ScheduledJob, ScheduledJobLog
from gallerycontrol.utils.logging import get_logger

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

        # Lock to prevent duplicate job execution
        self._executing_jobs: set[UUID] = set()
        self._job_lock = asyncio.Lock()

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
        now = utc_now()

        async with self.db_manager.session() as session:
            # Find enabled jobs that are due
            # For one-shot jobs: only if not yet executed (executed_at IS NULL)
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
                .where(
                    # For one-shot jobs, only run if not yet executed
                    (ScheduledJob.run_once == False)
                    | (ScheduledJob.executed_at == None)
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

            # Skip if already executing (prevents race condition with slow jobs)
            async with self._job_lock:
                if job.id in self._executing_jobs:
                    logger.debug(
                        "Skipping job - already executing",
                        job=job.name,
                    )
                    continue
                self._executing_jobs.add(job.id)

            try:
                await self._execute_job(job)
            except Exception as e:
                logger.error("Error executing job", job=job.name, error=str(e))
                await self._record_failure(job.id, str(e))
            finally:
                async with self._job_lock:
                    self._executing_jobs.discard(job.id)

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

        Supports targeting:
        - device: single device via target_device_id (backward compat)
        - artwork: all devices in an artwork via target_id
        - exhibition: all devices in an exhibition via target_id

        Returns:
            Tuple of (success, error_message)
        """
        if not self.orchestrator:
            return False, "Orchestrator not available"

        target_type = job.target_type or "device"
        action_type = job.action_type

        # Determine target ID based on target_type
        if target_type == "device":
            if not job.target_device_id:
                return False, "No target_device_id specified for device job"
            target_id = str(job.target_device_id)
        else:
            # artwork or exhibition
            if not job.target_id:
                return False, f"No target_id specified for {target_type} job"
            target_id = str(job.target_id)

            # Check if schedules are enabled for the target
            schedules_enabled = await self._check_schedules_enabled(target_type, job.target_id)
            if not schedules_enabled:
                logger.debug(
                    "Skipping job - schedules disabled for target",
                    job=job.name,
                    target_type=target_type,
                    target_id=target_id,
                )
                return True, None  # Return success to not trigger failure tracking

        if action_type in ("on", "off"):
            # Use orchestrator for ON/OFF commands
            result = await self.orchestrator.execute_control_command(
                target_type=target_type,
                target_id=target_id,
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
            # Execute shell action (only for device target)
            if target_type != "device":
                return False, "Shell actions only available for device targets"
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
        from gallerycontrol.devices.shell_manager import replace_credential_placeholders

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
            # Kill the subprocess to prevent zombie processes
            try:
                proc.kill()
                await proc.wait()
            except (ProcessLookupError, OSError):
                pass  # Process already terminated or OS error during cleanup
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)

    async def _check_schedules_enabled(
        self, target_type: str, target_id: UUID
    ) -> bool:
        """Check if schedules are enabled for the target artwork/exhibition.

        Args:
            target_type: 'artwork' or 'exhibition'
            target_id: UUID of the target

        Returns:
            True if schedules are enabled, False otherwise
        """
        async with self.db_manager.session() as session:
            if target_type == "artwork":
                stmt = select(Artwork.schedules_enabled).where(Artwork.id == target_id)
            elif target_type == "exhibition":
                stmt = select(Exhibition.schedules_enabled).where(Exhibition.id == target_id)
            else:
                return True  # Unknown type, allow execution

            result = await session.execute(stmt)
            enabled = result.scalar_one_or_none()

            # If not found, assume disabled (safe default)
            return enabled if enabled is not None else False

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
        now = utc_now()

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

                # Handle one-shot vs recurring jobs differently
                if job.run_once:
                    # One-shot job: mark as executed and disable
                    job.executed_at = now
                    job.enabled = False
                    # Don't need to update next_run_at for one-shot
                    logger.debug(
                        "One-shot job completed",
                        job=job.name,
                        success=success,
                    )
                else:
                    # Recurring job: calculate next run time
                    if job.cron_expression:
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
            scheduled_at=utc_now(),
            success=False,
            error_message=error,
            duration_ms=0,
        )

    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """Calculate the next run time for a cron expression.

        Cron fields are interpreted in LOCAL_TZ (Europe/Berlin) so that
        `30 9 * * *` means 09:30 local wall-clock, not 09:30 UTC.

        Args:
            cron_expression: Standard cron expression

        Returns:
            Next run time in UTC (naive datetime for DB compatibility)
        """
        now_local = datetime.now(LOCAL_TZ)
        cron = croniter(cron_expression, now_local)
        next_run_local = cron.get_next(datetime)

        return next_run_local.astimezone(timezone.utc).replace(tzinfo=None)

    async def _update_all_next_runs(self) -> None:
        """Update next_run_at for all enabled recurring jobs on startup.

        One-shot jobs keep their original next_run_at (set at creation time).
        """
        try:
            async with self.db_manager.session() as session:
                # Only update recurring jobs (not one-shots)
                stmt = (
                    select(ScheduledJob)
                    .where(ScheduledJob.enabled == True)
                    .where(ScheduledJob.run_once == False)
                    .where(ScheduledJob.cron_expression != None)
                )
                result = await session.execute(stmt)
                jobs = result.scalars().all()

                for job in jobs:
                    job.next_run_at = self._calculate_next_run(job.cron_expression)

                logger.info("Updated next_run_at for recurring jobs", count=len(jobs))

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
            {
                "name": "Memory Cleanup",
                "task_name": "memory_cleanup",
                "cron_expression": "0 * * * *",  # Every hour at :00
                "task_config": {},
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
                    "run_once": job.run_once,
                    "target_type": job.target_type,
                    "target_id": str(job.target_id) if job.target_id else None,
                    "task_name": job.task_name,
                    "action_type": job.action_type,
                    "enabled": job.enabled,
                    "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                    "last_success": job.last_success,
                    "last_error": job.last_error,
                    "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
                    "executed_at": job.executed_at.isoformat() if job.executed_at else None,
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
        # First, check the job exists and isn't circuit-open
        async with self.db_manager.session() as session:
            stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                return False

            if job.circuit_open:
                return False

        # Check if already executing (outside session to avoid nesting)
        async with self._job_lock:
            if job_id in self._executing_jobs:
                return False
            self._executing_jobs.add(job_id)

        try:
            # Re-fetch job with fresh session, then execute outside session
            # (_execute_job and _record_execution manage their own sessions)
            async with self.db_manager.session() as session:
                stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

            if job:
                await self._execute_job(job)
            return True
        except Exception as e:
            logger.error("Error triggering job", job_id=str(job_id), error=str(e))
            await self._record_failure(job_id, str(e))
            return False
        finally:
            async with self._job_lock:
                self._executing_jobs.discard(job_id)

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
            job.next_run_at = utc_now()

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

        Cron fields are interpreted in LOCAL_TZ (Europe/Berlin); results are
        converted to UTC for API responses.

        Returns:
            List of next run times in UTC (timezone-aware for API responses)
        """
        now_local = datetime.now(LOCAL_TZ)
        cron = croniter(cron_expression, now_local)
        runs = []

        for _ in range(count):
            next_run_local = cron.get_next(datetime)
            runs.append(next_run_local.astimezone(timezone.utc))

        return runs

    # === One-Shot Task Scheduling ===

    async def schedule_once(
        self,
        name: str,
        job_type: str,
        run_at: datetime,
        target_type: str = "device",
        target_id: Optional[str] = None,
        target_device_id: Optional[str] = None,
        action_type: Optional[str] = None,
        task_name: Optional[str] = None,
        task_config: Optional[dict] = None,
        dedupe_key: Optional[str] = None,
    ) -> Optional[UUID]:
        """Schedule a one-shot task to run at a specific time.

        Args:
            name: Job name (also used as dedupe_key if dedupe_key not provided)
            job_type: 'system' or 'device'
            run_at: When to execute (UTC datetime)
            target_type: 'device', 'artwork', or 'exhibition'
            target_id: Generic target UUID for artwork/exhibition
            target_device_id: Specific device UUID (for device target)
            action_type: 'on', 'off' for device jobs
            task_name: Task name for system jobs
            task_config: Task configuration for system jobs
            dedupe_key: Optional key for deduplication (defaults to name)

        Returns:
            Job UUID if created, None if dedupe_key already has a pending job
        """
        # Use name as dedupe_key if not provided
        check_name = dedupe_key or name

        try:
            async with self.db_manager.session() as session:
                # Check for existing pending one-shot job with same name (deduplication)
                stmt = select(ScheduledJob).where(
                    and_(
                        ScheduledJob.name == check_name,
                        ScheduledJob.run_once == True,
                        ScheduledJob.executed_at == None,
                    )
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(
                        "One-shot job already pending, skipping",
                        name=check_name,
                        existing_id=str(existing.id),
                    )
                    return None

                # Convert to UTC naive datetime for DB storage
                if run_at.tzinfo is None:
                    # Naive datetime: assume it's in local timezone
                    run_at = run_at.replace(tzinfo=LOCAL_TZ)
                run_at = run_at.astimezone(timezone.utc).replace(tzinfo=None)

                # Create the one-shot job
                job_id = uuid4()
                job = ScheduledJob(
                    id=job_id,
                    name=name,
                    job_type=job_type,
                    cron_expression=None,  # One-shots don't need cron
                    run_once=True,
                    target_type=target_type,
                    target_id=UUID(target_id) if target_id else None,
                    target_device_id=UUID(target_device_id) if target_device_id else None,
                    action_type=action_type,
                    task_name=task_name,
                    task_config=task_config,
                    enabled=True,
                    next_run_at=run_at,
                )
                session.add(job)

                logger.info(
                    "Scheduled one-shot job",
                    name=name,
                    job_type=job_type,
                    run_at=run_at.isoformat(),
                    target_type=target_type,
                )

                return job_id

        except Exception as e:
            logger.error("Error scheduling one-shot job", name=name, error=str(e))
            return None

    async def cancel_one_shot(self, name: str) -> bool:
        """Cancel a pending one-shot job by name.

        Args:
            name: Job name to cancel

        Returns:
            True if cancelled, False if not found
        """
        try:
            async with self.db_manager.session() as session:
                stmt = select(ScheduledJob).where(
                    and_(
                        ScheduledJob.name == name,
                        ScheduledJob.run_once == True,
                        ScheduledJob.executed_at == None,
                    )
                )
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if not job:
                    return False

                await session.delete(job)
                logger.info("Cancelled one-shot job", name=name)
                return True

        except Exception as e:
            logger.error("Error cancelling one-shot job", name=name, error=str(e))
            return False
