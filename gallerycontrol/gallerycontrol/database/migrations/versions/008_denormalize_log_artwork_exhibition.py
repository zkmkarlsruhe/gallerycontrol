# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Add artwork_id and exhibition_id to log tables for historical accuracy

Denormalizes artwork/exhibition into log tables so timeline filtering
works correctly even when devices are reassigned between exhibitions.

Revision ID: 008
Revises: 007
Create Date: 2026-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Determine database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    # Use appropriate UUID type
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)

    # Add columns to state_change_logs
    op.add_column('state_change_logs', sa.Column('artwork_id', uuid_type, nullable=True))
    op.add_column('state_change_logs', sa.Column('exhibition_id', uuid_type, nullable=True))
    op.create_index('idx_state_change_exhibition', 'state_change_logs', ['exhibition_id'])

    # Add columns to device_operation_logs
    op.add_column('device_operation_logs', sa.Column('artwork_id', uuid_type, nullable=True))
    op.add_column('device_operation_logs', sa.Column('exhibition_id', uuid_type, nullable=True))
    op.create_index('idx_device_op_log_exhibition', 'device_operation_logs', ['exhibition_id'])

    # Backfill existing records with current device artwork/exhibition
    # This is best-effort since we can't know historical assignments
    if is_postgresql:
        op.execute("""
            UPDATE state_change_logs scl
            SET artwork_id = d.artwork_id,
                exhibition_id = a.exhibition_id
            FROM devices d
            JOIN artworks a ON d.artwork_id = a.id
            WHERE scl.device_id = d.id
            AND scl.artwork_id IS NULL
        """)
        op.execute("""
            UPDATE device_operation_logs dol
            SET artwork_id = d.artwork_id,
                exhibition_id = a.exhibition_id
            FROM devices d
            JOIN artworks a ON d.artwork_id = a.id
            WHERE dol.device_id = d.id
            AND dol.artwork_id IS NULL
        """)


def downgrade() -> None:
    op.drop_index('idx_device_op_log_exhibition', 'device_operation_logs')
    op.drop_column('device_operation_logs', 'exhibition_id')
    op.drop_column('device_operation_logs', 'artwork_id')

    op.drop_index('idx_state_change_exhibition', 'state_change_logs')
    op.drop_column('state_change_logs', 'exhibition_id')
    op.drop_column('state_change_logs', 'artwork_id')
