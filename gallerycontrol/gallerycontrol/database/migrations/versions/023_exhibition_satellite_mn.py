# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Many-to-many satellites per exhibition; devices pick from their exhibition's set.

Revision ID: 023
Revises: 022
Create Date: 2026-05-26

The single-satellite-per-exhibition model (022) doesn't cover exhibitions
that span multiple network segments. Replaces with:
- exhibition_satellites: M:N join (which satellites are usable by an exhibition)
- devices.satellite_id: per-device choice, constrained to its exhibition's set

The application enforces the "pick from this exhibition's set" rule; the
schema only enforces FK integrity to the satellites table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exhibition_satellites",
        sa.Column(
            "exhibition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exhibitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "satellite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("satellites.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

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

    # Carry forward the single satellite previously assigned to each exhibition
    # as a member of the new M:N set, so existing assignments are not lost.
    op.execute(
        """
        INSERT INTO exhibition_satellites (exhibition_id, satellite_id)
        SELECT id, satellite_id FROM exhibitions WHERE satellite_id IS NOT NULL
        """
    )

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

    # Restore exhibitions.satellite_id from the first member of the M:N set
    op.execute(
        """
        UPDATE exhibitions SET satellite_id = subq.satellite_id
        FROM (
            SELECT DISTINCT ON (exhibition_id) exhibition_id, satellite_id
            FROM exhibition_satellites
        ) subq
        WHERE exhibitions.id = subq.exhibition_id
        """
    )

    op.drop_index("idx_devices_satellite", table_name="devices")
    op.drop_column("devices", "satellite_id")

    op.drop_table("exhibition_satellites")
