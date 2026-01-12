"""Per-device cooldown management to prevent rapid requests."""

import time
from datetime import datetime, timedelta
from typing import Dict


class CooldownManager:
    """Manage per-device cooldowns to prevent rapid successive requests."""

    def __init__(self):
        self._cooldowns: Dict[str, float] = {}  # device_id -> next_allowed_timestamp

    def is_allowed(self, device_id: str) -> bool:
        """Check if request is allowed for device."""
        if device_id not in self._cooldowns:
            return True

        return time.time() >= self._cooldowns[device_id]

    def next_allowed(self, device_id: str) -> datetime | None:
        """Get next allowed time for device."""
        if device_id not in self._cooldowns:
            return None

        return datetime.fromtimestamp(self._cooldowns[device_id])

    def record_request(self, device_id: str, cooldown_seconds: float) -> None:
        """Record a request and set cooldown."""
        self._cooldowns[device_id] = time.time() + cooldown_seconds

    def clear_cooldown(self, device_id: str) -> None:
        """Clear cooldown for device (useful for testing)."""
        if device_id in self._cooldowns:
            del self._cooldowns[device_id]

    def get_remaining_cooldown(self, device_id: str) -> float:
        """Get remaining cooldown time in seconds."""
        if device_id not in self._cooldowns:
            return 0.0

        remaining = self._cooldowns[device_id] - time.time()
        return max(0.0, remaining)
