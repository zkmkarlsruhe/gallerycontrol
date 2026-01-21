"""Add asset tracking tables and device columns

Adds:
- assets table: Projector assets for tracking lamp hours across onboard/offboard cycles
- lamp_hours_logs table: Lamp hours history log
- Device columns: resolved, resolved_at, asset_id

Revision ID: 010
Revises: 009
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create assets table first (no FK deps)
    op.create_table(
        'assets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_number', sa.String(50), unique=True, nullable=False),
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # 2. Create lamp_hours_logs table
    op.create_table(
        'lamp_hours_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', UUID(as_uuid=True), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_id', UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('lamp_hours', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False),
        sa.Column('exhibition_name', sa.String(255), nullable=True),
        sa.Column('artwork_name', sa.String(255), nullable=True),
        sa.Column('device_name', sa.String(255), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )

    # 3. Add columns to devices (nullable)
    op.add_column('devices', sa.Column('resolved', sa.String(255), nullable=True))
    op.add_column('devices', sa.Column('resolved_at', sa.DateTime(), nullable=True))
    op.add_column('devices', sa.Column('asset_id', UUID(as_uuid=True), nullable=True))

    # 4. Create foreign key for asset_id
    op.create_foreign_key(
        'fk_devices_asset_id',
        'devices', 'assets',
        ['asset_id'], ['id'],
        ondelete='SET NULL'
    )

    # 5. Create indexes
    op.create_index('idx_devices_asset', 'devices', ['asset_id'])
    op.create_index('idx_lamp_hours_asset', 'lamp_hours_logs', ['asset_id'])
    op.create_index('idx_lamp_hours_timestamp', 'lamp_hours_logs', ['timestamp'])
    op.create_index('idx_lamp_hours_event', 'lamp_hours_logs', ['event_type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_lamp_hours_event', 'lamp_hours_logs')
    op.drop_index('idx_lamp_hours_timestamp', 'lamp_hours_logs')
    op.drop_index('idx_lamp_hours_asset', 'lamp_hours_logs')
    op.drop_index('idx_devices_asset', 'devices')

    # Drop foreign key
    op.drop_constraint('fk_devices_asset_id', 'devices', type_='foreignkey')

    # Drop columns from devices
    op.drop_column('devices', 'asset_id')
    op.drop_column('devices', 'resolved_at')
    op.drop_column('devices', 'resolved')

    # Drop tables
    op.drop_table('lamp_hours_logs')
    op.drop_table('assets')
