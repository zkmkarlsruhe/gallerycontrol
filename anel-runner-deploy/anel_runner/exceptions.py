# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Custom exceptions for ANEL runner service."""


class ANELError(Exception):
    """Base exception for ANEL errors."""

    def __init__(self, message: str, device_ip: str | None = None):
        full_message = f"ANEL {device_ip}: {message}" if device_ip else f"ANEL: {message}"
        super().__init__(full_message)
        self.device_ip = device_ip
        self.message = message


class ANELConnectionError(ANELError):
    """Device not reachable."""

    pass


class ANELSocketError(ANELError):
    """UDP socket error."""

    pass


class ANELTimeoutError(ANELError):
    """Command timeout."""

    pass


class ANELInvalidResponseError(ANELError):
    """Invalid response format from device."""

    pass


class ANELShutdownError(ANELError):
    """Service is shutting down."""

    pass


class ANELQueueFullError(ANELError):
    """Command queue is full."""

    pass
