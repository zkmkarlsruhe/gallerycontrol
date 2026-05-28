# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Protected API endpoints for external trigger integration.

Provides endpoints for external systems (lidar, motion detectors, etc.) to trigger
artwork control with budget tracking, runtime limits, and cooldown enforcement.

Hierarchy:
1. Web UI / Scheduler (KING) -> Controls opening hours, sets accepting_triggers
2. Protection Service -> Manages runtime WHILE open for business
3. External System -> Triggers within allowed bounds via this API

Use /external/fast/* for simple triggers without budget tracking.
"""

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from gallerycontrol.database.connection import get_db_manager
from gallerycontrol.database.models import Artwork
from gallerycontrol.utils.api_errors import api_error_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external/protect", tags=["external-protect"])


# Response models
class ProtectTriggerResponse(BaseModel):
    """Response for protected trigger endpoints."""

    success: bool
    artwork_id: str
    action: str
    message: str | None = None


class ProtectStatusResponse(BaseModel):
    """Response for protection status endpoint."""

    protected: bool
    budget_remaining: int | None = None
    budget_remaining_formatted: str | None = None
    resets_in: int | None = None
    resets_in_formatted: str | None = None
    cooldown_active: bool = False
    cooldown_remaining: int | None = None
    cooldown_remaining_formatted: str | None = None
    can_start: bool = True
    block_reason: str | None = None
    is_running: bool = False
    runtime_seconds: int = 0
    runtime_formatted: str | None = None
    desired_state: str = "off"


def get_protection_service():
    """Dependency to get protection service instance."""
    from gallerycontrol.main import app

    return app.state.protection_service


@router.api_route("/artwork/{artwork_id}/{action}", methods=["GET", "POST"], response_model=ProtectTriggerResponse)
@api_error_handler("protected trigger")
async def protect_trigger(
    artwork_id: str,
    action: Literal["on", "off"],
    protection_service=Depends(get_protection_service),
) -> ProtectTriggerResponse:
    """
    Protected trigger endpoint for external systems.

    Supports both GET and POST for easy integration with various systems.

    This is the main integration point for external systems (lidar, motion, etc.)
    that need budget tracking and cooldown enforcement. The external system handles
    detection and debouncing; this endpoint handles:
    - Gate check (accepting_triggers must be True for ON, always allowed for OFF)
    - Budget/runtime checks
    - Cooldown checks
    - Device control via orchestrator

    **ON Behavior:**
    - Only works when artwork.accepting_triggers is True
    - Checks cooldown, budget, and min_runtime requirements
    - Executes command via orchestrator

    **OFF Behavior:**
    - Always allowed (don't trap devices ON)
    - Checks min_runtime and force_completion
    - Executes command via orchestrator
    - No cooldown after voluntary OFF

    **Returns:**
    - success: Whether the trigger was accepted
    - artwork_id: The artwork UUID
    - action: The requested action (on/off)
    - message: Reason if rejected, null if accepted

    **Status codes:**
    - 200: Trigger accepted or rejected (check success field)
    - 400: Protection not enabled for this artwork
    - 404: Artwork not found
    - 500: Internal error
    """
    db_manager = get_db_manager()

    # Validate artwork exists
    async with db_manager.session() as session:
        stmt = select(Artwork).where(Artwork.id == UUID(artwork_id))
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

        if not artwork.timeslice_enabled:
            raise HTTPException(
                status_code=400,
                detail="Protection not enabled for this artwork. Use /external/fast/* instead.",
            )

    # Handle the signal via protection service
    success, reason = await protection_service.handle_sensor_signal(
        artwork_id=UUID(artwork_id),
        desired_state=action,
    )

    if success:
        logger.info(
            f"Protected {action.upper()} accepted for artwork {artwork_id[:8]}"
        )
        return ProtectTriggerResponse(
            success=True,
            artwork_id=artwork_id,
            action=action,
            message=None,
        )
    else:
        logger.info(
            f"Protected {action.upper()} rejected for artwork {artwork_id[:8]}: {reason}"
        )
        return ProtectTriggerResponse(
            success=False,
            artwork_id=artwork_id,
            action=action,
            message=reason,
        )


@router.get("/artwork/{artwork_id}/status", response_model=ProtectStatusResponse)
@api_error_handler("protection status")
async def protect_status(
    artwork_id: str,
    protection_service=Depends(get_protection_service),
) -> ProtectStatusResponse:
    """
    Get protection status for budget display.

    Returns current protection state including:
    - Budget remaining (seconds and formatted)
    - Time until budget resets
    - Cooldown status
    - Whether artwork can start
    - Current running state
    - Desired state (on/off)

    Useful for external systems with displays that want to show remaining budget.

    **Status codes:**
    - 200: Status returned
    - 404: Artwork not found
    - 500: Internal error
    """
    db_manager = get_db_manager()

    # Validate artwork exists
    async with db_manager.session() as session:
        stmt = select(Artwork).where(Artwork.id == UUID(artwork_id))
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

    # Get protection status
    status = await protection_service.get_protection_status(UUID(artwork_id))

    if not status.get("protected"):
        return ProtectStatusResponse(
            protected=False,
            can_start=True,
        )

    state = status.get("state", {})
    time_slice = state.get("time_slice")

    return ProtectStatusResponse(
        protected=True,
        budget_remaining=time_slice.get("remaining") if time_slice else None,
        budget_remaining_formatted=time_slice.get("remaining_formatted") if time_slice else None,
        resets_in=time_slice.get("resets_in") if time_slice else None,
        resets_in_formatted=time_slice.get("resets_in_formatted") if time_slice else None,
        cooldown_active=state.get("cooldown_active", False),
        cooldown_remaining=state.get("cooldown_remaining"),
        cooldown_remaining_formatted=state.get("cooldown_remaining_formatted"),
        can_start=state.get("can_start", True),
        block_reason=state.get("block_reason"),
        is_running=state.get("is_running", False),
        runtime_seconds=state.get("runtime_seconds", 0),
        runtime_formatted=state.get("runtime_formatted"),
        desired_state=state.get("desired_state", "off"),
    )
