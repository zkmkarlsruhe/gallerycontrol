#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Import shell devices from SQLite database to the new system."""

import json
import re
import sqlite3
import requests
from typing import Optional

API_BASE = "http://localhost:8000/api/admin"
SQLITE_DB = "/workspace/mutech.db"

# Credential mapping: old file path -> new credential name
CREDENTIAL_MAP = {
    "/root/.ssh/museumstechnik.txt": "museumstechnik",
}


def get_credential_id(name: str) -> Optional[str]:
    """Get credential ID by name."""
    resp = requests.get(f"{API_BASE}/credentials")
    for cred in resp.json():
        if cred["name"] == name:
            return cred["id"]
    return None


def get_artwork_id(work_name: str, exhibit_name: str) -> Optional[str]:
    """Find artwork ID by name and exhibition."""
    resp = requests.get(f"{API_BASE}/artworks")
    for artwork in resp.json():
        if artwork["name"] == work_name and artwork.get("exhibition_name") == exhibit_name:
            return artwork["id"]
    # Try partial match
    for artwork in resp.json():
        if artwork["name"] == work_name:
            return artwork["id"]
    return None


def extract_target_host(args_json: str) -> Optional[str]:
    """Extract target host from shell commands."""
    # Look for hostnames
    hostnames = re.findall(r'[a-zA-Z0-9-]+\.zkm\.de', args_json)
    if hostnames:
        return hostnames[0]

    # Look for IPs
    ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', args_json)
    if ips:
        return ips[0]

    return None


def convert_command(cmd: str) -> tuple[str, Optional[str]]:
    """Convert old command format to new format with credential placeholders.

    Returns: (converted_cmd, credential_name)
    """
    credential_name = None

    # Convert: sshpass -f /path/to/file.txt ssh user@host
    # To: sshpass -p {{PASSWORD}} ssh {{USER}}@host
    match = re.search(r'sshpass -f ([^\s]+)', cmd)
    if match:
        file_path = match.group(1)
        credential_name = CREDENTIAL_MAP.get(file_path)
        if credential_name:
            # Replace file-based password with placeholder
            cmd = re.sub(r'sshpass -f [^\s]+', 'sshpass -p {{PASSWORD}}', cmd)
            # Replace username with placeholder (e.g., museumstechnik@host -> {{USER}}@host)
            cmd = re.sub(r'(\s)museumstechnik@', r'\1{{USER}}@', cmd)

    return cmd, credential_name


def parse_old_format(args: dict) -> dict:
    """Parse old args format to new config format."""
    name = args.get("name", "Device")
    commands = args.get("commands", [])

    new_config = {
        "commands": {},
        "actions": []
    }
    credential_name = None

    for cmd_entry in commands:
        cmd_name = cmd_entry.get("name", "").lower()
        cmd_str = cmd_entry.get("cmd", "")
        on_msg = cmd_entry.get("onMsg", "")
        off_msg = cmd_entry.get("offMsg", "")

        # Convert command
        converted_cmd, cred = convert_command(cmd_str)
        if cred:
            credential_name = cred

        if cmd_name == "status":
            new_config["commands"]["status"] = {
                "cmd": converted_cmd,
                "onPattern": on_msg if on_msg else None,
                "offPattern": off_msg if off_msg else None,
            }
        elif cmd_name == "on":
            new_config["commands"]["on"] = {"cmd": converted_cmd}
        elif cmd_name == "off":
            new_config["commands"]["off"] = {"cmd": converted_cmd}
        elif cmd_name == "reachable":
            # Skip reachable - not needed in new system
            pass
        else:
            # Custom action
            new_config["actions"].append({
                "name": cmd_entry.get("name", cmd_name),
                "cmd": converted_cmd
            })

    return name, new_config, credential_name


def import_shell_devices():
    """Import all shell devices from SQLite."""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all shell units with their parent work and exhibit
    cursor.execute("""
        SELECT
            u.id,
            u.host,
            u.args,
            u.automation,
            u.active,
            u.state,
            w.name as work_name,
            e.name as exhibit_name
        FROM units u
        JOIN works w ON u.parent_id = w.id
        JOIN exhibits e ON w.parent_id = e.id
        WHERE u.unit_type = 'shell'
    """)

    results = {"imported": 0, "failed": 0, "skipped": 0, "errors": []}

    for row in cursor.fetchall():
        try:
            args = json.loads(row["args"]) if row["args"] else {}

            # Parse old format
            device_name, config, credential_name = parse_old_format(args)

            # Extract target host
            target_host = extract_target_host(row["args"] or "")
            if target_host:
                config["target_host"] = target_host

            # Get credential ID
            if credential_name:
                cred_id = get_credential_id(credential_name)
                if cred_id:
                    config["credential_id"] = cred_id

            # Get artwork ID
            artwork_id = get_artwork_id(row["work_name"], row["exhibit_name"])
            if not artwork_id:
                results["errors"].append(f"Artwork not found: {row['work_name']} / {row['exhibit_name']}")
                results["skipped"] += 1
                continue

            # Determine host field
            host = target_host if target_host else "#nohost"

            # Check if has on/off commands for automation
            has_onoff = bool(config["commands"].get("on") or config["commands"].get("off"))

            # Create device
            device_data = {
                "artwork_id": artwork_id,
                "name": device_name,
                "device_type": "shell",
                "host": host,
                "enabled": bool(row["active"]),
                "automation_enabled": bool(row["automation"]) and has_onoff,
                "config": config,
            }

            resp = requests.post(f"{API_BASE}/devices", json=device_data)
            if resp.status_code in (200, 201):
                results["imported"] += 1
                print(f"✓ Imported: {device_name} ({row['work_name']}) -> {target_host or '#nohost'}")
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed to create {device_name}: {resp.text}")
                print(f"✗ Failed: {device_name} - {resp.status_code}")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Error processing {row['id']}: {str(e)}")
            print(f"✗ Error: {row['id']} - {e}")

    conn.close()

    print(f"\n=== Import Complete ===")
    print(f"Imported: {results['imported']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped: {results['skipped']}")

    if results["errors"]:
        print(f"\nErrors:")
        for err in results["errors"][:10]:
            print(f"  - {err}")

    return results


if __name__ == "__main__":
    # First delete the test device we created earlier
    print("Deleting test device...")
    resp = requests.get(f"{API_BASE}/devices?device_type=shell")
    for device in resp.json():
        requests.delete(f"{API_BASE}/devices/{device['id']}")
        print(f"  Deleted: {device['name']}")

    print("\nImporting shell devices from SQLite...\n")
    import_shell_devices()
