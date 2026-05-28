# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Inventory export service for generating device inventory reports."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from gallerycontrol.config import get_config

logger = logging.getLogger(__name__)

# Sort order for device types within an artwork
_DEVICE_TYPE_ORDER = {"pjlink": 0, "netio": 1, "anel": 2, "shell": 3}


def _device_sort_key(device: dict) -> tuple:
    """Sort devices by type (projectors first, then power strips, then shell)."""
    device_type = device.get("device_type", "")
    return (_DEVICE_TYPE_ORDER.get(device_type, 99), device.get("host", ""))


def format_device_line(device: dict, for_html: bool = False) -> str:
    """Format a single device into inventory line(s).

    Args:
        device: Device dict with device_type, host, port, config, name
        for_html: If True, format for HTML output

    Returns:
        Formatted string for the device
    """
    device_type = device.get("device_type", "")
    host = device.get("host", "")
    port = device.get("port")
    name = device.get("name", "")
    config = device.get("config") or {}

    prefix = "  - " if not for_html else ""

    if device_type == "pjlink":
        label = f"{name}: " if name else "Projektor: "
        return f"{prefix}{label}http://{host}"

    elif device_type in ("netio", "anel"):
        # Display 1-indexed port (matches physical device labeling)
        port_num = (port + 1) if port is not None else 1
        label = f"{name}: " if name else "Steckdose: "
        return f"{prefix}{label}http://{host} Port {port_num}"

    elif device_type == "shell":
        # Extract status command from config
        commands = config.get("commands", {})
        status_cmd = None

        # Handle both dict and list format
        if isinstance(commands, dict):
            status_cfg = commands.get("status", {})
            if isinstance(status_cfg, dict):
                status_cmd = status_cfg.get("cmd")
        elif isinstance(commands, list):
            for cmd in commands:
                if isinstance(cmd, dict) and cmd.get("name", "").lower() == "status":
                    status_cmd = cmd.get("cmd")
                    break

        label = name or "Shell"
        if status_cmd:
            if for_html:
                return f"{label}<br>&nbsp;&nbsp;&nbsp;&nbsp;{status_cmd}"
            else:
                return f"{prefix}{label}\n      {status_cmd}"
        else:
            return f"{prefix}{label}"

    else:
        # Unknown device type
        label = name or device_type
        return f"{prefix}{label}: {host}"


def generate_inventory_text(exhibitions: list[dict]) -> str:
    """Generate plain text inventory from exhibition data.

    Args:
        exhibitions: List of exhibition dicts with nested artworks and devices

    Returns:
        Plain text formatted inventory string suitable for email
    """
    lines = []

    for exhibition in sorted(exhibitions, key=lambda x: x.get("name", "")):
        exhibition_name = exhibition.get("name", "Unknown Exhibition")
        artworks = exhibition.get("artworks", [])

        # Filter to enabled artworks with enabled devices
        enabled_artworks = []
        for artwork in artworks:
            if not artwork.get("effective_enabled", True):
                continue

            enabled_devices = [
                d for d in artwork.get("devices", [])
                if d.get("effective_enabled", True)
            ]

            if enabled_devices:
                enabled_artworks.append({
                    **artwork,
                    "devices": enabled_devices
                })

        # Skip exhibition if no enabled artworks with devices
        if not enabled_artworks:
            continue

        # Add exhibition header with separator
        if lines:
            lines.append("")
        lines.append("=" * 50)
        lines.append(exhibition_name.upper())
        lines.append("=" * 50)

        for artwork in sorted(enabled_artworks, key=lambda x: x.get("name", "")):
            artwork_name = artwork.get("name", "Unknown Artwork")
            devices = artwork.get("devices", [])

            # Add artwork header
            lines.append("")
            lines.append(artwork_name)

            # Add device lines (sorted by type)
            for device in sorted(devices, key=_device_sort_key):
                lines.append(format_device_line(device))

    return "\n".join(lines)


