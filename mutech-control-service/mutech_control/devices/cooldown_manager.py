# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Cooldown manager for rate-limiting device requests."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import TYPE_CHECKING, Dict
from uuid import UUID

if TYPE_CHECKING:
    from mutech_control.devices.base import DeviceResult


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

    def cleanup_expired(self) -> int:
        """
        Remove expired cooldown entries to prevent memory leaks.

        Should be called periodically to clean up entries for
        devices that are no longer in cooldown.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired = [
                device_id for device_id, next_allowed in self._cooldowns.items()
                if next_allowed <= current_time
            ]
            for device_id in expired:
                del self._cooldowns[device_id]
            return len(expired)

    def cleanup_devices(self, valid_device_ids: set[UUID]) -> int:
        """
        Remove cooldown entries for devices that no longer exist.

        Args:
            valid_device_ids: Set of device UUIDs that still exist

        Returns:
            Number of entries removed
        """
        with self._lock:
            stale = [
                device_id for device_id in self._cooldowns.keys()
                if device_id not in valid_device_ids
            ]
            for device_id in stale:
                del self._cooldowns[device_id]
            return len(stale)

    def check_cooldown(self, device_id: UUID, current_state: int) -> DeviceResult | None:
        """
        Check cooldown and return error result if device is in cooldown.

        Args:
            device_id: UUID of the device
            current_state: Current state to return if blocked

        Returns:
            DeviceResult with error if in cooldown, None if request is allowed
        """
        if self.is_allowed(device_id):
            return None

        # Import here to avoid circular import
        from mutech_control.devices.base import DeviceResult

        next_time = self.next_allowed_time(device_id)
        remaining = self.get_remaining_seconds(device_id)
        return DeviceResult(
            success=False,
            state=current_state,
            error=f"Cooldown active, next allowed at {next_time} ({remaining:.1f}s remaining)",
        )
