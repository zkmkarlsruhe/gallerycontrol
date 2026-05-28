# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Custom exceptions for GalleryControl System."""


class GalleryControlError(Exception):
    """Base exception for all GalleryControl errors."""
    pass


class DeviceError(GalleryControlError):
    """Base exception for device-related errors."""

    def __init__(self, message: str, device_id: str | None = None, device_host: str | None = None):
        self.device_id = device_id
        self.device_host = device_host
        super().__init__(message)


class DeviceConnectionError(DeviceError):
    """Device connection failed."""
    pass


class DeviceTimeoutError(DeviceError):
    """Device request timed out."""
    pass


class DeviceAuthenticationError(DeviceError):
    """Device authentication failed."""
    pass


class DeviceCommandError(DeviceError):
    """Device command execution failed."""
    pass


class DeviceCooldownError(DeviceError):
    """Device is in cooldown period."""
    pass


class ConfigurationError(GalleryControlError):
    """Configuration is invalid or missing."""
    pass


class DatabaseError(GalleryControlError):
    """Database operation failed."""
    pass


class OrchestratorError(GalleryControlError):
    """Orchestrator operation failed."""
    pass
