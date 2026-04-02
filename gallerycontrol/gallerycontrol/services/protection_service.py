# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Artwork protection service - prevents overuse of artworks.

Implements protection mechanisms for sensor-triggered artworks:
1. Time Slice Windows - Budget-based limits (e.g., max 7 min per 15-min chunk)
2. Runtime + Cooldown - Session limits (e.g., max 2:30 continuous, then 2 min rest)
3. Sensor Integration - Handle external sensor ON/OFF signals with proper gate checks

Hierarchy:
1. Web UI / Scheduler (KING) -> Controls opening hours, sets accepting_triggers
2. Protection Service -> Manages runtime WHILE open for business
3. Sensor (Lidar) -> Triggers within allowed bounds
"""

import asyncio
from datetime import datetime, timedelta

from gallerycontrol.utils.datetime_utils import utc_now
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from gallerycontrol.database.models import Artwork, ArtworkProtectionState
from gallerycontrol.utils.datetime_utils import ensure_utc
from gallerycontrol.utils.duration import format_duration, parse_duration
from gallerycontrol.utils.logging import get_logger

if TYPE_CHECKING:
    from gallerycontrol.database.connection import DatabaseManager
    from gallerycontrol.orchestrator.command_orchestrator import CommandOrchestrator
    from gallerycontrol.services.sse_broadcaster import SSEBroadcaster

logger = get_logger(__name__)


def validate_protection_config(config: dict) -> List[str]:
    """Validate protection config for logical consistency.

    Returns list of error messages (empty if valid).
    """
    errors = []

    if not config:
        return errors

    # Parse durations
    try:
        slice_budget = _get_slice_budget_seconds(config)
        max_runtime = parse_duration(config.get("max_runtime", 0))
        min_runtime = parse_duration(config.get("min_runtime", 0))
        force_completion = config.get("force_completion", False)

        if min_runtime > slice_budget > 0:
            errors.append(
                f"min_runtime ({format_duration(min_runtime)}) exceeds slice_budget "
                f"({format_duration(slice_budget)}) - artwork can never start"
            )

        if min_runtime > max_runtime > 0:
            errors.append(
                f"min_runtime ({format_duration(min_runtime)}) exceeds max_runtime "
                f"({format_duration(max_runtime)}) - contradiction"
            )

        if force_completion and max_runtime > slice_budget > 0:
            errors.append(
                f"force_completion with max_runtime ({format_duration(max_runtime)}) > "
                f"slice_budget ({format_duration(slice_budget)}) - will always exceed budget"
            )

        if force_completion and max_runtime <= 0:
            errors.append("force_completion requires max_runtime > 0")

    except ValueError as e:
        errors.append(f"Invalid duration format: {e}")

    return errors


def _get_slice_budget_seconds(config: dict) -> int:
    """Get slice budget in seconds from config (supports both formats)."""
    # New format: slice_budget as duration string
    if "slice_budget" in config:
        return parse_duration(config["slice_budget"])

    # Legacy format: time_slices array
    time_slices = config.get("time_slices", [])
    if time_slices:
        # Return first slice's max (in minutes -> seconds)
        return time_slices[0].get("max", 0) * 60

    return 0


def _get_slice_window_minutes(config: dict) -> int:
    """Get slice window in minutes from config (supports both formats)."""
    # New format: slice_window as duration string
    if "slice_window" in config:
        return parse_duration(config["slice_window"]) // 60

    # Legacy format: time_slices array
    time_slices = config.get("time_slices", [])
    if time_slices:
        return time_slices[0].get("window", 15)

    return 15  # Default 15 minutes


class ProtectionService:
    """Manages artwork protection rules and state.

    Protection config schema (on Artwork.protection_config):
        New simplified format:
        {
            "slice_window": "15m",       # Time window duration
            "slice_budget": "7m",        # Max runtime per window
            "max_runtime": "2m30s",      # Max continuous runtime
            "min_runtime": "30s",        # Min runtime per activation
            "cooldown": "2m",            # Rest time after forced stop
            "force_completion": false,   # Ignore OFF until max_runtime
        }

        Legacy format (still supported):
        {
            "time_slices": [
                {"window": 15, "max": 7},   # max 7 min per 15-min chunk
            ],
            "max_runtime": 150,        # seconds continuous runtime
            "cooldown": 120,           # seconds forced rest after max_runtime
            "force_completion": false, # if true, ignore OFF until max_runtime
            "min_budget_to_start": 60  # won't start if budget < this (seconds)
        }
    """

    def __init__(
        self,
        db_manager: "DatabaseManager",
        sse_broadcaster: Optional["SSEBroadcaster"] = None,
        config: Optional[dict] = None,
    ):
        self.db_manager = db_manager
        self.sse_broadcaster = sse_broadcaster
        self.config = config or {}

        # In-memory state for fast checks
        self._states: Dict[UUID, dict] = {}  # artwork_id -> state dict
        self._configs: Dict[UUID, dict] = {}  # artwork_id -> protection config
        self._enabled_artworks: set[UUID] = set()  # artworks with timeslice_enabled=True

        # Per-artwork locks to prevent race conditions
        self._artwork_locks: Dict[UUID, asyncio.Lock] = {}

        # Orchestrator for sending OFF commands
        self._orchestrator: Optional["CommandOrchestrator"] = None

        # Enforcement loop
        self._enforcement_task: Optional[asyncio.Task] = None
        self._running = False

        # Interval for enforcement checks (how often to check max_runtime)
        self._enforcement_interval = self.config.get(
            "protection_enforcement_interval_seconds", 5
        )

    def _get_artwork_lock(self, artwork_id: UUID) -> asyncio.Lock:
        """Get or create lock for artwork to prevent race conditions."""
        if artwork_id not in self._artwork_locks:
            self._artwork_locks[artwork_id] = asyncio.Lock()
        return self._artwork_locks[artwork_id]

    def set_orchestrator(self, orchestrator: "CommandOrchestrator") -> None:
        """Set the orchestrator for sending OFF commands during force stop."""
        self._orchestrator = orchestrator

    def get_config(self, artwork_id: UUID) -> dict | None:
        """Get protection config for an artwork (from YAML/DB loaded configs)."""
        return self._configs.get(artwork_id)

    async def start(self) -> None:
        """Start the protection service and load state from database."""
        logger.info("Starting ProtectionService")
        await self._load_state_from_db()
        self._running = True
        self._enforcement_task = asyncio.create_task(self._enforcement_loop())
        logger.info(
            "ProtectionService started",
            protected_artworks=len(self._configs),
        )

    async def stop(self) -> None:
        """Stop the protection service and persist state."""
        logger.info("Stopping ProtectionService")
        self._running = False
        if self._enforcement_task:
            self._enforcement_task.cancel()
            try:
                await self._enforcement_task
            except asyncio.CancelledError:
                pass
        await self._persist_all_states()
        logger.info("ProtectionService stopped")

    async def _load_state_from_db(self) -> None:
        """Load protection configs and states from database."""
        async with self.db_manager.session() as session:
            # Load all artworks with protection_config
            stmt = (
                select(Artwork)
                .where(Artwork.protection_config.isnot(None))
                .options(selectinload(Artwork.protection_state))
            )
            result = await session.execute(stmt)
            artworks = result.scalars().all()

            for artwork in artworks:
                self._configs[artwork.id] = artwork.protection_config

                # Track enabled status
                if artwork.timeslice_enabled:
                    self._enabled_artworks.add(artwork.id)

                if artwork.protection_state:
                    state = artwork.protection_state
                    # Keep datetimes naive for consistent comparison with utcnow()
                    started_at = state.started_at
                    if started_at and started_at.tzinfo is not None:
                        started_at = started_at.replace(tzinfo=None)
                    cooldown_until = state.cooldown_until
                    if cooldown_until and cooldown_until.tzinfo is not None:
                        cooldown_until = cooldown_until.replace(tzinfo=None)
                    self._states[artwork.id] = {
                        "is_running": state.is_running,
                        "started_at": started_at,
                        "cooldown_until": cooldown_until,
                        "time_slice_usage": state.time_slice_usage or {},
                        "last_window_reset": state.last_window_reset or {},
                        "desired_state": getattr(state, "desired_state", "off") or "off",
                    }
                else:
                    # Initialize default state
                    self._states[artwork.id] = {
                        "is_running": False,
                        "started_at": None,
                        "cooldown_until": None,
                        "time_slice_usage": {},
                        "last_window_reset": {},
                        "desired_state": "off",
                    }

    async def _persist_all_states(self) -> None:
        """Persist all in-memory states to database."""
        for artwork_id, state in self._states.items():
            await self._persist_state(artwork_id, state)

    async def _persist_state(self, artwork_id: UUID, state: dict) -> None:
        """Persist state for a single artwork."""
        try:
            async with self.db_manager.session() as session:
                # Check if state exists
                stmt = select(ArtworkProtectionState).where(
                    ArtworkProtectionState.artwork_id == artwork_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    stmt = (
                        update(ArtworkProtectionState)
                        .where(ArtworkProtectionState.artwork_id == artwork_id)
                        .values(
                            is_running=state["is_running"],
                            started_at=state["started_at"],
                            cooldown_until=state["cooldown_until"],
                            time_slice_usage=state["time_slice_usage"],
                            last_window_reset=state["last_window_reset"],
                            desired_state=state.get("desired_state", "off"),
                            updated_at=utc_now(),
                        )
                    )
                    await session.execute(stmt)
                else:
                    # Create new
                    new_state = ArtworkProtectionState(
                        artwork_id=artwork_id,
                        is_running=state["is_running"],
                        started_at=state["started_at"],
                        cooldown_until=state["cooldown_until"],
                        time_slice_usage=state["time_slice_usage"],
                        last_window_reset=state["last_window_reset"],
                        desired_state=state.get("desired_state", "off"),
                    )
                    session.add(new_state)

        except Exception as e:
            logger.error(
                "Failed to persist protection state",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )

    def _get_time_slice_budget(
        self, artwork_id: UUID, window_minutes: int, *, readonly: bool = False
    ) -> Tuple[int, int]:
        """Get remaining budget for a time slice window.

        Args:
            artwork_id: The artwork UUID
            window_minutes: Window size in minutes
            readonly: If True, don't modify state (for status checks).
                     If False, update state on window rollover.

        Returns:
            (used_seconds, max_seconds)
        """
        config = self._configs.get(artwork_id, {})
        state = self._states.get(artwork_id, {})

        # Get max budget based on config format
        max_seconds = _get_slice_budget_seconds(config)
        if max_seconds == 0:
            return (0, 0)

        # Check if window needs reset
        usage = state.get("time_slice_usage", {})
        last_reset = state.get("last_window_reset", {})
        window_key = str(window_minutes)

        used_seconds = usage.get(window_key, 0)
        last_reset_str = last_reset.get(window_key)

        if last_reset_str:
            last_reset_dt = datetime.fromisoformat(last_reset_str)
            window_start = self._get_window_start(window_minutes)
            if last_reset_dt < window_start:
                # Window has rolled over, reset usage
                used_seconds = 0
                # Only update state if not readonly
                if not readonly:
                    usage[window_key] = 0
                    last_reset[window_key] = window_start.isoformat()
                    state["time_slice_usage"] = usage
                    state["last_window_reset"] = last_reset

        return (used_seconds, max_seconds)

    def _get_window_start(self, window_minutes: int) -> datetime:
        """Get the start of the current time window."""
        now = utc_now()
        # Align to window boundaries (e.g., 15-min chunks align to :00, :15, :30, :45)
        minutes_since_midnight = now.hour * 60 + now.minute
        window_start_minute = (minutes_since_midnight // window_minutes) * window_minutes
        return now.replace(
            hour=window_start_minute // 60,
            minute=window_start_minute % 60,
            second=0,
            microsecond=0,
        )

    def _get_window_end(self, window_minutes: int) -> datetime:
        """Get the end of the current time window."""
        return self._get_window_start(window_minutes) + timedelta(minutes=window_minutes)

    def _get_min_budget_across_slices(self, artwork_id: UUID, *, readonly: bool = False) -> int:
        """Get the minimum remaining budget across all time slices.

        Args:
            artwork_id: The artwork UUID
            readonly: If True, don't modify state on window rollover

        Returns the smallest remaining budget in seconds.
        """
        config = self._configs.get(artwork_id, {})

        # Get window minutes (supports both formats)
        window_minutes = _get_slice_window_minutes(config)
        if window_minutes <= 0:
            return float("inf")  # No limits

        used, max_sec = self._get_time_slice_budget(artwork_id, window_minutes, readonly=readonly)
        if max_sec == 0:
            return float("inf")  # No limits

        return max(0, max_sec - used)

    def _get_current_runtime(self, state: dict) -> int:
        """Get current runtime in seconds if running, else 0."""
        if not state.get("is_running") or not state.get("started_at"):
            return 0
        return int((utc_now() - state["started_at"]).total_seconds())

    def _get_min_runtime(self, config: dict) -> int:
        """Get min_runtime in seconds (supports both formats)."""
        # New format
        if "min_runtime" in config:
            return parse_duration(config["min_runtime"])
        # Legacy format: min_budget_to_start was used similarly
        return parse_duration(config.get("min_budget_to_start", 0))

    async def check_can_start(
        self, artwork_id: UUID, *, readonly: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Check if an artwork can start running.

        Args:
            artwork_id: The artwork UUID
            readonly: If True, don't modify state (for status checks)

        Returns:
            (allowed, reason) - reason is None if allowed, otherwise explains why blocked
        """
        # Check if timeslice feature is enabled for this artwork
        if artwork_id not in self._enabled_artworks:
            return (True, None)  # Feature disabled, always allowed

        # Check if artwork has protection config
        if artwork_id not in self._configs:
            return (True, None)  # No protection, always allowed

        config = self._configs[artwork_id]
        state = self._states.get(artwork_id, {})

        # Check cooldown
        cooldown_until = state.get("cooldown_until")
        if cooldown_until and utc_now() < cooldown_until:
            remaining = (cooldown_until - utc_now()).total_seconds()
            return (False, f"Cooldown active ({format_duration(remaining)} remaining)")

        # Check time slice budgets
        min_budget = self._get_min_budget_across_slices(artwork_id, readonly=readonly)
        min_runtime = self._get_min_runtime(config)
        force_completion = config.get("force_completion", False)

        if force_completion:
            # In force_completion mode, need enough budget for full max_runtime
            max_runtime = parse_duration(config.get("max_runtime", 0))
            need = max_runtime
        else:
            need = min_runtime

        if min_budget < need:
            # Check if we can bridge into the next window
            # If time until rollover < needed runtime, we'll cross into fresh budget
            window_minutes = _get_slice_window_minutes(config)
            if window_minutes > 0:
                window_end = self._get_window_end(window_minutes)
                time_to_rollover = (window_end - utc_now()).total_seconds()

                if time_to_rollover < need:
                    # We're close enough to rollover - allow bridging into new budget
                    logger.debug(
                        "Allowing start via window bridging",
                        artwork_id=str(artwork_id)[:8],
                        budget_remaining=min_budget,
                        time_to_rollover=int(time_to_rollover),
                        needed=need,
                    )
                    return (True, None)

            return (
                False,
                f"Insufficient budget ({format_duration(min_budget)} < {format_duration(need)} required)",
            )

        return (True, None)

    async def handle_sensor_signal(
        self,
        artwork_id: UUID,
        desired_state: Literal["on", "off"],
    ) -> Tuple[bool, Optional[str]]:
        """Handle sensor ON/OFF signal.

        This is the main entry point for external sensor triggers (lidar, motion, etc.).
        The sensor handles visitor detection and debouncing; this service handles
        budget tracking, runtime limits, and device control.

        IMPORTANT: Does NOT update state directly for ON/OFF execution.
        Delegates to orchestrator, state updated via notify_* callbacks.

        Args:
            artwork_id: The artwork UUID
            desired_state: "on" or "off"

        Returns:
            (success, reason_if_blocked)
        """
        async with self._get_artwork_lock(artwork_id):
            return await self._handle_sensor_signal_locked(artwork_id, desired_state)

    async def _handle_sensor_signal_locked(
        self,
        artwork_id: UUID,
        desired_state: Literal["on", "off"],
    ) -> Tuple[bool, Optional[str]]:
        """Handle sensor signal with lock held."""
        # Check if timeslice feature is enabled
        if artwork_id not in self._enabled_artworks:
            return (False, "Protection not enabled for this artwork")

        if artwork_id not in self._configs:
            return (False, "No protection config for this artwork")

        config = self._configs[artwork_id]
        state = self._states.get(artwork_id, {})

        # Always update desired_state (intent tracking)
        state["desired_state"] = desired_state
        self._states[artwork_id] = state

        if desired_state == "on":
            return await self._handle_sensor_on(artwork_id, config, state)
        else:
            return await self._handle_sensor_off(artwork_id, config, state)

    async def _handle_sensor_on(
        self,
        artwork_id: UUID,
        config: dict,
        state: dict,
    ) -> Tuple[bool, Optional[str]]:
        """Handle sensor ON signal."""
        # If already running, nothing to do
        if state.get("is_running"):
            return (True, None)

        # Check if artwork is accepting triggers (gate from web/scheduler)
        accepting = await self._is_accepting_triggers(artwork_id)
        if not accepting:
            return (False, "Artwork not accepting triggers")

        # Check cooldown
        cooldown_until = state.get("cooldown_until")
        if cooldown_until and utc_now() < cooldown_until:
            remaining = (cooldown_until - utc_now()).total_seconds()
            return (False, f"Cooldown active ({format_duration(remaining)} remaining)")

        # Check budget >= min_runtime
        min_budget = self._get_min_budget_across_slices(artwork_id)
        min_runtime = self._get_min_runtime(config)
        force_completion = config.get("force_completion", False)

        if force_completion:
            # Need enough for full max_runtime
            max_runtime = parse_duration(config.get("max_runtime", 0))
            need = max_runtime
        else:
            need = min_runtime

        if min_budget < need:
            # Check if we can bridge into the next window
            window_minutes = _get_slice_window_minutes(config)
            if window_minutes > 0:
                window_end = self._get_window_end(window_minutes)
                time_to_rollover = (window_end - utc_now()).total_seconds()

                if time_to_rollover < need:
                    # Allow bridging - we'll cross into fresh budget
                    logger.debug(
                        "Sensor ON allowed via window bridging",
                        artwork_id=str(artwork_id)[:8],
                        budget_remaining=min_budget,
                        time_to_rollover=int(time_to_rollover),
                    )
                else:
                    return (
                        False,
                        f"Insufficient budget ({format_duration(min_budget)} < {format_duration(need)} required)",
                    )
            else:
                return (
                    False,
                    f"Insufficient budget ({format_duration(min_budget)} < {format_duration(need)} required)",
                )

        # Execute via orchestrator
        if not self._orchestrator:
            logger.warning(
                "No orchestrator connected - cannot execute sensor ON",
                artwork_id=str(artwork_id)[:8],
            )
            return (False, "No orchestrator connected")

        try:
            result = await self._orchestrator.execute_control_command(
                target_type="artwork",
                target_id=str(artwork_id),
                command="on",
                source="sensor",
            )

            if result.get("success") and result.get("devices_successful", 0) > 0:
                logger.info(
                    "Sensor ON executed successfully",
                    artwork_id=str(artwork_id)[:8],
                    devices_successful=result.get("devices_successful", 0),
                )
                return (True, None)
            elif result.get("blocked"):
                return (False, result.get("reason", "Blocked by protection"))
            else:
                return (False, result.get("error", "Command failed"))

        except Exception as e:
            logger.error(
                "Failed to execute sensor ON",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )
            return (False, f"Execution error: {str(e)}")

    async def _handle_sensor_off(
        self,
        artwork_id: UUID,
        config: dict,
        state: dict,
    ) -> Tuple[bool, Optional[str]]:
        """Handle sensor OFF signal.

        OFF signals are always allowed even when accepting_triggers=False
        (we don't want to trap devices ON).
        """
        # If not running, nothing to do
        if not state.get("is_running"):
            return (True, None)

        # Check force_completion mode
        if config.get("force_completion", False):
            max_runtime = parse_duration(config.get("max_runtime", 0))
            current_runtime = self._get_current_runtime(state)
            if current_runtime < max_runtime:
                return (False, f"force_completion active ({format_duration(max_runtime - current_runtime)} remaining)")

        # Check min_runtime
        min_runtime = self._get_min_runtime(config)
        current_runtime = self._get_current_runtime(state)
        if current_runtime < min_runtime:
            remaining = min_runtime - current_runtime
            return (False, f"min_runtime not reached ({format_duration(remaining)} remaining)")

        # Execute via orchestrator
        if not self._orchestrator:
            logger.warning(
                "No orchestrator connected - cannot execute sensor OFF",
                artwork_id=str(artwork_id)[:8],
            )
            return (False, "No orchestrator connected")

        try:
            result = await self._orchestrator.execute_control_command(
                target_type="artwork",
                target_id=str(artwork_id),
                command="off",
                source="sensor",
            )

            if result.get("success") and result.get("devices_successful", 0) > 0:
                logger.info(
                    "Sensor OFF executed successfully",
                    artwork_id=str(artwork_id)[:8],
                    devices_successful=result.get("devices_successful", 0),
                )
                return (True, None)
            else:
                return (False, result.get("error", "Command failed"))

        except Exception as e:
            logger.error(
                "Failed to execute sensor OFF",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )
            return (False, f"Execution error: {str(e)}")

    async def _is_accepting_triggers(self, artwork_id: UUID) -> bool:
        """Check if artwork is accepting triggers (gate from web/scheduler)."""
        try:
            async with self.db_manager.session() as session:
                stmt = select(Artwork.accepting_triggers).where(Artwork.id == artwork_id)
                result = await session.execute(stmt)
                row = result.first()
                return row[0] if row else False
        except Exception as e:
            logger.error(
                "Failed to check accepting_triggers",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )
            return False

    async def notify_started(self, artwork_id: UUID, source: str = "unknown") -> None:
        """Notify that an artwork has started running.

        Called by orchestrator after successful ON command.
        Idempotent: if already running, does not overwrite started_at.

        Args:
            artwork_id: The artwork UUID
            source: Command source (web, fast, scheduler, sensor, protection)
        """
        if artwork_id not in self._configs:
            return

        if artwork_id not in self._states:
            self._states[artwork_id] = {
                "is_running": False,
                "started_at": None,
                "cooldown_until": None,
                "time_slice_usage": {},
                "last_window_reset": {},
                "desired_state": "off",
            }

        state = self._states[artwork_id]

        # Idempotent: don't overwrite started_at if already running
        if state.get("is_running"):
            logger.debug(
                "notify_started called but already running (idempotent)",
                artwork_id=str(artwork_id)[:8],
                source=source,
            )
            return

        state["is_running"] = True
        state["started_at"] = utc_now()

        # For sensor source, desired_state should already be "on" from handle_sensor_signal
        # For other sources, we don't update desired_state (it tracks sensor intent only)

        logger.info(
            "Artwork started running (protected)",
            artwork_id=str(artwork_id)[:8],
            source=source,
        )

        # Broadcast status update
        await self._broadcast_status(artwork_id)

    async def notify_stopped(self, artwork_id: UUID, source: str = "unknown") -> None:
        """Notify that an artwork has stopped running.

        Called by orchestrator after successful OFF command.
        Cooldown is ONLY applied on forced stop (protection source).

        Args:
            artwork_id: The artwork UUID
            source: Command source (web, fast, scheduler, sensor, protection)
        """
        if artwork_id not in self._configs:
            return

        state = self._states.get(artwork_id)
        if not state or not state.get("is_running"):
            return

        # Calculate runtime and update budgets
        started_at = state.get("started_at")
        runtime_seconds = 0
        if started_at:
            runtime_seconds = (utc_now() - started_at).total_seconds()
            await self._update_time_slice_usage(artwork_id, int(runtime_seconds))

        state["is_running"] = False
        state["started_at"] = None

        # Cooldown ONLY on forced stop (protection source)
        config = self._configs.get(artwork_id, {})
        if source == "protection":
            cooldown_seconds = parse_duration(config.get("cooldown", 0))
            if cooldown_seconds > 0:
                state["cooldown_until"] = utc_now() + timedelta(
                    seconds=cooldown_seconds
                )
                logger.info(
                    "Cooldown started after forced stop",
                    artwork_id=str(artwork_id)[:8],
                    cooldown_seconds=cooldown_seconds,
                )

        logger.info(
            "Artwork stopped running (protected)",
            artwork_id=str(artwork_id)[:8],
            runtime_seconds=int(runtime_seconds),
            source=source,
        )

        # Persist state on stop
        await self._persist_state(artwork_id, state)

        # Broadcast status update
        await self._broadcast_status(artwork_id)

    async def _update_time_slice_usage(
        self, artwork_id: UUID, runtime_seconds: int
    ) -> None:
        """Update time slice usage after a run."""
        config = self._configs.get(artwork_id, {})
        state = self._states.get(artwork_id, {})

        window_minutes = _get_slice_window_minutes(config)
        if window_minutes <= 0:
            return

        usage = state.get("time_slice_usage", {})
        last_reset = state.get("last_window_reset", {})
        window_key = str(window_minutes)
        window_start = self._get_window_start(window_minutes)

        # Check if window has rolled over
        last_reset_str = last_reset.get(window_key)
        if last_reset_str:
            last_reset_dt = datetime.fromisoformat(last_reset_str)
            if last_reset_dt < window_start:
                # Reset usage for new window
                usage[window_key] = 0

        # Add runtime to usage
        current_usage = usage.get(window_key, 0)
        usage[window_key] = current_usage + runtime_seconds
        last_reset[window_key] = window_start.isoformat()

        state["time_slice_usage"] = usage
        state["last_window_reset"] = last_reset

    async def _enforcement_loop(self) -> None:
        """Background loop to enforce max_runtime limits and check cooldown expiry."""
        while self._running:
            try:
                await asyncio.sleep(self._enforcement_interval)
                await self._check_all_runtimes()
                await self._check_cooldown_expiry()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in protection enforcement loop", error=str(e))

    async def _check_all_runtimes(self) -> None:
        """Check all running artworks for max_runtime and budget violations."""
        now = utc_now()

        for artwork_id, state in list(self._states.items()):
            # Skip artworks where timeslice feature is disabled
            if artwork_id not in self._enabled_artworks:
                continue

            if not state.get("is_running"):
                continue

            config = self._configs.get(artwork_id, {})
            started_at = state.get("started_at")
            if not started_at:
                continue

            runtime = (now - started_at).total_seconds()

            # Check max_runtime limit
            max_runtime = parse_duration(config.get("max_runtime", 0))
            if max_runtime > 0 and runtime >= max_runtime:
                # Acquire lock before force stopping
                async with self._get_artwork_lock(artwork_id):
                    # Re-check conditions under lock
                    if state.get("is_running") and state.get("started_at"):
                        await self._force_stop_locked(artwork_id, "max_runtime_exceeded")
                continue

            # Check time slice budget exhaustion
            window_minutes = _get_slice_window_minutes(config)
            max_seconds = _get_slice_budget_seconds(config)

            if window_minutes > 0 and max_seconds > 0:
                used, _ = self._get_time_slice_budget(artwork_id, window_minutes)
                projected_used = used + int(runtime)

                if projected_used >= max_seconds:
                    # Acquire lock before force stopping
                    async with self._get_artwork_lock(artwork_id):
                        # Re-check conditions under lock
                        if state.get("is_running") and state.get("started_at"):
                            await self._force_stop_locked(
                                artwork_id,
                                f"budget_exhausted_{window_minutes}m_window"
                            )

    async def _check_cooldown_expiry(self) -> None:
        """Check for cooldown expiry and auto-resume if desired_state is "on"."""
        now = utc_now()

        for artwork_id, state in list(self._states.items()):
            if artwork_id not in self._enabled_artworks:
                continue

            cooldown_until = state.get("cooldown_until")
            if not cooldown_until or now < cooldown_until:
                continue

            # Use lock for all state modifications to prevent races with sensor handlers
            async with self._get_artwork_lock(artwork_id):
                # Re-check cooldown under lock (may have changed)
                cooldown_until = state.get("cooldown_until")
                if not cooldown_until or now < cooldown_until:
                    continue

                # Cooldown expired - clear it
                state["cooldown_until"] = None
                logger.info(
                    "Cooldown expired",
                    artwork_id=str(artwork_id)[:8],
                )

                # Check if sensor still wants "on" and we should auto-resume
                if state.get("desired_state") == "on":
                    # Check if still accepting triggers
                    accepting = await self._is_accepting_triggers(artwork_id)
                    if accepting:
                        # Check if we can turn on (recheck under lock)
                        allowed, reason = await self.check_can_start(artwork_id)
                        if allowed:
                            logger.info(
                                "Auto-resuming after cooldown (desired_state=on)",
                                artwork_id=str(artwork_id)[:8],
                            )
                            await self._turn_on_via_orchestrator(artwork_id)
                        else:
                            logger.info(
                                "Cannot auto-resume after cooldown",
                                artwork_id=str(artwork_id)[:8],
                                reason=reason,
                            )

                await self._persist_state(artwork_id, state)
                await self._broadcast_status(artwork_id)

    async def _turn_on_via_orchestrator(self, artwork_id: UUID) -> None:
        """Turn on artwork via orchestrator (for auto-resume)."""
        if not self._orchestrator:
            logger.warning(
                "No orchestrator connected - cannot auto-resume",
                artwork_id=str(artwork_id)[:8],
            )
            return

        try:
            result = await self._orchestrator.execute_control_command(
                target_type="artwork",
                target_id=str(artwork_id),
                command="on",
                source="sensor",  # Auto-resume acts like sensor
            )

            if result.get("success") and result.get("devices_successful", 0) > 0:
                logger.info(
                    "Auto-resume ON executed successfully",
                    artwork_id=str(artwork_id)[:8],
                    devices_successful=result.get("devices_successful", 0),
                )
            else:
                logger.warning(
                    "Auto-resume ON failed",
                    artwork_id=str(artwork_id)[:8],
                    error=result.get("error"),
                )

        except Exception as e:
            logger.error(
                "Failed to auto-resume",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )

    async def _force_stop_locked(self, artwork_id: UUID, reason: str) -> None:
        """Force stop an artwork and enter cooldown. MUST be called with lock held.

        This method:
        1. Updates internal tracking state
        2. Sends actual OFF commands to devices via orchestrator
        3. Broadcasts SSE event for UI updates

        Cooldown is handled in notify_stopped() when source="protection".
        Caller MUST hold self._get_artwork_lock(artwork_id).
        """
        config = self._configs.get(artwork_id, {})
        state = self._states.get(artwork_id, {})
        cooldown_seconds = parse_duration(config.get("cooldown", 0))

        # Calculate runtime for budget update
        started_at = state.get("started_at")
        if started_at:
            runtime_seconds = (utc_now() - started_at).total_seconds()
            await self._update_time_slice_usage(artwork_id, int(runtime_seconds))

        # Update state (cooldown will be set in notify_stopped via source="protection")
        state["is_running"] = False
        state["started_at"] = None
        if cooldown_seconds > 0:
            state["cooldown_until"] = utc_now() + timedelta(
                seconds=cooldown_seconds
            )

        logger.warning(
            "Force stopping artwork (protection)",
            artwork_id=str(artwork_id)[:8],
            reason=reason,
            cooldown_seconds=cooldown_seconds,
        )

        # Persist state
        await self._persist_state(artwork_id, state)

        # Send actual OFF commands to devices via orchestrator
        if self._orchestrator:
            try:
                result = await self._orchestrator.execute_control_command(
                    target_type="artwork",
                    target_id=str(artwork_id),
                    command="off",
                    source="protection",
                )
                logger.info(
                    "Protection auto-OFF completed",
                    artwork_id=str(artwork_id)[:8],
                    reason=reason,
                    devices_targeted=result.get("devices_targeted", 0),
                    devices_successful=result.get("devices_successful", 0),
                )
            except Exception as e:
                logger.error(
                    "Failed to send protection auto-OFF",
                    artwork_id=str(artwork_id)[:8],
                    error=str(e),
                )
        else:
            logger.warning(
                "No orchestrator connected - cannot send auto-OFF commands",
                artwork_id=str(artwork_id)[:8],
            )

        # Broadcast forced stop event and updated status
        await self._broadcast_forced_off(artwork_id, reason)
        await self._broadcast_status(artwork_id)

    async def _broadcast_status(self, artwork_id: UUID) -> None:
        """Broadcast protection status update via SSE."""
        if not self.sse_broadcaster:
            return

        status = await self.get_protection_status(artwork_id)
        await self.sse_broadcaster.send_protection_status(str(artwork_id), status)

    async def _broadcast_forced_off(self, artwork_id: UUID, reason: str) -> None:
        """Broadcast forced off event via SSE."""
        if not self.sse_broadcaster:
            return

        await self.sse_broadcaster.send_protection_forced_off(str(artwork_id), reason)

    async def get_protection_status(self, artwork_id: UUID) -> dict:
        """Get current protection status for an artwork."""
        # Check if protection is enabled (both config exists AND timeslice_enabled)
        if artwork_id not in self._configs or artwork_id not in self._enabled_artworks:
            return {"protected": False}

        config = self._configs[artwork_id]
        state = self._states.get(artwork_id, {})
        now = utc_now()

        # Calculate current runtime if running
        runtime_seconds = 0
        if state.get("is_running") and state.get("started_at"):
            runtime_seconds = int((now - state["started_at"]).total_seconds())

        # Check cooldown
        cooldown_active = False
        cooldown_remaining = 0
        cooldown_until = state.get("cooldown_until")
        if cooldown_until and now < cooldown_until:
            cooldown_active = True
            cooldown_remaining = int((cooldown_until - now).total_seconds())

        # Build time slice info
        window_minutes = _get_slice_window_minutes(config)
        max_seconds = _get_slice_budget_seconds(config)

        time_slice_info = None
        if window_minutes > 0 and max_seconds > 0:
            # Use readonly=True to avoid side effects on status checks
            used, max_sec = self._get_time_slice_budget(artwork_id, window_minutes, readonly=True)
            window_end = self._get_window_end(window_minutes)
            remaining = max(0, max_sec - used)

            time_slice_info = {
                "window_minutes": window_minutes,
                "used": used,
                "max": max_sec,
                "remaining": remaining,
                "remaining_formatted": format_duration(remaining),
                "resets_at": window_end.isoformat(),
                "resets_in": int((window_end - now).total_seconds()),
                "resets_in_formatted": format_duration((window_end - now).total_seconds()),
            }

        # Check if can start (readonly to avoid side effects)
        can_start, block_reason = await self.check_can_start(artwork_id, readonly=True)

        return {
            "protected": True,
            "config": {
                "slice_window": format_duration(_get_slice_window_minutes(config) * 60),
                "slice_budget": format_duration(_get_slice_budget_seconds(config)),
                "max_runtime": format_duration(parse_duration(config.get("max_runtime", 0))),
                "min_runtime": format_duration(self._get_min_runtime(config)),
                "cooldown": format_duration(parse_duration(config.get("cooldown", 0))),
                "force_completion": config.get("force_completion", False),
            },
            "state": {
                "is_running": state.get("is_running", False),
                "runtime_seconds": runtime_seconds,
                "runtime_formatted": format_duration(runtime_seconds),
                "desired_state": state.get("desired_state", "off"),
                "cooldown_active": cooldown_active,
                "cooldown_remaining": cooldown_remaining,
                "cooldown_remaining_formatted": format_duration(cooldown_remaining),
                "time_slice": time_slice_info,
                "can_start": can_start,
                "block_reason": block_reason,
            },
        }

    async def reload_config(
        self,
        artwork_id: UUID,
        protection_config: Optional[dict] = None,
        timeslice_enabled: Optional[bool] = None,
    ) -> None:
        """Reload protection config for an artwork.

        Args:
            artwork_id: The artwork UUID
            protection_config: If provided, use this config directly (avoids DB read).
                              Pass empty dict {} or None to remove protection.
            timeslice_enabled: If provided, use this value directly.

        When called without config/enabled args, reads from database.
        When called WITH config/enabled args, uses provided values directly
        (useful when called from within a transaction that hasn't committed yet).
        """
        # If config provided directly, use it (avoids transaction isolation issues)
        if protection_config is not None or timeslice_enabled is not None:
            await self._apply_config(artwork_id, protection_config, timeslice_enabled)
            return

        # Otherwise, read from database
        async with self.db_manager.session() as session:
            stmt = select(Artwork).where(Artwork.id == artwork_id)
            result = await session.execute(stmt)
            artwork = result.scalar_one_or_none()

            if artwork:
                await self._apply_config(
                    artwork_id, artwork.protection_config, artwork.timeslice_enabled
                )

    async def _apply_config(
        self,
        artwork_id: UUID,
        protection_config: Optional[dict],
        timeslice_enabled: Optional[bool],
    ) -> None:
        """Apply protection config to in-memory state."""
        # Update protection config if provided
        if protection_config:
            # Validate config
            errors = validate_protection_config(protection_config)
            if errors:
                logger.warning(
                    "Protection config validation warnings",
                    artwork_id=str(artwork_id)[:8],
                    errors=errors,
                )

            self._configs[artwork_id] = protection_config

            if artwork_id not in self._states:
                self._states[artwork_id] = {
                    "is_running": False,
                    "started_at": None,
                    "cooldown_until": None,
                    "time_slice_usage": {},
                    "last_window_reset": {},
                    "desired_state": "off",
                }
            logger.info(
                "Reloaded protection config",
                artwork_id=str(artwork_id)[:8],
            )
        elif protection_config is not None and artwork_id in self._configs:
            # protection_config explicitly set to empty/None - remove protection
            del self._configs[artwork_id]
            if artwork_id in self._states:
                del self._states[artwork_id]
            logger.info(
                "Removed protection config",
                artwork_id=str(artwork_id)[:8],
            )

        # Update enabled status independently of config changes
        if timeslice_enabled is not None:
            if timeslice_enabled:
                self._enabled_artworks.add(artwork_id)
                logger.info(
                    "Protection enabled",
                    artwork_id=str(artwork_id)[:8],
                )
            else:
                self._enabled_artworks.discard(artwork_id)
                logger.info(
                    "Protection disabled",
                    artwork_id=str(artwork_id)[:8],
                )

    def is_protected(self, artwork_id: UUID) -> bool:
        """Check if an artwork has protection enabled."""
        return artwork_id in self._configs and artwork_id in self._enabled_artworks

    def get_artwork_id_for_device(self, device) -> Optional[UUID]:
        """Get artwork ID from a device object."""
        if hasattr(device, "artwork_id"):
            return device.artwork_id
        if hasattr(device, "artwork") and device.artwork:
            return device.artwork.id
        return None
