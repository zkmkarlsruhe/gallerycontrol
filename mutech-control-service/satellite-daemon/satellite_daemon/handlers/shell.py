# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Shell command device handler.

Executes shell commands for custom device control.
"""

import asyncio
import logging
import re
from typing import Dict, Optional

from .base import BaseHandler

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class ShellHandler(BaseHandler):
    """Handler for shell command devices."""

    async def get_state(self, device: Dict) -> Dict:
        """Get current state by running status command."""
        config = device.get("config", {})
        status_command = config.get("status_command")
        on_pattern = config.get("status_on_pattern")
        off_pattern = config.get("status_off_pattern")
        host = device.get("resolved") or device.get("host")

        if not status_command:
            return {"success": False, "state": -1, "error": "No status command configured"}

        # Replace placeholders
        cmd = self._replace_placeholders(status_command, device)

        try:
            output, returncode = await self._run_command(cmd)

            if returncode != 0:
                return {
                    "success": False,
                    "state": -1,
                    "error": f"Command failed with code {returncode}",
                    "raw_response": output,
                }

            # Determine state from output patterns
            state = self._match_state(output, on_pattern, off_pattern)

            return {
                "success": True,
                "state": state,
                "raw_response": output,
            }

        except Exception as e:
            logger.error(f"Error getting shell state: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def set_power(self, device: Dict, on: bool) -> Dict:
        """Set power state by running on/off command."""
        config = device.get("config", {})
        command = config.get("on_command") if on else config.get("off_command")

        if not command:
            return {
                "success": False,
                "state": -1,
                "error": f"No {'on' if on else 'off'} command configured",
            }

        # Replace placeholders
        cmd = self._replace_placeholders(command, device)

        try:
            output, returncode = await self._run_command(cmd)

            if returncode != 0:
                return {
                    "success": False,
                    "state": -1,
                    "error": f"Command failed with code {returncode}",
                    "raw_response": output,
                }

            # Try to get actual state after command
            state_result = await self.get_state(device)
            if state_result.get("success"):
                state = state_result.get("state", 1 if on else 0)
            else:
                state = 1 if on else 0

            return {
                "success": True,
                "state": state,
                "raw_response": output,
            }

        except Exception as e:
            logger.error(f"Error setting shell power: {e}")
            return {"success": False, "state": -1, "error": str(e)}

    async def _run_command(
        self, command: str, timeout: float = DEFAULT_TIMEOUT
    ) -> tuple[str, int]:
        """Run shell command and return output and return code."""
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                ),
                timeout=timeout,
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            output = stdout.decode(errors="replace") if stdout else ""
            return output, proc.returncode or 0

        except asyncio.TimeoutError:
            raise TimeoutError(f"Command timed out after {timeout}s")

    def _replace_placeholders(self, command: str, device: Dict) -> str:
        """Replace placeholders in command string."""
        config = device.get("config", {})
        host = device.get("resolved") or device.get("host")

        replacements = {
            "{host}": host,
            "{port}": str(device.get("port", "")),
            "{username}": config.get("username", ""),
            "{password}": config.get("password", ""),
        }

        result = command
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    def _match_state(
        self, output: str, on_pattern: Optional[str], off_pattern: Optional[str]
    ) -> int:
        """Match output against patterns to determine state."""
        if not output:
            return -1

        # Check ON pattern first
        if on_pattern:
            try:
                if re.search(on_pattern, output, re.IGNORECASE | re.MULTILINE):
                    return 1
            except re.error as e:
                logger.warning(f"Invalid on_pattern regex: {e}")

        # Check OFF pattern
        if off_pattern:
            try:
                if re.search(off_pattern, output, re.IGNORECASE | re.MULTILINE):
                    return 0
            except re.error as e:
                logger.warning(f"Invalid off_pattern regex: {e}")

        # If we have patterns but didn't match, return error state
        if on_pattern or off_pattern:
            return -1

        # No patterns configured - assume success based on exit code
        return 1
