# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Determine database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    # Use appropriate UUID and JSON types
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)
    json_type = postgresql.JSONB() if is_postgresql else sa.JSON()

    # Create exhibitions table
    op.create_table(
        'exhibitions',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create artworks table
    op.create_table(
        'artworks',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('exhibition_id', uuid_type, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['exhibition_id'], ['exhibitions.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_artworks_exhibition', 'artworks', ['exhibition_id'])

    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('artwork_id', uuid_type, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('device_type', sa.String(50), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('automation_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('exclude_from_auto_onoff', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('config', json_type, nullable=False, server_default='{}'),
        sa.Column('state', sa.Integer(), nullable=False, server_default='-1'),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('next_check_allowed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['artwork_id'], ['artworks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('host', 'port', 'device_type', name='unique_device'),
    )
    op.create_index('idx_devices_artwork', 'devices', ['artwork_id'])
    op.create_index('idx_devices_enabled', 'devices', ['enabled'])
    op.create_index('idx_devices_type', 'devices', ['device_type'])

    # Create command_log table
    op.create_table(
        'command_log',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('device_id', uuid_type, nullable=True),
        sa.Column('command', sa.String(50), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_command_log_device', 'command_log', ['device_id'])
    op.create_index('idx_command_log_timestamp', 'command_log', ['timestamp'])


def downgrade() -> None:
    op.drop_table('command_log')
    op.drop_table('devices')
    op.drop_table('artworks')
    op.drop_table('exhibitions')
