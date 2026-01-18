"""Remove exclude_from_auto_onoff column from devices table

This column is redundant with automation_enabled - devices with
automation_enabled=false are already excluded from bulk operations.

Revision ID: 006
Revises: 005
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove the redundant column
    op.drop_column('devices', 'exclude_from_auto_onoff')


def downgrade() -> None:
    # Re-add the column if rolling back
    op.add_column(
        'devices',
        sa.Column('exclude_from_auto_onoff', sa.Boolean(), nullable=False, server_default='false')
    )
