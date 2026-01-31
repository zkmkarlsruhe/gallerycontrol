# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add schedules_enabled flag to devices.

Revision ID: 018
Revises: 017
Create Date: 2026-01-25

Adds devices.schedules_enabled to control whether calendar/schedule button appears.
"""

from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "schedules_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Enable schedules feature for this device",
        ),
    )

    # Data migration: Enable schedules for devices that have scheduled jobs
    op.execute("""
        UPDATE devices
        SET schedules_enabled = true
        WHERE id IN (
            SELECT DISTINCT target_device_id
            FROM scheduled_jobs
            WHERE target_device_id IS NOT NULL
        )
    """)


def downgrade() -> None:
    op.drop_column("devices", "schedules_enabled")
