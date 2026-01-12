#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

Migrates data from the old Node.js/SQLite system to the new Python/PostgreSQL system.

Usage:
    python migrate_sqlite_to_postgres.py <sqlite_db_path>

Example:
    python migrate_sqlite_to_postgres.py /path/to/old/mutech.db
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import asyncpg


async def migrate(sqlite_db_path: str, postgres_url: str):
    """Main migration function."""
    print(f"Starting migration from {sqlite_db_path}")
    print(f"Target PostgreSQL: {postgres_url}")

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(postgres_url)

    try:
        # Migration steps
        await migrate_exhibitions(cursor, pg_conn)
        await migrate_works(cursor, pg_conn)
        await migrate_units(cursor, pg_conn)

        print("\n✅ Migration completed successfully!")

    finally:
        sqlite_conn.close()
        await pg_conn.close()


async def migrate_exhibitions(cursor: sqlite3.Cursor, pg_conn):
    """Migrate exhibitions table."""
    print("\n📦 Migrating exhibitions...")

    cursor.execute("SELECT * FROM exhibits")
    exhibits = cursor.fetchall()

    # Create mapping of old IDs to new UUIDs
    id_map = {}

    for exhibit in exhibits:
        new_id = uuid4()
        id_map[exhibit["id"]] = str(new_id)

        await pg_conn.execute(
            """
            INSERT INTO exhibitions (id, name, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            new_id,
            exhibit["name"],
            True,  # Default enabled
            datetime.fromisoformat(exhibit["created_at"])
            if exhibit.get("created_at")
            else datetime.utcnow(),
            datetime.utcnow(),
        )

    print(f"   Migrated {len(exhibits)} exhibitions")
    return id_map


async def migrate_works(cursor: sqlite3.Cursor, pg_conn):
    """Migrate works (artworks) table."""
    print("\n🎨 Migrating artworks...")

    cursor.execute("SELECT * FROM works")
    works = cursor.fetchall()

    # Get exhibition ID mapping
    cursor.execute("SELECT id FROM exhibits")
    exhibits = {row["id"]: uuid4() for row in cursor.fetchall()}

    # Re-query for works with correct mapping
    cursor.execute("SELECT * FROM works")
    works = cursor.fetchall()

    id_map = {}

    for work in works:
        new_id = uuid4()
        id_map[work["id"]] = str(new_id)

        # Map old parent_id to new exhibition UUID
        old_parent_id = work["parent_id"]
        # Get the new UUID for this exhibition
        cursor.execute("SELECT id FROM exhibits WHERE id = ?", (old_parent_id,))
        exhibit_row = cursor.fetchone()

        if not exhibit_row:
            print(f"   ⚠️ Warning: No exhibition found for work {work['name']}")
            continue

        # Get new exhibition UUID
        cursor.execute(
            "SELECT name FROM exhibits WHERE id = ?", (old_parent_id,)
        )
        exhibit = cursor.fetchone()
        exhibition_name = exhibit["name"] if exhibit else ""

        # Find the new UUID by name (since we need to match)
        new_exhibition_id = await pg_conn.fetchval(
            "SELECT id FROM exhibitions WHERE name = $1", exhibition_name
        )

        if not new_exhibition_id:
            print(f"   ⚠️ Warning: Could not map exhibition for work {work['name']}")
            continue

        await pg_conn.execute(
            """
            INSERT INTO artworks (id, exhibition_id, name, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            new_id,
            new_exhibition_id,
            work["name"],
            True,
            datetime.fromisoformat(work["created_at"])
            if work.get("created_at")
            else datetime.utcnow(),
            datetime.utcnow(),
        )

    print(f"   Migrated {len(works)} artworks")
    return id_map


async def migrate_units(cursor: sqlite3.Cursor, pg_conn):
    """Migrate units (devices) table."""
    print("\n🔌 Migrating devices...")

    cursor.execute("SELECT * FROM units")
    units = cursor.fetchall()

    migrated = 0
    skipped = 0

    for unit in units:
        new_id = uuid4()

        # Get parent work and find new artwork UUID
        old_parent_id = unit["parent_id"]
        cursor.execute("SELECT name FROM works WHERE id = ?", (old_parent_id,))
        work = cursor.fetchone()

        if not work:
            print(f"   ⚠️ Warning: No artwork found for device {unit.get('host')}")
            skipped += 1
            continue

        work_name = work["name"]
        new_artwork_id = await pg_conn.fetchval(
            "SELECT id FROM artworks WHERE name = $1", work_name
        )

        if not new_artwork_id:
            print(f"   ⚠️ Warning: Could not map artwork for device {unit.get('host')}")
            skipped += 1
            continue

        # Parse args JSON if present
        args = {}
        if unit.get("args"):
            try:
                args = json.loads(unit["args"])
            except json.JSONDecodeError:
                args = {}

        # Determine if device should be excluded from auto on/off
        # Shell devices with reboot/restart commands should be excluded
        exclude_from_auto = False
        if unit["unit_type"] == "shell":
            commands = args.get("commands", [])
            for cmd in commands:
                if cmd.get("name", "").lower() in ["reboot", "restart"]:
                    exclude_from_auto = True
                    break

        # Map unit_type to device_type
        device_type_map = {
            "projector": "pjlink",
            "netio": "netio",
            "anel": "anel",
            "shell": "shell",
            "udp": "netio",  # Old UDP units mapped to netio
        }
        device_type = device_type_map.get(unit["unit_type"], unit["unit_type"])

        try:
            await pg_conn.execute(
                """
                INSERT INTO devices (
                    id, artwork_id, name, device_type, host, port,
                    enabled, automation_enabled, exclude_from_auto_onoff,
                    config, state, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                new_id,
                new_artwork_id,
                unit.get("host", "unknown"),  # Use host as name if no name
                device_type,
                unit["host"],
                unit.get("port"),
                unit.get("active", True),
                unit.get("automation", True),
                exclude_from_auto,
                json.dumps(args),
                unit.get("state", -1),
                datetime.fromisoformat(unit["created_at"])
                if unit.get("created_at")
                else datetime.utcnow(),
                datetime.utcnow(),
            )
            migrated += 1

        except Exception as e:
            print(f"   ⚠️ Error migrating device {unit.get('host')}: {e}")
            skipped += 1

    print(f"   Migrated {migrated} devices ({skipped} skipped)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_sqlite_to_postgres.py <sqlite_db_path>")
        print("Example: python migrate_sqlite_to_postgres.py /path/to/mutech.db")
        sys.exit(1)

    sqlite_path = sys.argv[1]

    if not Path(sqlite_path).exists():
        print(f"Error: SQLite database not found: {sqlite_path}")
        sys.exit(1)

    # PostgreSQL URL from environment or default
    import os

    postgres_url = os.getenv(
        "DATABASE_URL", "postgresql://mutech:mutech_password@localhost:5432/mutech"
    )

    # Remove asyncpg:// prefix if present and replace with postgresql://
    if postgres_url.startswith("postgresql+asyncpg://"):
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "postgresql://")

    asyncio.run(migrate(sqlite_path, postgres_url))
