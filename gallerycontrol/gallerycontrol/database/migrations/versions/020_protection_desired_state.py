# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add desired_state to artwork protection states.

Revision ID: 020
Revises: 019
Create Date: 2026-01-29

Adds desired_state column for sensor integration:
- Tracks what state the sensor wants (on/off)
- Enables auto-resume after cooldown when sensor still wants "on"
"""

from alembic import op
import sqlalchemy as sa


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add desired_state column to artwork_protection_states
    op.add_column(
        "artwork_protection_states",
        sa.Column(
            "desired_state",
            sa.String(10),
            nullable=False,
            server_default="off",
            comment="Sensor's desired state: on or off",
        ),
    )


def downgrade() -> None:
    op.drop_column("artwork_protection_states", "desired_state")
