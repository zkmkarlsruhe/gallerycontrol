"""Control API endpoints for device control."""

import asyncio
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from mutech_control.database.connection import get_session
from mutech_control.database.models import Device
from mutech_control.devices.shell_manager import replace_credential_placeholders

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control", tags=["control"])


def get_orchestrator():
    """Dependency to get orchestrator instance."""
    from mutech_control.main import app

    return app.state.orchestrator


@router.post("/exhibition/{exhibition_id}/{command}")
async def control_exhibition(
    exhibition_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control all devices in an exhibition.

    - **ON**: Devices turned on with 1s stagger
    - **OFF**: Devices turned off in parallel with verification
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="exhibition",
            target_id=exhibition_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling exhibition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/artwork/{artwork_id}/{command}")
async def control_artwork(
    artwork_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control all devices in an artwork.

    - **ON**: Devices turned on with 1s stagger
    - **OFF**: Devices turned off in parallel with verification
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="artwork",
            target_id=artwork_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling artwork: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/device/{device_id}/{command}")
async def control_device(
    device_id: str,
    command: Literal["on", "off"],
    orchestrator=Depends(get_orchestrator),
):
    """
    Control a single device.

    - **ON**: Device turned on
    - **OFF**: Device turned off with verification (except shell devices)
    """
    try:
        result = await orchestrator.execute_control_command(
            target_type="device",
            target_id=device_id,
            command=command,
            source="web",
        )
        return result

    except Exception as e:
        logger.error(f"Error controlling device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/device/{device_id}/action/{action_name}")
async def execute_device_action(
    device_id: str,
    action_name: str,
    session=Depends(get_session),
):
    """
    Execute a shell device action (e.g., Reboot, Restart App).

    Actions are defined in the device config and are manual-only commands.
    """
    try:
        # Get device
        stmt = select(Device).where(Device.id == UUID(device_id))
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if device.device_type != "shell":
            raise HTTPException(status_code=400, detail="Actions only available for shell devices")

        # Find action - check both new format (actions array) and old format (commands dict)
        action = None

        # New format: config.actions array
        actions_array = device.config.get("actions", [])
        if actions_array:
            action = next((a for a in actions_array if a.get("name") == action_name), None)

        # Old format: custom commands in commands dict
        if not action:
            commands = device.config.get("commands", {})
            if isinstance(commands, dict) and action_name in commands:
                cmd_config = commands[action_name]
                if isinstance(cmd_config, dict) and cmd_config.get("cmd"):
                    action = {"name": action_name, "cmd": cmd_config["cmd"]}

        if not action:
            raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

        cmd = replace_credential_placeholders(action["cmd"])

        logger.info(f"Executing action '{action_name}' for device {device.name}")

        # Execute command
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode == 0:
            return {
                "success": True,
                "action": action_name,
                "output": stdout.decode()[:500] if stdout else None,
            }
        else:
            return {
                "success": False,
                "action": action_name,
                "error": stderr.decode()[:500] if stderr else "Command failed",
            }

    except asyncio.TimeoutError:
        logger.error(f"Action timeout for {device_id}")
        return {"success": False, "action": action_name, "error": "Command timeout"}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error executing action: {e}")
        raise HTTPException(status_code=500, detail=str(e))
