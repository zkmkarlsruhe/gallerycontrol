#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Remove obsolete 'reachable' commands from shell devices via API."""

import json
import httpx

API_BASE = "http://localhost:8000/api/admin"

def cleanup():
    client = httpx.Client(timeout=30.0)

    # Get all devices
    response = client.get(f"{API_BASE}/devices")
    devices = response.json()

    shell_devices = [d for d in devices if d.get("device_type") == "shell"]
    print(f"Found {len(shell_devices)} shell devices")

    updated = 0
    for device in shell_devices:
        config = device.get("config", {})
        commands = config.get("commands", {})

        if "reachable" in commands:
            # Remove reachable command
            del commands["reachable"]
            config["commands"] = commands

            # Update device via PUT
            response = client.put(
                f"{API_BASE}/devices/{device['id']}",
                json={"config": config}
            )

            if response.status_code == 200:
                print(f"  Updated: {device['name']}")
                updated += 1
            else:
                print(f"  ERROR updating {device['name']}: {response.text}")

    print(f"\nUpdated {updated} devices")
    client.close()

if __name__ == "__main__":
    cleanup()
