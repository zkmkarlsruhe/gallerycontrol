#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""
Standalone test script for MuTech Control System

Tests the system without Docker by:
1. Using in-memory SQLite database
2. Mocking device managers
3. Testing all core functionality

Run: python3 scripts/test_standalone.py
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mutech-control-service"))

# Patch SQLAlchemy types for SQLite compatibility BEFORE importing models
from sqlalchemy import JSON, String, create_engine, select
from sqlalchemy import types as sqltypes
from sqlalchemy.dialects import postgresql

# Replace JSONB with JSON for SQLite
postgresql.JSONB = JSON

# Replace UUID with String for SQLite
class TextUUID(sqltypes.TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        from uuid import UUID
        return UUID(value)

postgresql.UUID = TextUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from mutech_control.database.models import Base, Exhibition, Artwork, Device, CommandLog
from mutech_control.devices.base import DeviceManager, DeviceResult, ConnectionResult
from mutech_control.orchestrator.command_orchestrator import CommandOrchestrator
from mutech_control.database.connection import DatabaseManager


# Mock Device Manager
class MockDeviceManager(DeviceManager):
    """Mock device manager that simulates device responses."""

    def __init__(self, config: dict, device_type: str):
        self.config = config
        self.device_type = device_type
        self._device_states = {}  # Track states per device

    async def get_state(self, device) -> DeviceResult:
        """Return mock state."""
        current_state = self._device_states.get(str(device.id), 0)
        return DeviceResult(
            success=True,
            state=current_state,
            error=None,
            duration_ms=50
        )

    async def set_power(self, device, on: bool) -> DeviceResult:
        """Simulate power change."""
        new_state = 1 if on else 0
        self._device_states[str(device.id)] = new_state

        await asyncio.sleep(0.1)  # Simulate network delay

        return DeviceResult(
            success=True,
            state=new_state,
            error=None,
            duration_ms=100
        )

    async def test_connection(self, device) -> ConnectionResult:
        """Simulate connection test."""
        return ConnectionResult(success=True, error=None)

    async def close(self):
        """Cleanup."""
        pass


# Test Database Manager
class TestDatabaseManager:
    """Database manager using in-memory SQLite."""

    def __init__(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False
        )
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def initialize(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self):
        """Get database session as context manager."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_session(self):
        """Get database session (for tests)."""
        async with self.session() as session:
            yield session

    async def close(self):
        """Close engine."""
        await self.engine.dispose()

    async def update_device_state(self, device_id: str, state: int):
        """Update device state."""
        async with self.session() as session:
            # Convert string UUID to UUID object for query
            from uuid import UUID
            device = await session.get(Device, UUID(device_id))
            if device:
                device.state = state
                device.last_checked_at = datetime.utcnow()
                await session.commit()

    async def log_command(
        self,
        device_id: str,
        command: str,
        source: str,
        success: bool,
        error_message: str | None,
        duration_ms: int
    ):
        """Log command execution."""
        async with self.session() as session:
            log = CommandLog(
                device_id=device_id,
                command=command,
                source=source,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms
            )
            session.add(log)
            await session.commit()


# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_error(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


async def create_test_data(db: TestDatabaseManager):
    """Create test exhibition, artworks, and devices."""
    print_info("Creating test data...")

    async for session in db.get_session():
        # Create exhibition
        exhibition = Exhibition(
            id=uuid4(),
            name="Test Exhibition",
            enabled=True
        )
        session.add(exhibition)
        await session.flush()
        print_success(f"Created exhibition: {exhibition.name} (ID: {exhibition.id})")

        # Create artwork
        artwork = Artwork(
            id=uuid4(),
            exhibition_id=exhibition.id,
            name="Test Artwork",
            enabled=True
        )
        session.add(artwork)
        await session.flush()
        print_success(f"Created artwork: {artwork.name} (ID: {artwork.id})")

        # Create devices of each type
        devices = []

        # PJLink projector
        devices.append(Device(
            id=uuid4(),
            artwork_id=artwork.id,
            name="Mock PJLink Projector",
            device_type="pjlink",
            host="192.168.1.100",
            port=4352,
            enabled=True,
            automation_enabled=True,
            exclude_from_auto_onoff=False,
            config={"password": "test"},
            state=0
        ))

        # NETIO outlet
        devices.append(Device(
            id=uuid4(),
            artwork_id=artwork.id,
            name="Mock NETIO Outlet",
            device_type="netio",
            host="192.168.1.101",
            port=80,
            enabled=True,
            automation_enabled=True,
            exclude_from_auto_onoff=False,
            config={"username": "admin", "password": "test", "port_number": 1},
            state=0
        ))

        # ANEL outlet
        devices.append(Device(
            id=uuid4(),
            artwork_id=artwork.id,
            name="Mock ANEL Outlet",
            device_type="anel",
            host="192.168.2.100",
            port=75,
            enabled=True,
            automation_enabled=True,
            exclude_from_auto_onoff=False,
            config={"username": "admin", "password": "test", "port_number": 1},
            state=0
        ))

        # Shell command
        devices.append(Device(
            id=uuid4(),
            artwork_id=artwork.id,
            name="Mock Shell Command",
            device_type="shell",
            host="localhost",
            enabled=True,
            automation_enabled=True,
            exclude_from_auto_onoff=False,
            config={
                "commands": {
                    "on": {"cmd": "echo on", "timeout": 5},
                    "off": {"cmd": "echo off", "timeout": 5},
                    "status": {"cmd": "echo status", "timeout": 5}
                }
            },
            state=0
        ))

        # Shell reboot (excluded from auto on/off)
        devices.append(Device(
            id=uuid4(),
            artwork_id=artwork.id,
            name="Mock Reboot Command (Excluded)",
            device_type="shell",
            host="localhost",
            enabled=True,
            automation_enabled=True,
            exclude_from_auto_onoff=True,  # This one is excluded
            config={
                "commands": {
                    "on": {"cmd": "echo reboot", "timeout": 5}
                }
            },
            state=0
        ))

        for device in devices:
            session.add(device)
            print_success(f"Created device: {device.name} ({device.device_type}, Excluded: {device.exclude_from_auto_onoff})")

        await session.commit()

        return exhibition.id, artwork.id, [str(d.id) for d in devices]


async def test_control_operations(db: TestDatabaseManager, orchestrator: CommandOrchestrator, exhibition_id: str, artwork_id: str):
    """Test control operations."""
    print_info("\nTesting control operations...")

    # Test 1: Turn on exhibition
    print_info("Test 1: Turn ON exhibition (should stagger devices by 1 second)...")
    start_time = asyncio.get_event_loop().time()
    result = await orchestrator.execute_control_command(
        target_type="exhibition",
        target_id=str(exhibition_id),
        command="on",
        source="web"
    )
    elapsed = asyncio.get_event_loop().time() - start_time

    if result.get("success"):
        devices_targeted = result.get("devices_targeted", 0)
        print_success(f"Exhibition turned ON successfully")
        print_info(f"  - Devices targeted: {devices_targeted}")
        print_info(f"  - Time elapsed: {elapsed:.2f}s")

        # Check if stagger worked (should be ~4 seconds for 4 devices, 1 excluded)
        if elapsed >= 3.0:  # At least 3 seconds for 4 devices
            print_success(f"  - Stagger delay working correctly")
        else:
            print_warning(f"  - Stagger may not be working (expected ~4s, got {elapsed:.2f}s)")
    else:
        print_error("Failed to turn ON exhibition")

    # Test 2: Check device states
    print_info("\nTest 2: Checking device states...")
    async for session in db.get_session():
        stmt = select(Device).where(Device.state != -1)
        result = await session.execute(stmt)
        devices = result.scalars().all()

        on_count = sum(1 for d in devices if d.state == 1)
        off_count = sum(1 for d in devices if d.state == 0)
        excluded_count = sum(1 for d in devices if d.exclude_from_auto_onoff)

        print_info(f"  - Total devices: {len(devices)}")
        print_info(f"  - Devices ON: {on_count}")
        print_info(f"  - Devices OFF: {off_count}")
        print_info(f"  - Excluded devices: {excluded_count}")

        # Verify excluded device was not turned on
        excluded_devices = [d for d in devices if d.exclude_from_auto_onoff]
        if excluded_devices:
            for device in excluded_devices:
                if device.state == 0:
                    print_success(f"  - Excluded device '{device.name}' correctly NOT turned on")
                else:
                    print_error(f"  - Excluded device '{device.name}' was incorrectly turned on!")

    # Test 3: Turn off exhibition
    print_info("\nTest 3: Turn OFF exhibition (should broadcast)...")
    start_time = asyncio.get_event_loop().time()
    result = await orchestrator.execute_control_command(
        target_type="exhibition",
        target_id=str(exhibition_id),
        command="off",
        source="web"
    )
    elapsed = asyncio.get_event_loop().time() - start_time

    if result.get("success"):
        print_success(f"Exhibition turned OFF successfully")
        print_info(f"  - Time elapsed: {elapsed:.2f}s")

        # OFF should be fast (broadcast, no stagger)
        if elapsed < 2.0:
            print_success(f"  - Broadcast working correctly (fast)")
        else:
            print_warning(f"  - OFF took longer than expected ({elapsed:.2f}s)")
    else:
        print_error("Failed to turn OFF exhibition")

    # Wait a bit for state verifier to check (though it won't do much with mocks)
    await asyncio.sleep(1)

    # Test 4: Check command log
    print_info("\nTest 4: Checking command log...")
    async for session in db.get_session():
        stmt = select(CommandLog).order_by(CommandLog.timestamp.desc()).limit(10)
        result = await session.execute(stmt)
        logs = result.scalars().all()

        print_info(f"  - Total commands logged: {len(logs)}")

        web_commands = sum(1 for log in logs if log.source == "web")
        successful_commands = sum(1 for log in logs if log.success)

        print_info(f"  - Web commands: {web_commands}")
        print_info(f"  - Successful: {successful_commands}")

        if successful_commands == len(logs):
            print_success(f"  - All commands executed successfully")


async def test_fast_lane(db: TestDatabaseManager, orchestrator: CommandOrchestrator, artwork_id: str):
    """Test fast lane operations."""
    print_info("\nTesting fast lane operations...")

    # Get a device
    async for session in db.get_session():
        stmt = select(Device).where(Device.artwork_id == artwork_id).limit(1)
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            print_error("No device found for fast lane test")
            return

        print_info(f"Testing with device: {device.name}")

        # Fast ON
        print_info("Test: Fast lane ON...")
        result = await orchestrator.execute_control_command(
            target_type="device",
            target_id=str(device.id),
            command="on",
            source="fast"
        )

        if result.get("success"):
            print_success("Fast lane ON successful")
        else:
            print_error("Fast lane ON failed")

        # Fast OFF
        print_info("Test: Fast lane OFF...")
        result = await orchestrator.execute_control_command(
            target_type="device",
            target_id=str(device.id),
            command="off",
            source="fast"
        )

        if result.get("success"):
            print_success("Fast lane OFF successful")
        else:
            print_error("Fast lane OFF failed")


async def main():
    """Main test function."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}MuTech Control System - Standalone Test{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    # Initialize database
    print_info("Initializing in-memory database...")
    db = TestDatabaseManager()
    await db.initialize()
    print_success("Database initialized")

    # Create mock device managers
    print_info("\nInitializing mock device managers...")
    device_managers = {
        "pjlink": MockDeviceManager({"cooldown_seconds": 0.5}, "pjlink"),
        "netio": MockDeviceManager({"cooldown_seconds": 0.5}, "netio"),
        "anel": MockDeviceManager({"cooldown_seconds": 0.5}, "anel"),
        "shell": MockDeviceManager({"cooldown_seconds": 0.5}, "shell"),
    }
    print_success("Device managers initialized")

    # Create orchestrator
    print_info("\nInitializing command orchestrator...")
    config = {
        "orchestrator": {
            "on_stagger_delay_seconds": 1.0,
            "max_concurrent_on_commands": 10,
            "max_concurrent_off_commands": 50,
            "enable_off_verification": False  # Disable for mock test
        },
        "device_types": {
            "pjlink": {"cooldown_seconds": 0.5, "off_verify": None},
            "netio": {"cooldown_seconds": 0.5, "off_verify": None},
            "anel": {"cooldown_seconds": 0.5, "off_verify": None},
            "shell": {"cooldown_seconds": 0.5, "off_verify": None},
        }
    }
    orchestrator = CommandOrchestrator(db, device_managers, config)
    print_success("Orchestrator initialized")

    # Create test data
    exhibition_id, artwork_id, device_ids = await create_test_data(db)

    # Run tests
    await test_control_operations(db, orchestrator, exhibition_id, artwork_id)
    await test_fast_lane(db, orchestrator, artwork_id)

    # Final statistics
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test Summary{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    async for session in db.get_session():
        # Count entities
        exhibitions_count = len((await session.execute(select(Exhibition))).scalars().all())
        artworks_count = len((await session.execute(select(Artwork))).scalars().all())
        devices_count = len((await session.execute(select(Device))).scalars().all())
        commands_count = len((await session.execute(select(CommandLog))).scalars().all())

        print_info(f"Exhibitions created: {exhibitions_count}")
        print_info(f"Artworks created: {artworks_count}")
        print_info(f"Devices created: {devices_count}")
        print_info(f"Commands executed: {commands_count}")

        # Success rate
        successful = len((await session.execute(
            select(CommandLog).where(CommandLog.success == True)
        )).scalars().all())

        success_rate = (successful / commands_count * 100) if commands_count > 0 else 0
        print_info(f"Success rate: {success_rate:.1f}%")

        if success_rate == 100:
            print_success("\nAll tests passed! ✓")
        else:
            print_warning(f"\nSome tests had issues ({success_rate:.1f}% success)")

    # Cleanup
    await db.close()

    print(f"\n{Colors.GREEN}Testing complete!{Colors.RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Test failed with error: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
