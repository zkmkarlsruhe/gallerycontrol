# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Datetime utilities for consistent timezone handling.

The database stores naive UTC datetimes, but Python 3.12+ recommends using
timezone-aware datetimes. This module provides helpers to bridge the gap.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime.

    Use this instead of datetime.utcnow() which is deprecated.
    """
    return datetime.utcnow()


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is UTC-aware.

    If the datetime is naive (no tzinfo), assume it's UTC and add tzinfo.
    If it's already aware, convert to UTC.
    If None, return None.

    This is useful when loading naive datetimes from the database and
    comparing them with timezone-aware datetimes.

    Args:
        dt: A datetime that may be naive or aware, or None.

    Returns:
        A timezone-aware UTC datetime, or None if input was None.
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Already aware - convert to UTC
        return dt.astimezone(timezone.utc)


def ensure_utc_or_now(dt: datetime | None) -> datetime:
    """Ensure a datetime is UTC-aware, defaulting to now if None.

    Args:
        dt: A datetime that may be naive or aware, or None.

    Returns:
        A timezone-aware UTC datetime.
    """
    if dt is None:
        return utc_now()
    return ensure_utc(dt)  # type: ignore
