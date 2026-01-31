# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Fast lane API endpoints for external triggers."""

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mutech_control.database.connection import get_db_manager
from mutech_control.database.models import Artwork
from mutech_control.utils.api_errors import api_error_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fast", tags=["fast-lane"])


def get_orchestrator():
    """Dependency to get orchestrator instance."""
    from mutech_control.main import app

    return app.state.orchestrator


@router.post("/artwork/{artwork_id}/{command}")
@api_error_handler("fast lane control")
async def fast_control_artwork(
    artwork_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Fast lane control for external triggers (artwork level).

    **Behavior:**
    - Only works when artwork.accepting_triggers is True
    - Fire once, no retry
    - No OFF verification
    - No stagger delay
    - Time slice protection rules still apply

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

    # Execute command via orchestrator
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
    Fast lane state query for artwork.

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
