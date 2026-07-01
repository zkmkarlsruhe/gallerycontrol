# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Unit tests for CommandOrchestrator._filter_devices.

Guards the automation_enabled gating semantics:
- automation_enabled=False excludes a device from BULK (artwork/exhibition) ON/OFF
- an explicit single-device command is manual control and always goes through
- the scheduler bypasses the flag entirely
"""

from types import SimpleNamespace

import pytest

from gallerycontrol.orchestrator.command_orchestrator import CommandOrchestrator


@pytest.fixture
def orch():
    # Skip __init__ (needs a session); force effective-enabled True so the test
    # isolates the automation_enabled / target_type / source logic.
    o = object.__new__(CommandOrchestrator)
    o._is_effectively_enabled = lambda d: True
    return o


def _dev(automation_enabled):
    return SimpleNamespace(id="D", name="D", automation_enabled=automation_enabled)


@pytest.mark.parametrize(
    "target_type,source,automation_enabled,command,expected",
    [
        # The fix: explicit single-device manual control is never gated.
        ("device", "web", False, "on", True),
        ("device", "web", False, "off", True),
        ("device", "web", True, "on", True),
        # Bulk targets still exclude automation-disabled devices.
        ("artwork", "web", False, "on", False),
        ("exhibition", "web", False, "on", False),
        ("artwork", "web", True, "on", True),
        # Scheduler bypasses the flag for any target.
        ("artwork", "scheduler", False, "on", True),
        ("device", "scheduler", False, "on", True),
        # Non-scheduler bulk sources unchanged (no regression).
        ("artwork", "protection", False, "on", False),
        ("artwork", "fast", False, "on", False),
    ],
)
def test_filter_devices_automation_gating(
    orch, target_type, source, automation_enabled, command, expected
):
    device = _dev(automation_enabled)
    result = orch._filter_devices([device], command, source, target_type)
    assert (device in result) is expected
