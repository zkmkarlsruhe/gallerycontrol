"""Shell command device manager."""

import asyncio
import logging
import re

from mutech_control.devices.base import ConnectionResult, DeviceManager, DeviceResult
from mutech_control.devices.cooldown_manager import CooldownManager

logger = logging.getLogger(__name__)


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

        cmd = status_cmd["cmd"]
        on_pattern = status_cmd.get("onPattern")
        off_pattern = status_cmd.get("offPattern")

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 30)
            logger.info(f"Shell: Executing status command for {device.name}: {cmd}")

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

            return DeviceResult(success=True, state=state, duration_ms=duration_ms)

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

        cmd = command_cfg["cmd"]

        start_time = asyncio.get_event_loop().time()

        try:
            timeout = self.config.get("request_timeout", 30)
            logger.info(f"Shell: Executing {command_name} command for {device.name}: {cmd}")

            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            # Check exit code
            if proc.returncode == 0:
                new_state = 1 if on else 0

                # Record successful request
                cooldown = self.config.get("cooldown_seconds", 2)
                self.cooldown_manager.record_request(device.id, cooldown)

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                return DeviceResult(success=True, state=new_state, duration_ms=duration_ms)
            else:
                error_output = stderr.decode() if stderr else "Command failed"
                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                return DeviceResult(
                    success=False, state=device.state, error=error_output, duration_ms=duration_ms
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

            proc = await asyncio.create_subprocess_shell(
                status_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await asyncio.wait_for(proc.communicate(), timeout=5.0)

            return ConnectionResult(success=True)

        except Exception as e:
            logger.error(f"Shell: Connection test error for {device.name}: {e}")
            return ConnectionResult(success=False, error=str(e))
