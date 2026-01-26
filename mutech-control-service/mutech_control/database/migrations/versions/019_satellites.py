"""Add satellites table and satellite routing fields.

Revision ID: 019
Revises: 018
Create Date: 2026-01-26

Adds satellite support for relaying commands to devices in NATed/closed networks.
- satellites table: stores registered satellite relays
- exhibitions.satellite_id: assigns a satellite to an exhibition
- devices.use_satellite: enables satellite routing for specific devices
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create satellites table
    op.create_table(
        "satellites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True),  # SHA-256
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending/approved/offline",
        ),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Add index on api_key_hash for fast lookups
    op.create_index("idx_satellites_api_key_hash", "satellites", ["api_key_hash"])

    # Add index on status for filtering
    op.create_index("idx_satellites_status", "satellites", ["status"])

    # Add satellite_id to exhibitions
    op.add_column(
        "exhibitions",
        sa.Column(
            "satellite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("satellites.id", ondelete="SET NULL"),
            nullable=True,
            comment="Assigned satellite relay for this exhibition",
        ),
    )

    # Add index on satellite_id for efficient lookups
    op.create_index("idx_exhibitions_satellite", "exhibitions", ["satellite_id"])

    # Add use_satellite to devices
    op.add_column(
        "devices",
        sa.Column(
            "use_satellite",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Route commands through exhibition satellite",
        ),
    )


def downgrade() -> None:
    # Drop device column
    op.drop_column("devices", "use_satellite")

    # Drop exhibition column and index
    op.drop_index("idx_exhibitions_satellite", table_name="exhibitions")
    op.drop_column("exhibitions", "satellite_id")

    # Drop satellites table and indexes
    op.drop_index("idx_satellites_status", table_name="satellites")
    op.drop_index("idx_satellites_api_key_hash", table_name="satellites")
    op.drop_table("satellites")
