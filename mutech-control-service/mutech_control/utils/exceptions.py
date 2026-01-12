"""Custom exceptions for MuTech Control System."""


class MuTechError(Exception):
    """Base exception for all MuTech errors."""
    pass


class DeviceError(MuTechError):
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


class ConfigurationError(MuTechError):
    """Configuration is invalid or missing."""
    pass


class DatabaseError(MuTechError):
    """Database operation failed."""
    pass


class OrchestratorError(MuTechError):
    """Orchestrator operation failed."""
    pass
