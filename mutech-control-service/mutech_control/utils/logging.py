"""Enhanced logging utilities with context and request tracing."""

import logging
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

# Context variable for request tracing
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class ContextLogger:
    """Logger wrapper that adds context to all log messages."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _format_message(self, msg: str, extra_context: Optional[Dict[str, Any]] = None) -> str:
        """Format message with context."""
        parts = []

        # Add request ID if available
        request_id = _request_id.get()
        if request_id:
            parts.append(f"[req:{request_id[:8]}]")

        # Add extra context
        if extra_context:
            context_parts = []
            for key, value in extra_context.items():
                if value is not None:
                    context_parts.append(f"{key}={value}")
            if context_parts:
                parts.append(f"[{', '.join(context_parts)}]")

        # Add original message
        parts.append(msg)

        return " ".join(parts)

    def debug(self, msg: str, **context):
        """Log debug message with context."""
        self.logger.debug(self._format_message(msg, context))

    def info(self, msg: str, **context):
        """Log info message with context."""
        self.logger.info(self._format_message(msg, context))

    def warning(self, msg: str, **context):
        """Log warning message with context."""
        self.logger.warning(self._format_message(msg, context))

    def error(self, msg: str, **context):
        """Log error message with context."""
        self.logger.error(self._format_message(msg, context))

    def critical(self, msg: str, **context):
        """Log critical message with context."""
        self.logger.critical(self._format_message(msg, context))


def get_logger(name: str) -> ContextLogger:
    """Get a context-aware logger."""
    return ContextLogger(logging.getLogger(name))


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set request ID for current context. Returns the request ID."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    _request_id.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return _request_id.get()


def clear_request_id():
    """Clear request ID from context."""
    _request_id.set(None)


def log_device_operation(
    logger: ContextLogger,
    operation: str,
    device_name: str,
    device_type: str,
    device_host: str,
    success: bool,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
):
    """Log a device operation with full context."""
    context = {
        "device": device_name,
        "type": device_type,
        "host": device_host,
        "operation": operation,
    }

    if duration_ms is not None:
        context["duration_ms"] = duration_ms

    if success:
        logger.info(f"Device operation successful", **context)
    else:
        context["error"] = error or "Unknown error"
        logger.error(f"Device operation failed", **context)


def log_command_execution(
    logger: ContextLogger,
    command: str,
    target_type: str,
    target_id: str,
    device_count: int,
    success_count: int,
    duration_ms: Optional[int] = None,
):
    """Log a command execution summary."""
    context = {
        "command": command,
        "target_type": target_type,
        "target_id": target_id[:8],  # Shortened UUID
        "devices": device_count,
        "successful": success_count,
    }

    if duration_ms is not None:
        context["duration_ms"] = duration_ms

    if success_count == device_count:
        logger.info(f"Command completed successfully", **context)
    elif success_count > 0:
        logger.warning(f"Command partially successful", **context)
    else:
        logger.error(f"Command failed", **context)
