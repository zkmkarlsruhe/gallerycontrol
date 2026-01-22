#!/usr/bin/env python3
"""Fix device names - use hostname as fallback."""

import json
import sqlite3
import requests

API_BASE = "http://localhost:8000/api/admin"
SQLITE_DB = "/workspace/mutech.db"

TYPE_MAP = {
    "projector": "pjlink",
    "netio": "netio",
    "anel": "anel",
}


def fix_remaining_names():
    """Fix devices that still have IP/host as name using hostname field."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    results = {"fixed": 0, "skipped": 0}

    for old_type, new_type in TYPE_MAP.items():
        print(f"\n=== Fixing {new_type} devices ===")

        # Build lookup: host -> hostname from SQLite
        cursor.execute("""
            SELECT host, hostname, args
            FROM units
            WHERE unit_type = ?
        """, (old_type,))

        hostname_lookup = {}
        for row in cursor.fetchall():
            host = row["host"]
            hostname = row["hostname"]
            args = json.loads(row["args"]) if row["args"] else {}

            # Priority: args.name > hostname
            name = args.get("name", "").strip()
            if not name and hostname:
                name = hostname

            if name:
                hostname_lookup[host] = name

        # Get current devices
        resp = requests.get(f"{API_BASE}/devices", params={"device_type": new_type})
        devices = resp.json()

        for device in devices:
            current_name = device["name"]
            host = device["host"]

            # Only fix if name equals host (IP or hostname)
            if current_name == host:
                new_name = hostname_lookup.get(host)
                if new_name and new_name != host:
                    resp = requests.put(
                        f"{API_BASE}/devices/{device['id']}",
                        json={"name": new_name}
                    )
                    if resp.status_code in (200, 204):
                        print(f"  ✓ {host} -> {new_name}")
                        results["fixed"] += 1
                    else:
                        print(f"  ✗ Failed: {host}")
                else:
                    results["skipped"] += 1
            else:
                results["skipped"] += 1

    conn.close()
    print(f"\n=== Summary ===")
    print(f"Fixed: {results['fixed']}")
    print(f"Skipped: {results['skipped']}")


if __name__ == "__main__":
    fix_remaining_names()
