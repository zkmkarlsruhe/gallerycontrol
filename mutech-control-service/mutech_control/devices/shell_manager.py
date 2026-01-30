"""Shell command device manager."""

import asyncio
import logging
import random
import re
from typing import Dict, Optional

from mutech_control.devices.base import (
    ConnectionResult,
    DeviceManager,
    DeviceProtocol,
    DeviceResult,
)
from mutech_control.devices.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)

# Credential cache - populated by load_credentials()
_credential_cache: Dict[str, dict] = {}
_credential_cache_by_id: Dict[str, dict] = {}


async def load_credentials(db_session) -> None:
    """Load all credentials into cache. Call this at startup and when credentials change."""
    global _credential_cache, _credential_cache_by_id
    from sqlalchemy import select
    from mutech_control.database.models import Credential

    stmt = select(Credential)
    result = await db_session.execute(stmt)
    credentials = result.scalars().all()

    _credential_cache = {
        cred.name: {"username": cred.username, "password": cred.password}
        for cred in credentials
    }
    _credential_cache_by_id = {
        str(cred.id): {"username": cred.username, "password": cred.password}
        for cred in credentials
    }
    logger.info(f"Loaded {len(_credential_cache)} credentials into cache")


def get_credential(name: str) -> dict | None:
    """Get credential by name from cache.

    Args:
        name: The credential name to look up

    Returns:
        Dict with 'username' and 'password' keys, or None if not found
    """
    return _credential_cache.get(name)


def get_credential_by_id(credential_id: str) -> dict | None:
    """Get credential by ID from cache.

    Args:
        credential_id: The credential UUID to look up

    Returns:
        Dict with 'username' and 'password' keys, or None if not found
    """
    return _credential_cache_by_id.get(credential_id)


def replace_credential_placeholders(cmd: str, device=None) -> str:
    """Replace credential placeholders with actual values.

    Supports two formats:
    1. {{PASSWORD}} / {{USER}} - uses device's credential_id (preferred)
    2. {{PASSWORD:name}} / {{USER:name}} - uses named credential (legacy)

    Example:
        Input:  "sshpass -p {{PASSWORD}} ssh {{USER}}@host"
        Output: "sshpass -p actualpassword ssh actualuser@host"
    """
    if not cmd or "{{" not in cmd:
        return cmd

    # Get device credential if available
    device_cred = None
    if device:
        credential_id = device.config.get("credential_id")
        if credential_id:
            device_cred = get_credential_by_id(credential_id)
            if not device_cred:
                logger.warning(f"[device={device.name}] credential_id={credential_id} not found")

    # First, replace simple {{PASSWORD}} and {{USER}} with device credential
    if device_cred:
        cmd = cmd.replace("{{PASSWORD}}", device_cred.get("password", ""))
        cmd = cmd.replace("{{USER}}", device_cred.get("username", ""))
        cmd = cmd.replace("{{password}}", device_cred.get("password", ""))
        cmd = cmd.replace("{{user}}", device_cred.get("username", ""))

    # Then handle legacy {{PASSWORD:name}} and {{USER:name}} format
    def replace_named_placeholder(match):
        placeholder_type = match.group(1).upper()  # PASSWORD or USER
        cred_name = match.group(2)

        cred = _credential_cache.get(cred_name)
        if not cred:
            logger.warning(f"Credential '{cred_name}' not found in cache")
            return match.group(0)  # Return original placeholder

        if placeholder_type == "PASSWORD":
            return cred.get("password", "")
        elif placeholder_type == "USER":
            return cred.get("username", "")
        else:
            return match.group(0)

    # Match {{PASSWORD:name}} or {{USER:name}}
    pattern = r"\{\{(PASSWORD|USER):([^}]+)\}\}"
    return re.sub(pattern, replace_named_placeholder, cmd, flags=re.IGNORECASE)


