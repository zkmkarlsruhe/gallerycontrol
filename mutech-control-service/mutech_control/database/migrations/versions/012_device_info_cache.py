"""Add cached_info and cached_info_at columns to devices table.

Revision ID: 012
Revises: 011
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add device info cache columns to devices table."""
    op.add_column(
        "devices",
        sa.Column("cached_info", JSON, nullable=True),
    )
    op.add_column(
        "devices",
        sa.Column("cached_info_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Remove device info cache columns."""
    op.drop_column("devices", "cached_info_at")
    op.drop_column("devices", "cached_info")
