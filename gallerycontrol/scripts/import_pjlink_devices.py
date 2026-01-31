#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Import PJLink (projector) devices from SQLite database."""

import json
import sqlite3
import requests

API_BASE = "http://localhost:8000/api/admin"
SQLITE_DB = "/workspace/mutech.db"


def get_credential_id(password: str) -> str | None:
    """Get credential ID by password value."""
    if not password:
        return None
    resp = requests.get(f"{API_BASE}/credentials")
    for cred in resp.json():
        # Match by name (e.g., 'panasonic' password -> 'panasonic' credential)
        if cred["name"] == password:
            return cred["id"]
    return None


def get_artwork_id(work_name: str, exhibit_name: str) -> str | None:
    """Find artwork ID by name and exhibition."""
    resp = requests.get(f"{API_BASE}/artworks")
    artworks = resp.json()

    # Exact match first
    for artwork in artworks:
        if artwork["name"] == work_name and artwork.get("exhibition_name") == exhibit_name:
            return artwork["id"]

    # Partial match fallback
    for artwork in artworks:
        if artwork["name"] == work_name:
            return artwork["id"]

    return None


def import_pjlink_devices():
    """Import all PJLink devices from SQLite."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.id,
            u.host,
            u.hostname,
            u.args,
            u.automation,
            u.active,
            u.state,
            w.name as work_name,
            e.name as exhibit_name
        FROM units u
        JOIN works w ON u.parent_id = w.id
        JOIN exhibits e ON w.parent_id = e.id
        WHERE u.unit_type = 'projector'
    """)

    results = {"imported": 0, "failed": 0, "skipped": 0, "errors": []}

    for row in cursor.fetchall():
        try:
            args = json.loads(row["args"]) if row["args"] else {}

            # Name priority: args.name > host (hostname is resolved DNS, not user input)
            name = args.get("name", "").strip() or row["host"]

            # Get artwork ID
            artwork_id = get_artwork_id(row["work_name"], row["exhibit_name"])
            if not artwork_id:
                results["errors"].append(f"Artwork not found: {row['work_name']} / {row['exhibit_name']}")
                results["skipped"] += 1
                continue

            # Get credential ID
            credential_id = get_credential_id(args.get("password", ""))

            # Build device data
            device_data = {
                "artwork_id": artwork_id,
                "name": name,
                "device_type": "pjlink",
                "host": row["host"],
                "port": int(args.get("port") or 4352),
                "enabled": bool(row["active"]),
                "automation_enabled": bool(row["automation"]),
                "config": {}
            }

            if credential_id:
                device_data["config"]["credential_id"] = credential_id

            # Create device
            resp = requests.post(f"{API_BASE}/devices", json=device_data)
            if resp.status_code in (200, 201):
                results["imported"] += 1
                print(f"✓ {name} ({row['work_name']})")
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed: {name} - {resp.text}")
                print(f"✗ {name} - {resp.status_code}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Error: {row['host']} - {str(e)}")
            print(f"✗ Error: {row['host']} - {e}")

    conn.close()

    print(f"\n=== PJLink Import Complete ===")
    print(f"Imported: {results['imported']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped: {results['skipped']}")

    if results["errors"][:5]:
        print(f"\nFirst errors:")
        for err in results["errors"][:5]:
            print(f"  - {err}")

    return results


if __name__ == "__main__":
    import_pjlink_devices()