class ShellManager(DeviceManager):
    """Manage shell command execution devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()

    async def get_state(self, device) -> DeviceResult:
        """Execute status command and parse output. No cooldown - queries are read-only."""
        # Get status command from device config
        commands = device.config.get("commands", {})

        # Handle legacy list format from migration
        if isinstance(commands, list):
            # Find status command in list (look for "status" or "Status" in name)
            status_cmd = next(
                (c for c in commands if c.get("name", "").lower() == "status"),
                None
            )
            if not status_cmd:
                return DeviceResult(success=False, state=-1, error="No status command in list format")
        else:
            status_cmd = commands.get("status")

        if not status_cmd or not status_cmd.get("cmd"):
            return DeviceResult(success=False, state=-1, error="No status command configured")

        cmd = replace_credential_placeholders(status_cmd["cmd"], device)
        on_pattern = status_cmd.get("onPattern")
        off_pattern = status_cmd.get("offPattern")

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 30)
            # Log command without credentials for security
            logger.info(f"Shell: Executing status command for {device.name}")

            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output = stdout.decode()

            # Pattern matching
            state = -1
            if on_pattern and re.search(on_pattern, output):
                state = 1
            elif off_pattern and re.search(off_pattern, output):
                state = 0

            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Combine stdout and stderr for raw response
            raw_output = output
            if stderr:
                stderr_text = stderr.decode()
                if stderr_text:
                    raw_output += f"\n--- stderr ---\n{stderr_text}"

            return DeviceResult(
                success=True,
                state=state,
                duration_ms=duration_ms,
                raw_response=raw_output,
            )

        except asyncio.TimeoutError:
            # Kill the subprocess to prevent zombie processes
            try:
                proc.kill()
                await proc.wait()
            except (ProcessLookupError, OSError):
                pass  # Process already terminated or OS error during cleanup
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"Shell: Command timeout for {device.name}")
            return DeviceResult(
                success=False, state=-1, error="Command timeout", duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"Shell: Error executing command for {device.name}: {e}")
            return DeviceResult(success=False, state=-1, error=str(e), duration_ms=duration_ms)

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Execute on/off command."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(device.id):
            next_time = self.cooldown_manager.next_allowed_time(device.id)
            remaining = self.cooldown_manager.get_remaining_seconds(device.id)
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        # Get on/off command from device config
        commands = device.config.get("commands", {})
        command_name = "on" if on else "off"

        # Handle legacy list format from migration
        if isinstance(commands, list):
            # Find on/off command in list (look for "on"/"off" in name, case-insensitive)
            command_cfg = next(
                (c for c in commands if c.get("name", "").lower() == command_name),
                None
            )
        else:
            command_cfg = commands.get(command_name)

        if not command_cfg or not command_cfg.get("cmd"):
            return DeviceResult(
                success=False, state=device.state, error=f"No {command_name} command configured"
            )

        cmd = replace_credential_placeholders(command_cfg["cmd"], device)

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 30)
            # Log command without credentials for security
            logger.info(f"Shell: Executing {command_name} command for {device.name}")

            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            # Combine stdout and stderr for raw response
            output = stdout.decode() if stdout else ""
            stderr_text = stderr.decode() if stderr else ""
            raw_output = output
            if stderr_text:
                raw_output += f"\n--- stderr ---\n{stderr_text}"

            # Check exit code
            if proc.returncode == 0:
                new_state = 1 if on else 0

                # Record minimal random cooldown (0-1s) to prevent accidental double-clicks
                cooldown = random.uniform(0, 1)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(
                    success=True,
                    state=new_state,
                    duration_ms=duration_ms,
                    raw_response=raw_output,
                )
            else:
                error_output = stderr_text if stderr_text else "Command failed"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(
                    success=False,
                    state=device.state,
                    error=error_output,
                    duration_ms=duration_ms,
                    raw_response=raw_output,
                )

        except asyncio.TimeoutError:
            # Kill the subprocess to prevent zombie processes
            try:
                proc.kill()
                await proc.wait()
            except (ProcessLookupError, OSError):
                pass  # Process already terminated or OS error during cleanup
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"Shell: Command timeout for {device.name}")
            return DeviceResult(
                success=False,
                state=device.state,
                error="Command timeout",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.error(f"Shell: Error executing command for {device.name}: {e}")
            return DeviceResult(
                success=False, state=device.state, error=str(e), duration_ms=duration_ms
            )

    async def test_connection(self, device) -> ConnectionResult:
        """Test shell command execution (run status command)."""
        try:
            logger.info(f"Shell: Testing connection for {device.name}")

            commands = device.config.get("commands", {})

            # Handle legacy list format from migration
            if isinstance(commands, list):
                status_entry = next(
                    (c for c in commands if c.get("name", "").lower() == "status"),
                    None
                )
                status_cmd = status_entry.get("cmd") if status_entry else None
            else:
                status_cmd = commands.get("status", {}).get("cmd")

            if not status_cmd:
                return ConnectionResult(success=False, error="No status command configured")

            cmd = replace_credential_placeholders(status_cmd, device)
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await asyncio.wait_for(proc.communicate(), timeout=5.0)

            return ConnectionResult(success=True)

        except Exception as e:
            logger.error(f"Shell: Connection test error for {device.name}: {e}")
            return ConnectionResult(success=False, error=str(e))
