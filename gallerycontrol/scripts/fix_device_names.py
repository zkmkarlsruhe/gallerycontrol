#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Fix device names from SQLite database."""

import json
import sqlite3
import requests

API_BASE = "http://localhost:8000/api/admin"
SQLITE_DB = "/workspace/mutech.db"

# Map old unit_type to new device_type
TYPE_MAP = {
    "projector": "pjlink",
    "netio": "netio",
    "anel": "anel",
}


def get_devices_by_type(device_type: str) -> list:
    """Get all devices of a type from API."""
    resp = requests.get(f"{API_BASE}/devices", params={"device_type": device_type})
    return resp.json()


def update_device_name(device_id: str, name: str) -> bool:
    """Update device name via API."""
    resp = requests.put(f"{API_BASE}/devices/{device_id}", json={"name": name})
    return resp.status_code in (200, 204)


def fix_device_names():
    """Fix device names from SQLite data."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    results = {"fixed": 0, "skipped": 0, "not_found": 0}

    for old_type, new_type in TYPE_MAP.items():
        print(f"\n=== Fixing {new_type} devices ===")

        # Get original data from SQLite
        cursor.execute("""
            SELECT id, host, hostname, args
            FROM units
            WHERE unit_type = ?
        """, (old_type,))

        # Build lookup by host
        original_data = {}
        for row in cursor.fetchall():
            host = row["host"]
            args = json.loads(row["args"]) if row["args"] else {}

            # Get name from args, or fall back to hostname
            name = args.get("name", "").strip()
            if not name and row["hostname"]:
                # Use hostname but make it nicer (e.g., panasonic-pt-d4000e-100016026.zkm.de -> Panasonic PT-D4000E)
                hostname = row["hostname"]
                # Keep as-is for now, or extract model
                name = ""

            if name:
                original_data[host] = name

        print(f"  Found {len(original_data)} devices with names in SQLite")

        # Get current devices from API
        devices = get_devices_by_type(new_type)
        print(f"  Found {len(devices)} devices in API")

        for device in devices:
            current_name = device["name"]
            host = device["host"]

            # Check if name matches host (meaning it was set incorrectly)
            if current_name == host:
                # Look up original name
                original_name = original_data.get(host)
                if original_name:
                    if update_device_name(device["id"], original_name):
                        print(f"  ✓ Fixed: {host} -> {original_name}")
                        results["fixed"] += 1
                    else:
                        print(f"  ✗ Failed to update: {host}")
                else:
                    # No original name found, skip
                    results["not_found"] += 1
            else:
                # Name is already different from host, skip
                results["skipped"] += 1

    conn.close()

    print(f"\n=== Summary ===")
    print(f"Fixed: {results['fixed']}")
    print(f"Skipped (already named): {results['skipped']}")
    print(f"Not found in SQLite: {results['not_found']}")


if __name__ == "__main__":
    fix_device_names()
