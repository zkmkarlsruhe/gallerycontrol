# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Base handler interface for device types."""

from abc import ABC, abstractmethod
from typing import Dict


class BaseHandler(ABC):
    """Abstract base class for device handlers."""

    @abstractmethod
    async def get_state(self, device: Dict) -> Dict:
        """Get current device state.

        Args:
            device: Device configuration dict with host, port, config, etc.

        Returns:
            Dict with:
                - success: bool
                - state: int (-1=error, 0=off, 1=on, 2=cooling, 3=warming)
                - error: Optional[str]
                - raw_response: Optional[str]
        """
        pass

    @abstractmethod
    async def set_power(self, device: Dict, on: bool) -> Dict:
        """Set device power state.

        Args:
            device: Device configuration dict
            on: True to turn on, False to turn off

        Returns:
            Dict with:
                - success: bool
                - state: int
                - error: Optional[str]
                - raw_response: Optional[str]
        """
        pass

    async def get_device_info(self, device: Dict) -> Dict:
        """Return device metadata (MAC, firmware, lamp hours, etc.).

        Default impl returns an empty success — subclasses override as needed.
        """
        return {"success": True, "info": {}}
