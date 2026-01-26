"""Add feature enabled flags for time slices and schedules.

Revision ID: 017
Revises: 016
Create Date: 2026-01-25

Adds explicit enable/disable toggles:
- artworks.timeslice_enabled: Enable time slice protection feature
- artworks.schedules_enabled: Enable schedules feature for artwork
- exhibitions.schedules_enabled: Enable schedules feature for exhibition

When disabled, config/schedules are preserved but feature is inactive.
"""

from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add timeslice_enabled to artworks
    op.add_column(
        "artworks",
        sa.Column(
            "timeslice_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Enable time slice protection feature",
        ),
    )

    # Add schedules_enabled to artworks
    op.add_column(
        "artworks",
        sa.Column(
            "schedules_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Enable schedules feature for this artwork",
        ),
    )

    # Add schedules_enabled to exhibitions
    op.add_column(
        "exhibitions",
        sa.Column(
            "schedules_enabled",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Enable schedules feature for this exhibition",
        ),
    )

    # Data migration: Enable timeslice for artworks that have protection_config
    op.execute("""
        UPDATE artworks
        SET timeslice_enabled = true
        WHERE protection_config IS NOT NULL
    """)

    # Data migration: Enable schedules for artworks that have scheduled jobs
    op.execute("""
        UPDATE artworks
        SET schedules_enabled = true
        WHERE id IN (
            SELECT DISTINCT target_id::uuid
            FROM scheduled_jobs
            WHERE target_type = 'artwork'
        )
    """)

    # Data migration: Enable schedules for exhibitions that have scheduled jobs
    op.execute("""
        UPDATE exhibitions
        SET schedules_enabled = true
        WHERE id IN (
            SELECT DISTINCT target_id::uuid
            FROM scheduled_jobs
            WHERE target_type = 'exhibition'
        )
    """)


def downgrade() -> None:
    op.drop_column("artworks", "timeslice_enabled")
    op.drop_column("artworks", "schedules_enabled")
    op.drop_column("exhibitions", "schedules_enabled")
