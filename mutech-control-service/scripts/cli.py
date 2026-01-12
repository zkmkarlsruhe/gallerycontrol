#!/usr/bin/env python
"""Simple CLI tool for MuTech Control Service operations."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


BASE_URL = "http://localhost:8000"


async def list_exhibitions():
    """List all exhibitions."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/admin/exhibitions")
        if response.status_code == 200:
            exhibitions = response.json()
            if not exhibitions:
                print("No exhibitions found.")
                return

            print("\n📚 Exhibitions:")
            for ex in exhibitions:
                print(f"  [{ex['id'][:8]}] {ex['name']} " f"({'✓ enabled' if ex['enabled'] else '✗ disabled'})")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)


async def list_devices():
    """List all devices."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/admin/devices")
        if response.status_code == 200:
            devices = response.json()
            if not devices:
                print("No devices found.")
                return

            print("\n🔌 Devices:")
            for dev in devices:
                state_emoji = {-1: "❌", 0: "⚫", 1: "🟢", 2: "🟡", 3: "🟡"}.get(dev["state"], "❓")
                print(
                    f"  {state_emoji} [{dev['id'][:8]}] {dev['name']} "
                    f"({dev['device_type']} @ {dev['host']})"
                    f" - State: {dev['state']}"
                )
        else:
            print(f"Error: {response.status_code}")
            print(response.text)


async def control_device(device_id: str, command: str):
    """Send control command to device."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{BASE_URL}/api/control/device/{device_id}/{command}")
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Command sent: {command.upper()}")
            print(f"   Request ID: {result.get('request_id', 'N/A')[:8]}")
            print(f"   Devices targeted: {result.get('devices_targeted', 0)}")
            print(f"   Duration: {result.get('duration_ms', 0)}ms")

            if "results" in result and result["results"]:
                print(f"\n   Results:")
                for r in result["results"]:
                    success_icon = "✅" if r.get("success") else "❌"
                    print(
                        f"     {success_icon} Device {r.get('device_id', 'unknown')[:8]}: "
                        f"state={r.get('state')}, duration={r.get('duration_ms')}ms"
                    )
                    if r.get("error"):
                        print(f"        Error: {r['error']}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)


async def control_artwork(artwork_id: str, command: str):
    """Send control command to artwork."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{BASE_URL}/api/control/artwork/{artwork_id}/{command}")
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Command sent to artwork: {command.upper()}")
            print(f"   Request ID: {result.get('request_id', 'N/A')[:8]}")
            print(f"   Devices targeted: {result.get('devices_targeted', 0)}")
            print(f"   Duration: {result.get('duration_ms', 0)}ms")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)


async def control_exhibition(exhibition_id: str, command: str):
    """Send control command to exhibition."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{BASE_URL}/api/control/exhibition/{exhibition_id}/{command}")
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Command sent to exhibition: {command.upper()}")
            print(f"   Request ID: {result.get('request_id', 'N/A')[:8]}")
            print(f"   Devices targeted: {result.get('devices_targeted', 0)}")
            print(f"   Duration: {result.get('duration_ms', 0)}ms")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)


async def health_check():
    """Check service health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                print("✅ Service is healthy")
                print(response.json())
            else:
                print(f"❌ Service returned {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ Service is not reachable: {e}")
        print(f"   Make sure the service is running at {BASE_URL}")
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MuTech Control Service CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Health check
    subparsers.add_parser("health", help="Check service health")

    # List commands
    subparsers.add_parser("list-exhibitions", help="List all exhibitions")
    subparsers.add_parser("list-devices", help="List all devices")

    # Control commands
    device_parser = subparsers.add_parser("device", help="Control a device")
    device_parser.add_argument("device_id", help="Device ID")
    device_parser.add_argument("action", choices=["on", "off"], help="Command to send")

    artwork_parser = subparsers.add_parser("artwork", help="Control an artwork")
    artwork_parser.add_argument("artwork_id", help="Artwork ID")
    artwork_parser.add_argument("action", choices=["on", "off"], help="Command to send")

    exhibition_parser = subparsers.add_parser("exhibition", help="Control an exhibition")
    exhibition_parser.add_argument("exhibition_id", help="Exhibition ID")
    exhibition_parser.add_argument("action", choices=["on", "off"], help="Command to send")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate function
    if args.command == "health":
        asyncio.run(health_check())
    elif args.command == "list-exhibitions":
        asyncio.run(list_exhibitions())
    elif args.command == "list-devices":
        asyncio.run(list_devices())
    elif args.command == "device":
        asyncio.run(control_device(args.device_id, args.action))
    elif args.command == "artwork":
        asyncio.run(control_artwork(args.artwork_id, args.action))
    elif args.command == "exhibition":
        asyncio.run(control_exhibition(args.exhibition_id, args.action))


if __name__ == "__main__":
    main()
