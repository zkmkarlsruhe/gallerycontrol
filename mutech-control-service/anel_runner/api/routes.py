"""REST API endpoints for ANEL runner service."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from anel_runner.api.models import (
    BroadcastCacheResponse,
    CachedDeviceState,
    CommandResponse,
    DeviceInfoResponse,
    PortInfo,
    StateResponse,
)
from anel_runner.core.anel_service import ANELService
from anel_runner.exceptions import ANELError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


def get_anel_service(request: Request) -> ANELService:
    """Dependency to get ANEL service from app state."""
    return request.app.state.anel_service


@router.get("/{host}/state", response_model=StateResponse)
async def get_state(
    host: str,
    port: Annotated[int, Query(ge=0, le=7, description="Port number (0-7)")],
    service: ANELService = Depends(get_anel_service),
) -> StateResponse:
    """
    Query power state for a specific port.

    - **host**: Device IP address
    - **port**: Port number (0-based, 0-7)
    """
    try:
        result = await service.get_power_state(host, port)
        return StateResponse(
            host=result.host,
            port=result.port,
            state=result.state,
            name=result.name,
            success=result.success,
            error=result.error,
        )
    except ANELError as e:
        logger.error(f"Get state error: {e}")
        return StateResponse(
            host=host,
            port=port,
            state=-1,
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting state for {host}:{port}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host}/on", response_model=CommandResponse)
async def power_on(
    host: str,
    port: Annotated[int, Query(ge=0, le=7, description="Port number (0-7)")],
    fast_lane: Annotated[bool, Query(description="Bypass command queue")] = False,
    user: Annotated[str | None, Query(description="Override username")] = None,
    password: Annotated[str | None, Query(description="Override password")] = None,
    service: ANELService = Depends(get_anel_service),
) -> CommandResponse:
    """
    Turn on a specific port.

    - **host**: Device IP address
    - **port**: Port number (0-based, 0-7)
    - **fast_lane**: If true, bypass command queue (immediate execution)
    - **user**: Override default username
    - **password**: Override default password
    """
    try:
        result = await service.set_power_state(
            host=host,
            port=port,
            state=True,
            user=user,
            password=password,
            fast_lane=fast_lane,
        )
        return CommandResponse(
            success=result.success,
            host=result.host,
            port=result.port,
            command=result.command,
            state=result.state,
            error=result.error,
        )
    except ANELError as e:
        logger.error(f"Power on error: {e}")
        return CommandResponse(
            success=False,
            host=host,
            port=port,
            command="on",
            error=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error powering on {host}:{port}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{host}/off", response_model=CommandResponse)
async def power_off(
    host: str,
    port: Annotated[int, Query(ge=0, le=7, description="Port number (0-7)")],
    fast_lane: Annotated[bool, Query(description="Bypass command queue")] = False,
    user: Annotated[str | None, Query(description="Override username")] = None,
    password: Annotated[str | None, Query(description="Override password")] = None,
    service: ANELService = Depends(get_anel_service),
) -> CommandResponse:
    """
    Turn off a specific port.

    - **host**: Device IP address
    - **port**: Port number (0-based, 0-7)
    - **fast_lane**: If true, bypass command queue (immediate execution)
    - **user**: Override default username
    - **password**: Override default password
    """
    try:
        result = await service.set_power_state(
            host=host,
            port=port,
            state=False,
            user=user,
            password=password,
            fast_lane=fast_lane,
        )
        return CommandResponse(
            success=result.success,
            host=result.host,
            port=result.port,
            command=result.command,
            state=result.state,
            error=result.error,
        )
    except ANELError as e:
        logger.error(f"Power off error: {e}")
        return CommandResponse(
            success=False,
            host=host,
            port=port,
            command="off",
            error=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error powering off {host}:{port}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host}/info", response_model=DeviceInfoResponse)
async def get_device_info(
    host: str,
    service: ANELService = Depends(get_anel_service),
) -> DeviceInfoResponse:
    """
    Get full device information.

    - **host**: Device IP address
    """
    try:
        status = await service.get_device_info(host)
        if status:
            return DeviceInfoResponse(
                host=host,
                name=status.name,
                ip=status.ip,
                mac=status.mac,
                ports=[
                    PortInfo(port=p.port, name=p.name, state=p.state)
                    for p in status.ports
                ],
                temperature=status.temperature,
                success=True,
            )
        else:
            return DeviceInfoResponse(
                host=host,
                name="",
                ip=host,
                ports=[],
                success=False,
                error="Could not get device info",
            )
    except ANELError as e:
        logger.error(f"Get device info error: {e}")
        return DeviceInfoResponse(
            host=host,
            name="",
            ip=host,
            ports=[],
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error getting info for {host}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/broadcast/cache", response_model=BroadcastCacheResponse)
async def get_broadcast_cache(
    service: ANELService = Depends(get_anel_service),
) -> BroadcastCacheResponse:
    """
    Get all cached device states from UDP broadcasts.

    ANEL devices periodically broadcast their state. This endpoint returns
    all cached states without querying devices directly.
    """
    try:
        # Get thread-safe snapshot of cached states
        device_states = await service.get_all_cached_states()

        cached_devices = []
        for host, status in device_states.items():
            cached_devices.append(
                CachedDeviceState(
                    host=host,
                    name=status.name,
                    ports=[
                        PortInfo(port=p.port, name=p.name, state=p.state)
                        for p in status.ports
                    ],
                    temperature=status.temperature,
                    mac=status.mac,
                )
            )

        return BroadcastCacheResponse(
            device_count=len(cached_devices),
            devices=cached_devices,
        )
    except Exception as e:
        logger.exception("Error getting broadcast cache")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{host}/cached", response_model=DeviceInfoResponse)
async def get_cached_state(
    host: str,
    service: ANELService = Depends(get_anel_service),
) -> DeviceInfoResponse:
    """
    Get cached device state without querying.

    Returns state from last UDP broadcast. Returns 404 if device has not
    broadcasted since service start.

    - **host**: Device IP address
    """
    try:
        status = service.get_cached_state(host)
        if status:
            return DeviceInfoResponse(
                host=host,
                name=status.name,
                ip=status.ip,
                mac=status.mac,
                ports=[
                    PortInfo(port=p.port, name=p.name, state=p.state)
                    for p in status.ports
                ],
                temperature=status.temperature,
                success=True,
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No cached state for {host}. Device may not have broadcasted yet.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting cached state for {host}")
        raise HTTPException(status_code=500, detail=str(e))
