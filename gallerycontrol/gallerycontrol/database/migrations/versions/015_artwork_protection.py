# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add artwork protection feature.

Revision ID: 015
Revises: 014
Create Date: 2026-01-24

Adds protection rules to prevent artwork overuse:
- protection_config column on artworks table (JSON config)
- artwork_protection_states table for runtime state tracking

Protection supports:
- Time slice windows (budget per time period)
- Max runtime with cooldown periods
- Force completion mode
- Minimum budget to start
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add protection_config column to artworks
    op.add_column(
        "artworks",
        sa.Column(
            "protection_config",
            sa.JSON,
            nullable=True,
            comment="Protection rules for overuse prevention",
        ),
    )

    # Create artwork_protection_states table
    op.create_table(
        "artwork_protection_states",
        sa.Column(
            "artwork_id",
            UUID(as_uuid=True),
            sa.ForeignKey("artworks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "is_running",
            sa.Boolean,
            default=False,
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime,
            nullable=True,
            comment="When current run started",
        ),
        sa.Column(
            "cooldown_until",
            sa.DateTime,
            nullable=True,
            comment="Active cooldown period end",
        ),
        sa.Column(
            "time_slice_usage",
            sa.JSON,
            default=dict,
            nullable=False,
            comment="Usage per time window in seconds: {window_minutes: seconds_used}",
        ),
        sa.Column(
            "last_window_reset",
            sa.JSON,
            default=dict,
            nullable=False,
            comment="Last reset timestamp per window: {window_minutes: iso_timestamp}",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("artwork_protection_states")
    op.drop_column("artworks", "protection_config")
