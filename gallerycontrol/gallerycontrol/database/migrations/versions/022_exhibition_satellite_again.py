# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Move satellite routing back to exhibition-level (no per-device opt-in).

Revision ID: 022
Revises: 021
Create Date: 2026-05-26

The per-device satellite_id (added in 021) turned out to be UX clutter
on the device modal. All devices in an isolated network typically share
the same satellite anyway, so routing becomes a property of the exhibition.
No opt-in flag — every device in an exhibition with satellite_id routes
via that satellite automatically.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.drop_index("idx_devices_satellite", table_name="devices")
    op.drop_column("devices", "satellite_id")


def downgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "satellite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("satellites.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_devices_satellite", "devices", ["satellite_id"])

    op.drop_index("idx_exhibitions_satellite", table_name="exhibitions")
    op.drop_column("exhibitions", "satellite_id")
