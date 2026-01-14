"""Cooldown manager for rate-limiting device requests."""

import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict
from uuid import UUID


class CooldownManager:
    """
    Manages cooldown periods for devices to prevent rapid polling.

    Each device gets a cooldown timer that prevents requests within
    the configured cooldown period after a successful operation.
    """

    def __init__(self):
        self._cooldowns: Dict[UUID, float] = {}  # device_id -> next_allowed_time (timestamp)
        self._lock = Lock()

    def is_allowed(self, device_id: UUID) -> bool:
        """
        Check if a device request is allowed (not in cooldown).

        Args:
            device_id: UUID of the device

        Returns:
            True if request is allowed, False if still in cooldown
        """
        with self._lock:
            if device_id not in self._cooldowns:
                return True

            next_allowed = self._cooldowns[device_id]
            current_time = time.time()

            return current_time >= next_allowed

    def record_request(self, device_id: UUID, cooldown_seconds: float) -> None:
        """
        Record a successful request and start cooldown period.

        Args:
            device_id: UUID of the device
            cooldown_seconds: Duration of cooldown in seconds
        """
        with self._lock:
            next_allowed = time.time() + cooldown_seconds
            self._cooldowns[device_id] = next_allowed

    def next_allowed_time(self, device_id: UUID) -> datetime | None:
        """
        Get the next allowed time for a device.

        Args:
            device_id: UUID of the device

        Returns:
            datetime when next request is allowed, or None if no cooldown
        """
        with self._lock:
            if device_id not in self._cooldowns:
                return None

            next_allowed = self._cooldowns[device_id]
            return datetime.fromtimestamp(next_allowed, tz=timezone.utc)

    def get_remaining_seconds(self, device_id: UUID) -> float:
        """
        Get remaining cooldown time in seconds.

        Args:
            device_id: UUID of the device

        Returns:
            Remaining seconds, or 0 if no cooldown
        """
        with self._lock:
            if device_id not in self._cooldowns:
                return 0.0

            next_allowed = self._cooldowns[device_id]
            current_time = time.time()
            remaining = next_allowed - current_time

            return max(0.0, remaining)

    def clear(self, device_id: UUID | None = None) -> None:
        """
        Clear cooldown for a specific device or all devices.

        Args:
            device_id: UUID of device to clear, or None to clear all
        """
        with self._lock:
            if device_id is None:
                self._cooldowns.clear()
            elif device_id in self._cooldowns:
                del self._cooldowns[device_id]

    def get_active_count(self) -> int:
        """
        Get number of devices currently in cooldown.

        Returns:
            Count of devices with active cooldowns
        """
        with self._lock:
            current_time = time.time()
            return sum(1 for next_allowed in self._cooldowns.values()
                      if next_allowed > current_time)
