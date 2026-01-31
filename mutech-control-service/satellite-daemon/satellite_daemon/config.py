# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Configuration management for satellite daemon."""

import os
import secrets
from pathlib import Path
from typing import Optional

import yaml


DEFAULT_CONFIG_PATH = Path("/etc/satellite-daemon/config.yaml")
DEFAULT_STATE_PATH = Path("/var/lib/satellite-daemon/state.yaml")


class Config:
    """Configuration manager for satellite daemon."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
    ):
        self.config_path = config_path or Path(
            os.environ.get("SATELLITE_CONFIG", DEFAULT_CONFIG_PATH)
        )
        self.state_path = state_path or Path(
            os.environ.get("SATELLITE_STATE", DEFAULT_STATE_PATH)
        )

        self._config: dict = {}
        self._state: dict = {}

    def load(self) -> None:
        """Load configuration and state from files."""
        # Load config
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = yaml.safe_load(f) or {}

        # Load state
        if self.state_path.exists():
            with open(self.state_path) as f:
                self._state = yaml.safe_load(f) or {}

    def save_state(self) -> None:
        """Save state to file."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            yaml.dump(self._state, f, default_flow_style=False)

    @property
    def server_url(self) -> str:
        """Get server WebSocket URL."""
        url = self._config.get("server_url", "")
        if not url:
            raise ValueError("server_url must be configured in config.yaml")
        return url

    @property
    def api_key(self) -> str:
        """Get or generate API key."""
        if "api_key" not in self._state:
            self._state["api_key"] = secrets.token_urlsafe(32)
            self.save_state()
        return self._state["api_key"]

    @property
    def satellite_id(self) -> Optional[str]:
        """Get satellite ID (assigned after approval)."""
        return self._state.get("satellite_id")

    @satellite_id.setter
    def satellite_id(self, value: str) -> None:
        """Set satellite ID."""
        self._state["satellite_id"] = value
        self.save_state()

    @property
    def satellite_name(self) -> Optional[str]:
        """Get satellite name (assigned after approval)."""
        return self._state.get("name")

    @satellite_name.setter
    def satellite_name(self, value: str) -> None:
        """Set satellite name."""
        self._state["name"] = value
        self.save_state()

    @property
    def is_approved(self) -> bool:
        """Check if satellite is approved."""
        return self.satellite_id is not None

    @property
    def hostname(self) -> str:
        """Get system hostname."""
        import socket
        return socket.gethostname()

    @property
    def reconnect_delay(self) -> float:
        """Get reconnect delay in seconds."""
        return self._config.get("reconnect_delay", 5.0)

    @property
    def heartbeat_interval(self) -> float:
        """Get heartbeat interval in seconds."""
        return self._config.get("heartbeat_interval", 30.0)

    @property
    def command_timeout(self) -> float:
        """Get command timeout in seconds."""
        return self._config.get("command_timeout", 30.0)
