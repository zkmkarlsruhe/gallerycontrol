#!/usr/bin/env python
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Create sample data for development and testing."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gallerycontrol.database.connection import get_db_manager
from gallerycontrol.database.models import Artwork, Device, Exhibition


async def create_sample_data():
    """Create sample exhibitions, artworks, and devices."""
    db = get_db_manager()

    async with db.session() as session:
        # Create exhibitions
        print("Creating sample exhibitions...")
        exhibition1 = Exhibition(
            id=uuid4(),
            name="Gallery Floor 1",
            enabled=True,
        )
        exhibition2 = Exhibition(
            id=uuid4(),
            name="Gallery Floor 2",
            enabled=True,
        )
        session.add_all([exhibition1, exhibition2])
        await session.flush()

        # Create artworks for exhibition 1
        print(f"Creating artworks for {exhibition1.name}...")
        artwork1_1 = Artwork(
            id=uuid4(),
            name="Interactive Display A",
            exhibition_id=exhibition1.id,
            enabled=True,
        )
        artwork1_2 = Artwork(
            id=uuid4(),
            name="Video Installation B",
            exhibition_id=exhibition1.id,
            enabled=True,
        )
        session.add_all([artwork1_1, artwork1_2])
        await session.flush()

        # Create artworks for exhibition 2
        print(f"Creating artworks for {exhibition2.name}...")
        artwork2_1 = Artwork(
            id=uuid4(),
            name="Projection Room C",
            exhibition_id=exhibition2.id,
            enabled=True,
        )
        session.add_all([artwork2_1])
        await session.flush()

        # Create sample devices
        print("Creating sample devices...")

        # PJLink projector for artwork 1.1
        device1 = Device(
            id=uuid4(),
            name="Main Projector",
            artwork_id=artwork1_1.id,
            device_type="pjlink",
            host="192.168.1.100",
            port=4352,
            enabled=True,
            automation_enabled=True,
                        config={"password": "panasonic"},
            state=0,
        )

        # NETIO power strip for artwork 1.2
        device2 = Device(
            id=uuid4(),
            name="Video Player Power",
            artwork_id=artwork1_2.id,
            device_type="netio",
            host="192.168.1.101",
            port=1,
            enabled=True,
            automation_enabled=True,
                        config={"username": "netio", "password": "netio"},
            state=0,
        )

        # ANEL power strip for artwork 2.1
        device3 = Device(
            id=uuid4(),
            name="Projection System Power",
            artwork_id=artwork2_1.id,
            device_type="anel",
            host="192.168.1.102",
            port=0,
            enabled=True,
            automation_enabled=True,
                        config={"username": "admin", "password": "anel"},
            state=0,
        )

        # Shell command device (excluded from auto on/off)
        device4 = Device(
            id=uuid4(),
            name="Server Control",
            artwork_id=artwork1_1.id,
            device_type="shell",
            host="localhost",
            enabled=True,
            automation_enabled=False,
                        config={
                "commands": [
                    {
                        "name": "Status",
                        "cmd": "echo 'Running'",
                        "onPattern": "Running",
                        "offPattern": "Stopped",
                    },
                    {
                        "name": "On",
                        "cmd": "echo 'Starting server...'",
                    },
                    {
                        "name": "Off",
                        "cmd": "echo 'Stopping server...'",
                    },
                ]
            },
            state=-1,
        )

        session.add_all([device1, device2, device3, device4])
        await session.commit()

        print("\n✅ Sample data created successfully!")
        print(f"\nExhibitions:")
        print(f"  - {exhibition1.name} ({exhibition1.id})")
        print(f"    - {artwork1_1.name} ({artwork1_1.id})")
        print(f"      - {device1.name} (PJLink @ {device1.host})")
        print(f"      - {device4.name} (Shell)")
        print(f"    - {artwork1_2.name} ({artwork1_2.id})")
        print(f"      - {device2.name} (NETIO @ {device2.host}:{device2.port})")
        print(f"  - {exhibition2.name} ({exhibition2.id})")
        print(f"    - {artwork2_1.name} ({artwork2_1.id})")
        print(f"      - {device3.name} (ANEL @ {device3.host}:{device3.port})")

        return {
            "exhibitions": [exhibition1, exhibition2],
            "artworks": [artwork1_1, artwork1_2, artwork2_1],
            "devices": [device1, device2, device3, device4],
        }


if __name__ == "__main__":
    asyncio.run(create_sample_data())
