# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Configuration management for ANEL runner service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ANELConfig(BaseSettings):
    """ANEL runner service configuration via environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ANEL_",
        env_file=".env",
        extra="ignore",
    )

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080

    # UDP settings
    udp_send_port: int = 9975
    udp_receive_port: int = 9977

    # Queue settings
    command_delay_seconds: float = 0.5
    connection_timeout_seconds: float = 5.0

    # Authentication defaults
    default_user: str = "admin"
    default_password: str = "anel"

    # API settings
    api_key: str | None = None

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_config() -> ANELConfig:
    """Get cached configuration instance."""
    return ANELConfig()
