"""Artwork protection service - prevents overuse of artworks.

Implements two protection mechanisms:
1. Time Slice Windows - Budget-based limits (e.g., max 7 min per 15-min chunk)
2. Runtime + Cooldown - Session limits (e.g., max 2:30 continuous, then 2 min rest)
"""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from mutech_control.database.models import Artwork, ArtworkProtectionState
from mutech_control.utils.logging import get_logger

if TYPE_CHECKING:
    from mutech_control.database.connection import DatabaseManager
    from mutech_control.services.sse_broadcaster import SSEBroadcaster

logger = get_logger(__name__)


class ProtectionService:
    """Manages artwork protection rules and state.

    Protection config schema (on Artwork.protection_config):
        {
            "time_slices": [
                {"window": 15, "max": 7},   # max 7 min per 15-min chunk
                {"window": 60, "max": 20},  # max 20 min per hour
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

        # Enforcement loop
        self._enforcement_task: Optional[asyncio.Task] = None
        self._running = False

        # Interval for enforcement checks (how often to check max_runtime)
        self._enforcement_interval = self.config.get(
            "protection_enforcement_interval_seconds", 5
        )

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

                if artwork.protection_state:
                    state = artwork.protection_state
                    self._states[artwork.id] = {
                        "is_running": state.is_running,
                        "started_at": state.started_at,
                        "cooldown_until": state.cooldown_until,
                        "time_slice_usage": state.time_slice_usage or {},
                        "last_window_reset": state.last_window_reset or {},
                    }
                else:
                    # Initialize default state
                    self._states[artwork.id] = {
                        "is_running": False,
                        "started_at": None,
                        "cooldown_until": None,
                        "time_slice_usage": {},
                        "last_window_reset": {},
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
                            updated_at=datetime.utcnow(),
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
                    )
                    session.add(new_state)

        except Exception as e:
            logger.error(
                "Failed to persist protection state",
                artwork_id=str(artwork_id)[:8],
                error=str(e),
            )

    def _get_time_slice_budget(
        self, artwork_id: UUID, window_minutes: int
    ) -> Tuple[int, int]:
        """Get remaining budget for a time slice window.

        Returns:
            (used_seconds, max_seconds)
        """
        config = self._configs.get(artwork_id, {})
        state = self._states.get(artwork_id, {})

        # Find the time slice config
        time_slices = config.get("time_slices", [])
        max_seconds = 0
        for ts in time_slices:
            if ts.get("window") == window_minutes:
                max_seconds = ts.get("max", 0) * 60  # Convert minutes to seconds
                break

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

        return (used_seconds, max_seconds)

    def _get_window_start(self, window_minutes: int) -> datetime:
        """Get the start of the current time window."""
        now = datetime.utcnow()
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

    def _get_min_budget_across_slices(self, artwork_id: UUID) -> int:
        """Get the minimum remaining budget across all time slices.

        Returns the smallest remaining budget in seconds.
        """
        config = self._configs.get(artwork_id, {})
        time_slices = config.get("time_slices", [])

        if not time_slices:
            return float("inf")  # No limits

        min_remaining = float("inf")
        for ts in time_slices:
            window = ts.get("window")
            if window:
                used, max_sec = self._get_time_slice_budget(artwork_id, window)
                remaining = max_sec - used
                min_remaining = min(min_remaining, remaining)

        return min_remaining if min_remaining != float("inf") else float("inf")

    async def check_can_start(
        self, artwork_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Check if an artwork can start running.

        Returns:
            (allowed, reason) - reason is None if allowed, otherwise explains why blocked
        """
        # Check if artwork has protection config
        if artwork_id not in self._configs:
            return (True, None)  # No protection, always allowed

        config = self._configs[artwork_id]
        state = self._states.get(artwork_id, {})

        # Check cooldown
        cooldown_until = state.get("cooldown_until")
        if cooldown_until and datetime.utcnow() < cooldown_until:
            remaining = (cooldown_until - datetime.utcnow()).total_seconds()
            return (False, f"Cooldown active ({int(remaining)}s remaining)")

        # Check time slice budgets
        min_budget = self._get_min_budget_across_slices(artwork_id)
        min_budget_to_start = config.get("min_budget_to_start", 0)
        force_completion = config.get("force_completion", False)

        if force_completion:
            # In force_completion mode, need enough budget for full max_runtime
            max_runtime = config.get("max_runtime", 0)
            need = max_runtime
        else:
            need = min_budget_to_start

        if min_budget < need:
            return (False, f"Insufficient budget ({int(min_budget)}s < {int(need)}s required)")

        return (True, None)

    async def notify_started(self, artwork_id: UUID) -> None:
        """Notify that an artwork has started running."""
        if artwork_id not in self._configs:
            return

        now = datetime.utcnow()
        if artwork_id not in self._states:
            self._states[artwork_id] = {
                "is_running": False,
                "started_at": None,
                "cooldown_until": None,
                "time_slice_usage": {},
                "last_window_reset": {},
            }

        state = self._states[artwork_id]
        state["is_running"] = True
        state["started_at"] = now

        logger.info(
            "Artwork started running (protected)",
            artwork_id=str(artwork_id)[:8],
        )

        # Broadcast status update
        await self._broadcast_status(artwork_id)

    async def notify_stopped(self, artwork_id: UUID) -> None:
        """Notify that an artwork has stopped running."""
        if artwork_id not in self._configs:
            return

        state = self._states.get(artwork_id)
        if not state or not state.get("is_running"):
            return

        # Calculate runtime and update budgets
        started_at = state.get("started_at")
        if started_at:
            runtime_seconds = (datetime.utcnow() - started_at).total_seconds()
            await self._update_time_slice_usage(artwork_id, int(runtime_seconds))

        state["is_running"] = False
        state["started_at"] = None

        logger.info(
            "Artwork stopped running (protected)",
            artwork_id=str(artwork_id)[:8],
            runtime_seconds=int(runtime_seconds) if started_at else 0,
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
        time_slices = config.get("time_slices", [])

        usage = state.get("time_slice_usage", {})
        last_reset = state.get("last_window_reset", {})
        now = datetime.utcnow()

        for ts in time_slices:
            window = ts.get("window")
            if not window:
                continue

            window_key = str(window)
            window_start = self._get_window_start(window)

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
        """Background loop to enforce max_runtime limits."""
        while self._running:
            try:
                await asyncio.sleep(self._enforcement_interval)
                await self._check_all_runtimes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in protection enforcement loop", error=str(e))

    async def _check_all_runtimes(self) -> None:
        """Check all running artworks for max_runtime violations."""
        now = datetime.utcnow()

        for artwork_id, state in list(self._states.items()):
            if not state.get("is_running"):
                continue

            config = self._configs.get(artwork_id, {})
            max_runtime = config.get("max_runtime")
            if not max_runtime:
                continue

            started_at = state.get("started_at")
            if not started_at:
                continue

            runtime = (now - started_at).total_seconds()
            if runtime >= max_runtime:
                await self._force_stop(artwork_id, "max_runtime_exceeded")

    async def _force_stop(self, artwork_id: UUID, reason: str) -> None:
        """Force stop an artwork and enter cooldown."""
        config = self._configs.get(artwork_id, {})
        state = self._states.get(artwork_id, {})
        cooldown_seconds = config.get("cooldown", 0)

        # Calculate runtime for budget update
        started_at = state.get("started_at")
        if started_at:
            runtime_seconds = (datetime.utcnow() - started_at).total_seconds()
            await self._update_time_slice_usage(artwork_id, int(runtime_seconds))

        # Update state
        state["is_running"] = False
        state["started_at"] = None
        if cooldown_seconds > 0:
            state["cooldown_until"] = datetime.utcnow() + timedelta(
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

        # Broadcast forced stop event
        await self._broadcast_forced_off(artwork_id, reason)

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
        if artwork_id not in self._configs:
            return {"protected": False}

        config = self._configs[artwork_id]
        state = self._states.get(artwork_id, {})
        now = datetime.utcnow()

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
        time_slices_info = []
        for ts in config.get("time_slices", []):
            window = ts.get("window")
            max_minutes = ts.get("max", 0)
            if window:
                used, max_sec = self._get_time_slice_budget(artwork_id, window)
                window_end = self._get_window_end(window)
                time_slices_info.append({
                    "window": window,
                    "used": used,
                    "max": max_sec,
                    "remaining": max(0, max_sec - used),
                    "resets_at": window_end.isoformat(),
                })

        # Check if can start
        can_start, block_reason = await self.check_can_start(artwork_id)

        return {
            "protected": True,
            "config": {
                "time_slices": config.get("time_slices", []),
                "max_runtime": config.get("max_runtime"),
                "cooldown": config.get("cooldown"),
                "force_completion": config.get("force_completion", False),
                "min_budget_to_start": config.get("min_budget_to_start", 0),
            },
            "state": {
                "is_running": state.get("is_running", False),
                "runtime_seconds": runtime_seconds,
                "cooldown_active": cooldown_active,
                "cooldown_remaining": cooldown_remaining,
                "time_slices": time_slices_info,
                "can_start": can_start,
                "block_reason": block_reason,
            },
        }

    async def reload_config(self, artwork_id: UUID) -> None:
        """Reload protection config for an artwork from database."""
        async with self.db_manager.session() as session:
            stmt = select(Artwork).where(Artwork.id == artwork_id)
            result = await session.execute(stmt)
            artwork = result.scalar_one_or_none()

            if artwork and artwork.protection_config:
                self._configs[artwork_id] = artwork.protection_config
                if artwork_id not in self._states:
                    self._states[artwork_id] = {
                        "is_running": False,
                        "started_at": None,
                        "cooldown_until": None,
                        "time_slice_usage": {},
                        "last_window_reset": {},
                    }
                logger.info(
                    "Reloaded protection config",
                    artwork_id=str(artwork_id)[:8],
                )
            elif artwork_id in self._configs:
                # Protection was removed
                del self._configs[artwork_id]
                if artwork_id in self._states:
                    del self._states[artwork_id]
                logger.info(
                    "Removed protection config",
                    artwork_id=str(artwork_id)[:8],
                )

    def is_protected(self, artwork_id: UUID) -> bool:
        """Check if an artwork has protection enabled."""
        return artwork_id in self._configs

    def get_artwork_id_for_device(self, device) -> Optional[UUID]:
        """Get artwork ID from a device object."""
        if hasattr(device, "artwork_id"):
            return device.artwork_id
        if hasattr(device, "artwork") and device.artwork:
            return device.artwork.id
        return None
