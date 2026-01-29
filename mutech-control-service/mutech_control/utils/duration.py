"""Duration parsing and formatting utilities.

Parse and format human-readable duration strings like "5m", "2m30s", "1h15m".
"""

import re
from typing import Union

# Pattern for parsing duration strings like "1h30m45s", "5m", "2m30s", "300"
DURATION_PATTERN = re.compile(
    r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$",
    re.IGNORECASE,
)


def parse_duration(value: Union[str, int, float, None]) -> int:
    """Parse a duration value to seconds.

    Accepts:
        - Integer/float: Already in seconds
        - String "300": Numeric string (seconds)
        - String "5m": 5 minutes
        - String "2m30s": 2 minutes 30 seconds
        - String "1h15m": 1 hour 15 minutes
        - String "1h30m45s": Full format
        - None: Returns 0

    Returns:
        Duration in seconds (integer).

    Raises:
        ValueError: If the string format is invalid.

    Examples:
        >>> parse_duration("5m")
        300
        >>> parse_duration("2m30s")
        150
        >>> parse_duration("1h")
        3600
        >>> parse_duration(300)
        300
        >>> parse_duration("300")
        300
    """
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    if not isinstance(value, str):
        raise ValueError(f"Invalid duration type: {type(value)}")

    # Strip whitespace
    value = value.strip()

    if not value:
        return 0

    # Try parsing as plain integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try parsing as duration string
    match = DURATION_PATTERN.match(value)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{value}'. "
            "Expected format like '5m', '2m30s', '1h15m', or integer seconds."
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    # Handle edge case: empty match (pattern matches empty string with all optional groups)
    if hours == 0 and minutes == 0 and seconds == 0 and value:
        raise ValueError(
            f"Invalid duration format: '{value}'. "
            "Expected format like '5m', '2m30s', '1h15m', or integer seconds."
        )

    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: Union[int, float, None]) -> str:
    """Format seconds as a human-readable duration string.

    Returns the most compact representation:
        - Under 1 minute: "30s"
        - Exact minutes: "5m"
        - Mixed: "2m30s"
        - Hours: "1h15m" or "1h"

    Args:
        seconds: Duration in seconds, or None.

    Returns:
        Human-readable duration string.

    Examples:
        >>> format_duration(30)
        '30s'
        >>> format_duration(300)
        '5m'
        >>> format_duration(150)
        '2m30s'
        >>> format_duration(3600)
        '1h'
        >>> format_duration(4500)
        '1h15m'
    """
    if seconds is None or seconds <= 0:
        return "0s"

    seconds = int(seconds)

    hours = seconds // 3600
    remaining = seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60

    parts = []

    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")

    # Handle edge case: exact hours or minutes with no remainder
    if not parts:
        return "0s"

    return "".join(parts)


def format_duration_verbose(seconds: Union[int, float, None]) -> str:
    """Format seconds as verbose human-readable text.

    Unlike format_duration(), uses full words for better readability in UIs.

    Args:
        seconds: Duration in seconds, or None.

    Returns:
        Human-readable duration string with words.

    Examples:
        >>> format_duration_verbose(30)
        '30 seconds'
        >>> format_duration_verbose(60)
        '1 minute'
        >>> format_duration_verbose(150)
        '2 minutes 30 seconds'
        >>> format_duration_verbose(3600)
        '1 hour'
    """
    if seconds is None or seconds <= 0:
        return "0 seconds"

    seconds = int(seconds)

    hours = seconds // 3600
    remaining = seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60

    parts = []

    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs > 0:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    if not parts:
        return "0 seconds"

    return " ".join(parts)
