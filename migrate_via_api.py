#!/usr/bin/env python3
"""Migrate data from SQLite to the new API."""

import json
import sqlite3
import httpx

API_BASE = "http://localhost:8000/api/admin"
SQLITE_DB = "/workspace/mutech.db"

def row_to_dict(cursor, row):
    """Convert sqlite row to dict."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def migrate():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    client = httpx.Client(timeout=30.0)

    # Step 1: Migrate exhibitions
    print("\n=== Migrating Exhibitions ===")
    cursor.execute("SELECT * FROM exhibits ORDER BY name")
    exhibits = cursor.fetchall()

    exhibition_map = {}  # old_id -> new_id

    for exhibit in exhibits:
        old_id = exhibit["id"]
        name = exhibit["name"]

        response = client.post(f"{API_BASE}/exhibitions", json={
            "name": name,
            "enabled": True
        })

        if response.status_code == 201:
            new_id = response.json()["id"]
            exhibition_map[old_id] = new_id
            print(f"  Created exhibition: {name} ({old_id} -> {new_id})")
        else:
            print(f"  ERROR creating exhibition {name}: {response.text}")

    print(f"\nMigrated {len(exhibition_map)} exhibitions")

    # Step 2: Migrate artworks (works)
    print("\n=== Migrating Artworks ===")
    cursor.execute("SELECT * FROM works ORDER BY name")
    works = cursor.fetchall()

    artwork_map = {}  # old_id -> new_id

    for work in works:
        old_id = work["id"]
        name = work["name"]
        parent_id = work["parent_id"]

        new_exhibition_id = exhibition_map.get(parent_id)
        if not new_exhibition_id:
            print(f"  SKIP artwork {name}: no exhibition mapping for {parent_id}")
            continue

        response = client.post(f"{API_BASE}/artworks", json={
            "exhibition_id": new_exhibition_id,
            "name": name,
            "enabled": True
        })

        if response.status_code == 201:
            new_id = response.json()["id"]
            artwork_map[old_id] = new_id
            print(f"  Created artwork: {name} ({old_id} -> {new_id})")
        else:
            print(f"  ERROR creating artwork {name}: {response.text}")

    print(f"\nMigrated {len(artwork_map)} artworks")

    # Step 3: Migrate devices (units)
    print("\n=== Migrating Devices ===")
    cursor.execute("SELECT * FROM units ORDER BY host")
    units = cursor.fetchall()

    device_type_map = {
        "projector": "pjlink",
        "netio": "netio",
        "anel": "anel",
        "shell": "shell",
    }

    migrated = 0
    skipped = 0

    for unit in units:
        old_id = unit["id"]
        parent_id = unit["parent_id"]
        host = unit["host"]
        unit_type = unit["unit_type"]
        automation = bool(unit["automation"])
        active = bool(unit["active"])
        args_str = unit["args"] or "{}"

        new_artwork_id = artwork_map.get(parent_id)
        if not new_artwork_id:
            print(f"  SKIP device {host}: no artwork mapping for {parent_id}")
            skipped += 1
            continue

        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}

        device_type = device_type_map.get(unit_type, unit_type)

        # Build device config based on type
        config = {}

        if device_type == "pjlink":
            # PJLink projector
            password = args.get("password", "")
            port = args.get("port", "") or None
            name = args.get("name", "") or host

            config = {}
            if password:
                config["credential_name"] = "panasonic"  # Use credential store

        elif device_type == "netio":
            # NETIO power strip - port is the outlet number
            port_num = args.get("port", "0")
            name = args.get("name", "") or f"Port {port_num}"
            config = {"outlet": int(port_num) if port_num else 0}

        elif device_type == "anel":
            # ANEL power strip - port is the outlet number
            port_num = args.get("port", "0")
            name = args.get("name", "") or f"Port {port_num}"
            config = {"outlet": int(port_num) if port_num else 0}

        elif device_type == "shell":
            # Shell device - convert old command format to new
            shell_name = args.get("name", "Shell")
            commands = args.get("commands", [])

            # Convert commands to new format
            new_commands = {}
            for cmd in commands:
                cmd_name = cmd.get("name", "").lower()
                cmd_str = cmd.get("cmd", "")
                on_msg = cmd.get("onMsg", "")
                off_msg = cmd.get("offMsg", "")

                if cmd_name == "status":
                    new_commands["status"] = {
                        "cmd": cmd_str,
                        "onPattern": on_msg,
                        "offPattern": off_msg
                    }
                elif cmd_name == "on":
                    new_commands["on"] = {"cmd": cmd_str}
                elif cmd_name == "off":
                    new_commands["off"] = {"cmd": cmd_str}
                elif cmd_name == "reachable":
                    new_commands["reachable"] = {"cmd": cmd_str}
                elif cmd_name in ["restart", "restart app", "reboot"]:
                    new_commands[cmd_name.replace(" ", "_")] = {"cmd": cmd_str}

            name = shell_name
            config = {"commands": new_commands}

        else:
            name = host
            config = args

        # Create device via API
        device_data = {
            "artwork_id": new_artwork_id,
            "name": name,
            "device_type": device_type,
            "host": host,
            "port": None,  # Port is stored in config for power strips
            "enabled": active,
            "automation_enabled": automation,
            "config": config
        }

        response = client.post(f"{API_BASE}/devices", json=device_data)

        if response.status_code == 201:
            new_id = response.json()["id"]
            migrated += 1
            print(f"  Created device: {name} @ {host} ({device_type})")
        else:
            print(f"  ERROR creating device {host}: {response.text}")
            skipped += 1

    print(f"\nMigrated {migrated} devices ({skipped} skipped)")

    conn.close()
    client.close()
    print("\n=== Migration Complete ===")

if __name__ == "__main__":
    migrate()
