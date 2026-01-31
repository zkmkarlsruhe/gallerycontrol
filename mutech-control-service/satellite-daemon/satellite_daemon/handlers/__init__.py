# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Device handlers for satellite daemon."""

from .base import BaseHandler
from .anel import ANELHandler
from .netio import NETIOHandler
from .pjlink import PJLinkHandler
from .shell import ShellHandler

# Handler registry
HANDLERS = {
    "anel": ANELHandler(),
    "netio": NETIOHandler(),
    "pjlink": PJLinkHandler(),
    "shell": ShellHandler(),
}


async def handle_command(device_type: str, device: dict, command: str) -> dict:
    """Route command to appropriate handler."""
    handler = HANDLERS.get(device_type)
    if not handler:
        return {"success": False, "state": -1, "error": f"Unknown device type: {device_type}"}

    if command == "on":
        return await handler.set_power(device, True)
    elif command == "off":
        return await handler.set_power(device, False)
    elif command == "state":
        return await handler.get_state(device)
    else:
        return {"success": False, "state": -1, "error": f"Unknown command: {command}"}
