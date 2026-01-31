# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add accepting_triggers field to artworks.

Revision ID: 016
Revises: 015
Create Date: 2026-01-25

Adds gate for fast-lane API triggers:
- accepting_triggers: boolean field on artworks table
- When true, artwork accepts external API triggers (fast-lane)
- When false, fast-lane triggers return error
- Set by web/cron ON/OFF at artwork/exhibition level
- Device-level ON/OFF does not change this (maintenance mode)
"""

from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artworks",
        sa.Column(
            "accepting_triggers",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Gate for fast-lane API triggers",
        ),
    )


def downgrade() -> None:
    op.drop_column("artworks", "accepting_triggers")
