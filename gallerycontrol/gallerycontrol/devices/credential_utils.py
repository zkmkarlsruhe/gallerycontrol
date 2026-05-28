# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Shared credential resolution utilities for device managers.

All device managers that need to resolve credentials from the credential cache
should use these helpers to ensure consistent behavior.
"""

import logging
from typing import NamedTuple

from gallerycontrol.devices.shell_manager import get_credential, get_credential_by_id

logger = logging.getLogger(__name__)


class UsernamePassword(NamedTuple):
    """Username and password credential pair."""
    username: str
    password: str


def resolve_password(
    device,
    default: str | None = None,
) -> str | None:
    """Resolve password-only credential from device config.

    Tries credential_id first (frontend format), then credential_name (legacy).

    Args:
        device: Device object with config dict containing credential_id or credential_name
        default: Default password if no credential found

    Returns:
        Password string or default if not found
    """
    device_name = getattr(device, 'name', 'unknown')

    # Try credential_id first (used by frontend)
    credential_id = device.config.get("credential_id")
    if credential_id:
        cred = get_credential_by_id(credential_id)
        if cred:
            password = cred.get("password")
            logger.debug(
                f"[device={device_name}] Using credential_id={credential_id}, "
                f"password={'*' * len(password) if password else 'None'}"
            )
            return password
        else:
            logger.warning(f"[device={device_name}] credential_id={credential_id} not found in cache")

    # Fall back to credential_name (legacy)
    credential_name = device.config.get("credential_name")
    if credential_name:
        cred = get_credential(credential_name)
        if cred:
            logger.debug(f"[device={device_name}] Using credential_name={credential_name}")
            return cred.get("password")

    logger.debug(f"[device={device_name}] No credential configured, using default")
    return default


def resolve_credentials(
    device,
    default_username: str,
    default_password: str,
) -> UsernamePassword:
    """Resolve username/password credentials from device config.

    Tries credential_id first (frontend format), then credential_name (legacy),
    then inline config values, finally defaults.

    Args:
        device: Device object with config dict containing credential_id, credential_name,
                or inline username/password
        default_username: Default username if no credential found
        default_password: Default password if no credential found

    Returns:
        UsernamePassword tuple with resolved or default values
    """
    device_name = getattr(device, 'name', 'unknown')

    # Try credential_id first (used by frontend)
    credential_id = device.config.get("credential_id")
    if credential_id:
        cred = get_credential_by_id(credential_id)
        if cred:
            logger.debug(f"[device={device_name}] Using credential_id={credential_id}")
            return UsernamePassword(
                username=cred.get("username") or default_username,
                password=cred.get("password") or default_password,
            )
        else:
            logger.warning(f"[device={device_name}] credential_id={credential_id} not found in cache")

    # Fall back to credential_name (legacy)
    credential_name = device.config.get("credential_name")
    if credential_name:
        cred = get_credential(credential_name)
        if cred:
            logger.debug(f"[device={device_name}] Using credential_name={credential_name}")
            return UsernamePassword(
                username=cred.get("username") or default_username,
                password=cred.get("password") or default_password,
            )

    # Fall back to inline config values
    username = device.config.get("username", default_username)
    password = device.config.get("password", default_password)
    return UsernamePassword(username=username, password=password)
