"""Add scheduled_jobs table for unified cron scheduling.

Revision ID: 013
Revises: 012
Create Date: 2026-01-22

Unified scheduler for both system maintenance tasks and device automation.
Replaces the old interval-based TaskScheduler with cron expressions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "job_type",
            sa.String(20),
            nullable=False,
            comment="system or device",
        ),
        sa.Column(
            "cron_expression",
            sa.String(100),
            nullable=False,
            comment="Standard cron: minute hour day month weekday",
        ),
        # Device job fields
        sa.Column(
            "target_device_id",
            UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "action_type",
            sa.String(20),
            nullable=True,
            comment="on, off, or action",
        ),
        sa.Column(
            "action_name",
            sa.String(100),
            nullable=True,
            comment="For shell device actions",
        ),
        # System job fields
        sa.Column(
            "task_name",
            sa.String(50),
            nullable=True,
            comment="asset_linker, log_cleanup, device_info_cache, lamp_hours_check",
        ),
        sa.Column(
            "task_config",
            JSONB,
            nullable=True,
            comment="Task-specific configuration",
        ),
        # State
        sa.Column("enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("last_run_at", sa.DateTime, nullable=True),
        sa.Column("last_success", sa.Boolean, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("last_duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "next_run_at",
            sa.DateTime,
            nullable=True,
            comment="Pre-computed for efficient querying",
        ),
        # Resiliency
        sa.Column(
            "fail_count",
            sa.Integer,
            default=0,
            nullable=False,
            comment="Consecutive failures for circuit breaker",
        ),
        sa.Column(
            "backoff_until",
            sa.DateTime,
            nullable=True,
            comment="Skip execution until this time (exponential backoff)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Indexes for efficient queries
    op.create_index(
        "idx_scheduled_jobs_enabled_next_run",
        "scheduled_jobs",
        ["enabled", "next_run_at"],
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_index(
        "idx_scheduled_jobs_job_type",
        "scheduled_jobs",
        ["job_type"],
    )
    op.create_index(
        "idx_scheduled_jobs_device",
        "scheduled_jobs",
        ["target_device_id"],
        postgresql_where=sa.text("target_device_id IS NOT NULL"),
    )
    op.create_index(
        "idx_scheduled_jobs_task_name",
        "scheduled_jobs",
        ["task_name"],
        postgresql_where=sa.text("task_name IS NOT NULL"),
    )

    # Execution log table for history
    op.create_table(
        "scheduled_job_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime, nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "result",
            JSONB,
            nullable=True,
            comment="Task result data for system jobs",
        ),
    )

    op.create_index(
        "idx_scheduled_job_logs_job_executed",
        "scheduled_job_logs",
        ["job_id", "executed_at"],
    )


def downgrade() -> None:
    op.drop_table("scheduled_job_logs")
    op.drop_table("scheduled_jobs")
