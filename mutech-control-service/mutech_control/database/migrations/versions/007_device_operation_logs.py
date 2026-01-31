# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add device_operation_logs table for debug data with raw responses

Revision ID: 007
Revises: 006
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Determine database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    # Use appropriate UUID type
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)

    # Create device_operation_logs table
    op.create_table(
        'device_operation_logs',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('device_id', uuid_type, nullable=False),
        sa.Column('operation_type', sa.String(20), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('state_before', sa.Integer(), nullable=True),
        sa.Column('state_after', sa.Integer(), nullable=True),
        sa.Column('raw_request', sa.Text(), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    )

    # Create indexes for efficient querying
    op.create_index('idx_device_op_log_device', 'device_operation_logs', ['device_id'])
    op.create_index('idx_device_op_log_timestamp', 'device_operation_logs', ['timestamp'])
    op.create_index('idx_device_op_log_success', 'device_operation_logs', ['success'])
    op.create_index('idx_device_op_log_type', 'device_operation_logs', ['operation_type'])


def downgrade() -> None:
    op.drop_table('device_operation_logs')
