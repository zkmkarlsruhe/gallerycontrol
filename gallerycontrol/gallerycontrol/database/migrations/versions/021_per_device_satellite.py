# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Move satellite routing from exhibition-level to per-device.

Revision ID: 021
Revises: 020
Create Date: 2026-05-26

Replaces the two-level model (Exhibition.satellite_id + Device.use_satellite)
with a single Device.satellite_id field. Devices can now route via any satellite
independent of their exhibition.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "satellite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("satellites.id", ondelete="SET NULL"),
            nullable=True,
            comment="Satellite relay for this device, NULL = direct connection",
        ),
    )
    op.create_index("idx_devices_satellite", "devices", ["satellite_id"])

    op.drop_column("devices", "use_satellite")

    op.drop_index("idx_exhibitions_satellite", table_name="exhibitions")
    op.drop_column("exhibitions", "satellite_id")


def downgrade() -> None:
    op.add_column(
        "exhibitions",
        sa.Column(
            "satellite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("satellites.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_exhibitions_satellite", "exhibitions", ["satellite_id"])

    op.add_column(
        "devices",
        sa.Column(
            "use_satellite",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )

    op.drop_index("idx_devices_satellite", table_name="devices")
    op.drop_column("devices", "satellite_id")
