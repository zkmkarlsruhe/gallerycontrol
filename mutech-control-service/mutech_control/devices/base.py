"""Base device manager interface and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

DeviceState = Literal[-1, 0, 1, 2, 3]  # error, off, on, cooling, warming


class DeviceProtocol(Protocol):
    """Protocol defining expected device attributes for type checking."""

    id: UUID
    name: str
    device_type: str
    host: str
    port: int | None
    state: int
    config: dict[str, Any]


@dataclass
class DeviceResult:
    """Result of a device operation."""

    success: bool
    state: DeviceState
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class ConnectionResult:
    """Result of connection test."""

    success: bool
    error: str | None = None


class DeviceManager(ABC):
    """Base interface for all device managers."""

    @abstractmethod
    async def get_state(self, device: DeviceProtocol) -> DeviceResult:
        """
        Get current state of device.

        Args:
            device: Device database model

        Returns:
            DeviceResult with success, state, and optional error
        """
        pass

    @abstractmethod
    async def set_power(self, device: DeviceProtocol, on: bool) -> DeviceResult:
        """
        Set power state of device.

        Args:
            device: Device database model
            on: True to turn on, False to turn off

        Returns:
            DeviceResult with success, new state, and optional error
        """
        pass

    @abstractmethod
    async def test_connection(self, device: DeviceProtocol) -> ConnectionResult:
        """
        Test connection to device.

        Args:
            device: Device database model

        Returns:
            ConnectionResult with success and optional error
        """
        pass
