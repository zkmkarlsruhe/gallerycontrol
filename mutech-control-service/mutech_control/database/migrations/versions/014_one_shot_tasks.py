"""Add one-shot task support to scheduled_jobs.

Revision ID: 014
Revises: 013
Create Date: 2026-01-22

Enables one-shot scheduled tasks for:
- Delayed lamp hours recording (replace fire-and-forget asyncio tasks)
- Scheduled power on/off for artworks and exhibitions
- Any future one-time scheduled operations

Key changes:
- cron_expression becomes nullable (one-shots don't need it)
- run_once flag to distinguish one-shot from recurring jobs
- target_type for device/artwork/exhibition targeting
- target_id for generic UUID targeting (artwork/exhibition)
- executed_at for tracking one-shot completion (for cleanup)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make cron_expression optional for one-shot jobs
    op.alter_column(
        "scheduled_jobs",
        "cron_expression",
        existing_type=sa.String(100),
        nullable=True,
    )

    # Add one-shot support flag
    op.add_column(
        "scheduled_jobs",
        sa.Column(
            "run_once",
            sa.Boolean,
            server_default=sa.false(),
            nullable=False,
            comment="True for one-shot tasks, False for recurring cron jobs",
        ),
    )

    # Add target flexibility for artwork/exhibition scheduling
    op.add_column(
        "scheduled_jobs",
        sa.Column(
            "target_type",
            sa.String(20),
            server_default="device",
            nullable=False,
            comment="device, artwork, or exhibition",
        ),
    )

    op.add_column(
        "scheduled_jobs",
        sa.Column(
            "target_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Generic target UUID for artwork/exhibition (no FK)",
        ),
    )

    # Track execution for one-shot cleanup
    op.add_column(
        "scheduled_jobs",
        sa.Column(
            "executed_at",
            sa.DateTime,
            nullable=True,
            comment="When one-shot was executed (for cleanup)",
        ),
    )

    # Index for finding pending one-shot jobs
    op.create_index(
        "idx_scheduled_jobs_one_shot_pending",
        "scheduled_jobs",
        ["run_once", "executed_at"],
        postgresql_where=sa.text("run_once = true AND executed_at IS NULL"),
    )

    # Index for cleanup of executed one-shots
    op.create_index(
        "idx_scheduled_jobs_one_shot_executed",
        "scheduled_jobs",
        ["run_once", "executed_at"],
        postgresql_where=sa.text("run_once = true AND executed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_scheduled_jobs_one_shot_executed")
    op.drop_index("idx_scheduled_jobs_one_shot_pending")
    op.drop_column("scheduled_jobs", "executed_at")
    op.drop_column("scheduled_jobs", "target_id")
    op.drop_column("scheduled_jobs", "target_type")
    op.drop_column("scheduled_jobs", "run_once")

    # Restore NOT NULL constraint on cron_expression
    # Note: This may fail if there are one-shot jobs with NULL cron_expression
    op.alter_column(
        "scheduled_jobs",
        "cron_expression",
        existing_type=sa.String(100),
        nullable=False,
    )
