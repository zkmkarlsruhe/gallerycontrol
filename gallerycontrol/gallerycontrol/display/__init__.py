# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Display module for visitor-facing kiosk displays.

Provides template-based HTML displays showing artwork protection status
(budget remaining, cooldown, etc.) for museum kiosk systems.
"""

from gallerycontrol.display.config_loader import (
    DisplayConfigLoader,
    get_display_config_loader,
)

__all__ = [
    "DisplayConfigLoader",
    "get_display_config_loader",
]
