"""Add hostname_manual flag to assets table.

Revision ID: 011
Revises: 010
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add hostname_manual column to assets table."""
    op.add_column(
        "assets",
        sa.Column("hostname_manual", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove hostname_manual column."""
    op.drop_column("assets", "hostname_manual")
