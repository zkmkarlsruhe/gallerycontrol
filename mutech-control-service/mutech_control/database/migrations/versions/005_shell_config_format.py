"""Migrate shell device configs to new format

Revision ID: 005
Revises: 004
Create Date: 2026-01-14

Converts legacy array format to new structured format:
- commands.status/on/off for automation
- actions[] for manual buttons
- Replaces sshpass -f with {{PASSWORD:name}} placeholders
"""
from typing import Sequence, Union
import json
import re

from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def convert_config(old_config: dict) -> tuple[dict, bool]:
    """Convert legacy config to new format.

    Returns: (new_config, is_automatable)
    """
    old_commands = old_config.get('commands', [])

    if not isinstance(old_commands, list):
        # Already in new format or empty
        return old_config, bool(
            old_commands.get('status') and
            old_commands.get('on') and
            old_commands.get('off')
        )

    new_config = {}
    commands = {}
    actions = []

    # Map of normalized names to command types
    automation_commands = {'status', 'on', 'off'}

    for cmd in old_commands:
        name = cmd.get('name', '').lower().strip()
        cmd_str = cmd.get('cmd', '')

        # Replace sshpass -f with placeholder
        cmd_str = re.sub(
            r'sshpass\s+-f\s+/root/\.ssh/museumstechnik\.txt\s+ssh\s+museumstechnik@',
            'sshpass -p {{PASSWORD:museumstechnik}} ssh {{USER:museumstechnik}}@',
            cmd_str
        )

        if name in automation_commands:
            # This is an automation command
            cmd_obj = {'cmd': cmd_str}
            if name == 'status':
                # Add patterns
                if cmd.get('onMsg'):
                    cmd_obj['onPattern'] = cmd['onMsg']
                if cmd.get('offMsg'):
                    cmd_obj['offPattern'] = cmd['offMsg']
            commands[name] = cmd_obj
        elif name and name != 'reachable':
            # This is an action (skip 'reachable' as it's redundant with status)
            actions.append({
                'name': cmd.get('name', name),  # Preserve original case
                'cmd': cmd_str
            })

    if commands:
        new_config['commands'] = commands
    if actions:
        new_config['actions'] = actions

    # Check if automatable (has all three: status, on, off)
    is_automatable = all(k in commands for k in ['status', 'on', 'off'])

    return new_config, is_automatable


def upgrade() -> None:
    conn = op.get_bind()

    # Get all shell devices
    result = conn.execute(sa.text(
        "SELECT id, config, automation_enabled FROM devices WHERE device_type = 'shell'"
    ))

    for row in result:
        device_id, old_config, current_automation = row

        new_config, is_automatable = convert_config(old_config or {})

        # If not automatable, force automation_enabled to false
        new_automation = current_automation if is_automatable else False

        conn.execute(
            sa.text("UPDATE devices SET config = :config, automation_enabled = :automation WHERE id = :id"),
            {'config': json.dumps(new_config), 'automation': new_automation, 'id': device_id}
        )


def downgrade() -> None:
    # No downgrade - this is a one-way migration
    pass
