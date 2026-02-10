# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Fast lane API endpoints for external triggers.

Simple fire-and-forget control for external systems. Checks the
accepting_triggers gate, and routes through the protection service
when timeslice_enabled is True (budget/runtime/cooldown enforcement).

Use /external/protect/* for the dedicated budget-managed endpoint.
"""

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from gallerycontrol.database.connection import get_db_manager
from gallerycontrol.database.models import Artwork
from gallerycontrol.utils.api_errors import api_error_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external/fast", tags=["external-fast"])


def get_orchestrator():
    """Dependency to get orchestrator instance."""
    from gallerycontrol.main import app

    return app.state.orchestrator


def get_protection_service():
    """Dependency to get protection service instance."""
    from gallerycontrol.main import app

    return app.state.protection_service


@router.api_route("/artwork/{artwork_id}/{command}", methods=["GET", "POST"])
@api_error_handler("fast lane control")
async def fast_control_artwork(
    artwork_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
    protection_service=Depends(get_protection_service),
):
    """
    Fast lane control for external triggers (artwork level).

    Supports both GET and POST for easy integration with various systems.

    **Behavior:**
    - Only works when artwork.accepting_triggers is True
    - If artwork has timeslice_enabled, routes through protection service
    - Fire once, no retry
    - No OFF verification
    - No stagger delay

    **Gate check:**
    - Artwork must be "open for business" (turned ON via web/scheduler)
    - Returns 403 if artwork is not accepting triggers
    """
    db_manager = get_db_manager()

    # Check if artwork exists and is accepting triggers
    async with db_manager.session() as session:
        stmt = select(Artwork).where(Artwork.id == UUID(artwork_id))
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

        if not artwork.accepting_triggers:
            logger.warning(
                f"Fast lane blocked - artwork not accepting triggers: {artwork.name} ({artwork_id[:8]})"
            )
            raise HTTPException(
                status_code=403,
                detail="Artwork not accepting triggers. Turn on via web/scheduler first.",
            )

        # Capture fields while session is open
        artwork_name = artwork.name
        timeslice_enabled = artwork.timeslice_enabled

    # If protection is enabled, route through protection service
    if timeslice_enabled:
        success, reason = await protection_service.handle_sensor_signal(
            artwork_id=UUID(artwork_id),
            desired_state=command,
        )
        if success:
            logger.info(
                f"Fast lane -> protection accepted {command.upper()} for {artwork_name} ({artwork_id[:8]})"
            )
            return {"success": True, "artwork_id": artwork_id, "action": command, "routed": "protection"}
        else:
            logger.info(
                f"Fast lane -> protection rejected {command.upper()} for {artwork_name} ({artwork_id[:8]}): {reason}"
            )
            return {"success": False, "artwork_id": artwork_id, "action": command, "message": reason, "routed": "protection"}

    # Execute command via orchestrator (no protection)
    return await orchestrator.execute_control_command(
        target_type="artwork",
        target_id=artwork_id,
        command=command,
        source="fast",
    )


@router.get("/artwork/{artwork_id}/state")
@api_error_handler("getting artwork state")
async def fast_get_artwork_state(artwork_id: str):
    """
    Get artwork state for external systems.

    Returns artwork state including:
    - accepting_triggers status
    - All device states within the artwork
    """
    db_manager = get_db_manager()

    async with db_manager.session() as session:
        stmt = (
            select(Artwork)
            .where(Artwork.id == UUID(artwork_id))
            .options(selectinload(Artwork.devices))
        )
        result = await session.execute(stmt)
        artwork = result.scalar_one_or_none()

        if not artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")

        devices_state = [
            {
                "device_id": str(device.id),
                "name": device.name,
                "device_type": device.device_type,
                "state": device.state,
                "last_checked_at": device.last_checked_at.isoformat()
                if device.last_checked_at
                else None,
            }
            for device in artwork.devices
        ]

        return {
            "artwork_id": str(artwork.id),
            "name": artwork.name,
            "accepting_triggers": artwork.accepting_triggers,
            "devices": devices_state,
        }
