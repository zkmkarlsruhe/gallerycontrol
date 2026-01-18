"""Add credential_type column to credentials table

Revision ID: 004
Revises: 003
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add credential_type column with default value 'shell'
    op.add_column(
        'credentials',
        sa.Column('credential_type', sa.String(20), nullable=False, server_default='shell')
    )

    # Create index for filtering by type
    op.create_index('idx_credentials_type', 'credentials', ['credential_type'])


def downgrade() -> None:
    op.drop_index('idx_credentials_type', table_name='credentials')
    op.drop_column('credentials', 'credential_type')
