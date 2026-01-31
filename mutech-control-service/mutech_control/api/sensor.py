# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Sensor API endpoints for external trigger integration.

Provides endpoints for external sensors (lidar, motion detectors, etc.) to trigger
artwork control. The sensor handles visitor detection and debouncing; this API
handles budget tracking, runtime limits, and device control via the protection service.

Hierarchy:
1. Web UI / Scheduler (KING) -> Controls opening hours, sets accepting_triggers
2. Protection Service -> Manages runtime WHILE open for business
3. Sensor (Lidar) -> Triggers within allowed bounds via this API
"""

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from mutech_control.database.connection import get_db_manager
from mutech_control.database.models import Artwork
from mutech_control.utils.api_errors import api_error_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sensor", tags=["sensor"])


# Response models
class SensorTriggerResponse(BaseModel):
    """Response for sensor trigger endpoints."""

    success: bool
    artwork_id: str
    action: str
    message: str | None = None


class SensorStatusResponse(BaseModel):
    """Response for sensor status endpoint."""

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
    from mutech_control.main import app

    return app.state.protection_service


@router.post("/artwork/{artwork_id}/{action}", response_model=SensorTriggerResponse)
@api_error_handler("sensor trigger")
async def sensor_trigger(
    artwork_id: str,
    action: Literal["on", "off"],
    protection_service=Depends(get_protection_service),
) -> SensorTriggerResponse:
    """
    Sensor trigger endpoint for external sensors.

    This is the main integration point for external sensors (lidar, motion, etc.).
    The sensor handles visitor detection and debouncing; this endpoint handles:
    - Gate check (accepting_triggers must be True for ON, always allowed for OFF)
    - Budget/runtime checks
    - Cooldown checks
    - Device control via orchestrator

    **ON Signal Behavior:**
    - Only works when artwork.accepting_triggers is True
    - Checks cooldown, budget, and min_runtime requirements
    - Executes command via orchestrator
    - No cooldown on sensor OFF (voluntary stop)

    **OFF Signal Behavior:**
    - Always allowed (don't trap devices ON)
    - Checks min_runtime and force_completion
    - Executes command via orchestrator
    - No cooldown after sensor OFF

    **Returns:**
    - success: Whether the trigger was accepted
    - artwork_id: The artwork UUID
    - action: The requested action (on/off)
    - message: Reason if rejected, null if accepted

    **Status codes:**
    - 200: Trigger accepted (or already in desired state)
    - 400: Trigger rejected (with reason in message)
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
                detail="Protection not enabled for this artwork",
            )

    # Handle the sensor signal via protection service
    success, reason = await protection_service.handle_sensor_signal(
        artwork_id=UUID(artwork_id),
        desired_state=action,
    )

    if success:
        logger.info(
            f"Sensor {action.upper()} accepted for artwork {artwork_id[:8]}"
        )
        return SensorTriggerResponse(
            success=True,
            artwork_id=artwork_id,
            action=action,
            message=None,
        )
    else:
        logger.info(
            f"Sensor {action.upper()} rejected for artwork {artwork_id[:8]}: {reason}"
        )
        return SensorTriggerResponse(
            success=False,
            artwork_id=artwork_id,
            action=action,
            message=reason,
        )


@router.get("/artwork/{artwork_id}/status", response_model=SensorStatusResponse)
@api_error_handler("sensor status")
async def sensor_status(
    artwork_id: str,
    protection_service=Depends(get_protection_service),
) -> SensorStatusResponse:
    """
    Get protection status for budget display on sensor devices.

    Returns current protection state including:
    - Budget remaining (seconds and formatted)
    - Time until budget resets
    - Cooldown status
    - Whether artwork can start
    - Current running state
    - Sensor's desired state (on/off)

    Useful for sensors with displays that want to show remaining budget.

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
        return SensorStatusResponse(
            protected=False,
            can_start=True,
        )

    state = status.get("state", {})
    time_slice = state.get("time_slice")

    return SensorStatusResponse(
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
