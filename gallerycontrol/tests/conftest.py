# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Pytest configuration and fixtures."""

import pytest
from uuid import uuid4

from tests.mocks import MockPJLinkDevice, MockNETIODevice, MockANELDevice, MockShellDevice


@pytest.fixture
def mock_pjlink_device():
    """Mock PJLink projector responding on TCP."""
    device = MockPJLinkDevice(
        host="192.168.1.100",
        port=4352,
        password="panasonic",
        initial_state=0,  # off
    )
    return device


@pytest.fixture
def mock_netio_device():
    """Mock NETIO power strip with HTTP API."""
    device = MockNETIODevice(
        host="192.168.1.101",
        username="netio",
        password="netio",
        port_count=4,
    )
    return device


@pytest.fixture
def mock_anel_device():
    """Mock ANEL power strip with UDP protocol."""
    device = MockANELDevice(
        host="192.168.1.102",
        username="admin",
        password="anel",
        port_count=8,
    )
    return device


@pytest.fixture
def mock_shell_device():
    """Mock shell command execution."""
    device = MockShellDevice(host="192.168.1.103")
    return device


@pytest.fixture
def config():
    """Test configuration matching default.yaml structure."""
    return {
        "device_types": {
            "pjlink": {
                "cooldown_seconds": 1,  # Short for testing
                "request_timeout": 5,
                "verify": {
                    "enabled": True,
                    "interval_seconds": 1,
                    "initial_timeout_seconds": 10,
                    "stable_duration_seconds": 1,
                    "max_retries": 3,
                    "on": {"success_states": [1, 3]},
                    "off": {"success_states": [0, 2]},
                },
            },
            "netio": {
                "cooldown_seconds": 1,
                "request_timeout": 5,
                "verify": {
                    "enabled": True,
                    "interval_seconds": 1,
                    "initial_timeout_seconds": 10,
                    "stable_duration_seconds": 1,
                    "max_retries": 3,
                    "on": {"success_states": [1]},
                    "off": {"success_states": [0]},
                },
            },
            "anel": {
                "cooldown_seconds": 1,
                "request_timeout": 5,
                "runner_url": "http://localhost:8001",
                "runner_api_key": "test-key",
                "verify": {
                    "enabled": True,
                    "interval_seconds": 1,
                    "initial_timeout_seconds": 10,
                    "stable_duration_seconds": 1,
                    "max_retries": 3,
                    "on": {"success_states": [1]},
                    "off": {"success_states": [0]},
                },
            },
            "shell": {
                "cooldown_seconds": 1,
                "request_timeout": 10,
                "verify": {"enabled": False},
            },
        },
        "orchestrator": {
            "on_stagger_delay_seconds": 0.1,  # Fast for testing
            "max_concurrent_on_commands": 10,
            "max_concurrent_off_commands": 50,
            "enable_verification": True,
        },
    }


@pytest.fixture
def mock_device_model():
    """Mock Device database model."""
    from dataclasses import dataclass
    from uuid import UUID

    @dataclass
    class MockDevice:
        id: UUID
        artwork_id: UUID
        name: str
        device_type: str
        host: str
        port: int | None
        enabled: bool
        automation_enabled: bool
        config: dict
        state: int

    return MockDevice(
        id=uuid4(),
        artwork_id=uuid4(),
        name="Test Device",
        device_type="pjlink",
        host="192.168.1.100",
        port=4352,
        enabled=True,
        automation_enabled=True,
        config={"password": "panasonic"},
        state=0,
    )
