"""Add actions and onoff_mode columns to shell_templates

Allows templates to store custom actions and track which mode
(ON/OFF commands vs custom actions) the template uses.

Revision ID: 009
Revises: 008
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add actions column (JSON array of {name, cmd} objects)
    op.add_column('shell_templates', sa.Column('actions', sa.JSON(), nullable=True))

    # Add onoff_mode column (True=ON/OFF mode, False=Actions mode)
    op.add_column('shell_templates', sa.Column('onoff_mode', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('shell_templates', 'onoff_mode')
    op.drop_column('shell_templates', 'actions')