def generate_inventory_html(exhibitions: list[dict]) -> str:
    """Generate HTML inventory from exhibition data.

    Args:
        exhibitions: List of exhibition dicts with nested artworks and devices

    Returns:
        HTML-formatted inventory string suitable for email
    """
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.5; color: #333; max-width: 600px; }",
        ".exhibition { margin-bottom: 24px; }",
        ".exhibition-header { background: #f5f5f5; padding: 8px 12px; font-weight: bold; border-left: 3px solid #666; margin-bottom: 12px; }",
        ".artwork { margin-bottom: 16px; margin-left: 8px; }",
        ".artwork-name { font-weight: 600; margin-bottom: 4px; }",
        ".device { margin-left: 16px; color: #555; padding: 2px 0; }",
        ".device-indent { margin-left: 32px; color: #777; font-size: 13px; }",
        "</style>",
        "</head>",
        "<body>",
    ]

    for exhibition in sorted(exhibitions, key=lambda x: x.get("name", "")):
        exhibition_name = exhibition.get("name", "Unknown Exhibition")
        artworks = exhibition.get("artworks", [])

        # Filter to enabled artworks with enabled devices
        enabled_artworks = []
        for artwork in artworks:
            if not artwork.get("effective_enabled", True):
                continue

            enabled_devices = [
                d for d in artwork.get("devices", [])
                if d.get("effective_enabled", True)
            ]

            if enabled_devices:
                enabled_artworks.append({
                    **artwork,
                    "devices": enabled_devices
                })

        # Skip exhibition if no enabled artworks with devices
        if not enabled_artworks:
            continue

        html_lines.append('<div class="exhibition">')
        html_lines.append(f'<div class="exhibition-header">{exhibition_name}</div>')

        for artwork in sorted(enabled_artworks, key=lambda x: x.get("name", "")):
            artwork_name = artwork.get("name", "Unknown Artwork")
            devices = artwork.get("devices", [])

            html_lines.append('<div class="artwork">')
            html_lines.append(f'<div class="artwork-name">{artwork_name}</div>')

            for device in sorted(devices, key=_device_sort_key):
                device_line = format_device_line(device, for_html=True)
                html_lines.append(f'<div class="device">{device_line}</div>')

            html_lines.append('</div>')

        html_lines.append('</div>')

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


async def send_inventory_email(
    recipients: list[str],
    subject: str,
    exhibitions: list[dict],
) -> dict[str, Any]:
    """Send inventory email via SMTP.

    Args:
        recipients: List of email addresses
        subject: Email subject line
        exhibitions: List of exhibition dicts with nested artworks and devices

    Returns:
        Dict with success status and message
    """
    config = get_config()

    smtp_host = config.get("email.smtp_host")
    smtp_port = config.get("email.smtp_port", 587)
    smtp_user = config.get("email.smtp_user")
    smtp_password = config.get("email.smtp_password")
    smtp_use_tls = config.get("email.smtp_use_tls", True)
    from_address = config.get("email.from_address")

    # Validate configuration
    if not smtp_host:
        return {
            "success": False,
            "message": "SMTP host not configured. Set SMTP_HOST environment variable.",
        }

    if not from_address:
        return {
            "success": False,
            "message": "From address not configured. Set EMAIL_FROM environment variable.",
        }

    if not recipients:
        return {
            "success": False,
            "message": "No recipients specified.",
        }

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = ", ".join(recipients)

        # Attach plain text version
        text_content = generate_inventory_text(exhibitions)
        text_part = MIMEText(text_content, "plain", "utf-8")
        msg.attach(text_part)

        # Attach HTML version
        html_content = generate_inventory_html(exhibitions)
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        # Send email
        # Port 465 uses implicit SSL (SMTP_SSL), other ports use STARTTLS
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        elif smtp_use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(from_address, recipients, msg.as_string())
        server.quit()

        logger.info(f"Inventory email sent to {len(recipients)} recipient(s)")
        return {
            "success": True,
            "message": f"Email sent to {len(recipients)} recipient(s)",
            "recipients": recipients,
        }

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return {
            "success": False,
            "message": "SMTP authentication failed. Check credentials.",
        }
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return {
            "success": False,
            "message": f"SMTP error: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Failed to send inventory email: {e}")
        return {
            "success": False,
            "message": f"Failed to send email: {str(e)}",
        }
