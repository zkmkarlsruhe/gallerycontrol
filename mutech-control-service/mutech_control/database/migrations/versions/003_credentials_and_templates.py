"""Add credentials and shell_templates tables

Revision ID: 003
Revises: 002
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Determine database type
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    # Use appropriate UUID type
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(36)

    # Create credentials table
    op.create_table(
        'credentials',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create shell_templates table
    op.create_table(
        'shell_templates',
        sa.Column('id', uuid_type, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status_command', sa.Text(), nullable=True),
        sa.Column('status_on_pattern', sa.String(255), nullable=True),
        sa.Column('status_off_pattern', sa.String(255), nullable=True),
        sa.Column('on_command', sa.Text(), nullable=True),
        sa.Column('off_command', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('shell_templates')
    op.drop_table('credentials')
