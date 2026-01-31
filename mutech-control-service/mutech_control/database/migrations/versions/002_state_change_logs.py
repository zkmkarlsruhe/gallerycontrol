# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add state_change_logs table

Revision ID: 002
Revises: 001
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Determine database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    # Use appropriate UUID type
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)

    # Create state_change_logs table
    op.create_table(
        'state_change_logs',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('device_id', uuid_type, nullable=False),
        sa.Column('previous_state', sa.Integer(), nullable=False),
        sa.Column('new_state', sa.Integer(), nullable=False),
        sa.Column('trigger', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_state_change_device', 'state_change_logs', ['device_id'])
    op.create_index('idx_state_change_timestamp', 'state_change_logs', ['timestamp'])
    op.create_index('idx_state_change_new_state', 'state_change_logs', ['new_state'])


def downgrade() -> None:
    op.drop_table('state_change_logs')
