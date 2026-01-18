"""Shell command device manager."""

import asyncio
import logging
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


async def load_credentials(db_session) -> None:
    """Load all credentials into cache. Call this at startup and when credentials change."""
    global _credential_cache
    from sqlalchemy import select
    from mutech_control.database.models import Credential

    stmt = select(Credential)
    result = await db_session.execute(stmt)
    credentials = result.scalars().all()

    _credential_cache = {
        cred.name: {"username": cred.username, "password": cred.password}
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


def replace_credential_placeholders(cmd: str) -> str:
    """Replace {{PASSWORD:name}} and {{USER:name}} placeholders with actual values.

    Example:
        Input:  "sshpass -p {{PASSWORD:museumstechnik}} ssh {{USER:museumstechnik}}@host"
        Output: "sshpass -p actualpassword ssh actualuser@host"
    """
    if not cmd or "{{" not in cmd:
        return cmd

    def replace_placeholder(match):
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
    return re.sub(pattern, replace_placeholder, cmd, flags=re.IGNORECASE)


class ShellManager(DeviceManager):
    """Manage shell command execution devices."""

    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()

    async def get_state(self, device) -> DeviceResult:
        """Execute status command and parse output."""
        # Check cooldown
        if not self.cooldown_manager.is_allowed(device.id):
            next_time = self.cooldown_manager.next_allowed_time(device.id)
            remaining = self.cooldown_manager.get_remaining_seconds(device.id)
            return DeviceResult(
                success=False,
                state=device.state,
                error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
            )

        # Get status command from device config
        commands = device.config.get("commands", {})
        status_cmd = commands.get("status")

        if not status_cmd or not status_cmd.get("cmd"):
            return DeviceResult(success=False, state=-1, error="No status command configured")

        cmd = replace_credential_placeholders(status_cmd["cmd"])
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

            # Record successful request
            cooldown = self.config.get("cooldown_seconds", 2)
            self.cooldown_manager.record_request(device.id, cooldown)

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
        command_cfg = commands.get(command_name)

        if not command_cfg or not command_cfg.get("cmd"):
            return DeviceResult(
                success=False, state=device.state, error=f"No {command_name} command configured"
            )

        cmd = replace_credential_placeholders(command_cfg["cmd"])

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

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 2)
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
            status_cmd = commands.get("status", {}).get("cmd")

            if not status_cmd:
                return ConnectionResult(success=False, error="No status command configured")

            cmd = replace_credential_placeholders(status_cmd)
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await asyncio.wait_for(proc.communicate(), timeout=5.0)

            return ConnectionResult(success=True)

        except Exception as e:
            logger.error(f"Shell: Connection test error for {device.name}: {e}")
            return ConnectionResult(success=False, error=str(e))
