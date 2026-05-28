# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Pydantic models for API request/response."""

from pydantic import BaseModel, Field


class StateResponse(BaseModel):
    """Response for state query endpoint."""

    host: str
    port: int
    state: int = Field(description="0=off, 1=on, -1=error")
    name: str | None = None
    success: bool = True
    error: str | None = None


class CommandResponse(BaseModel):
    """Response for power command endpoints."""

    success: bool
    host: str
    port: int
    command: str
    state: int | None = Field(None, description="New state after command: 0=off, 1=on")
    error: str | None = None


class PortInfo(BaseModel):
    """Port information."""

    port: int
    name: str
    state: int


class DeviceInfoResponse(BaseModel):
    """Response for device info endpoint."""

    host: str
    name: str
    ip: str
    mac: str | None = None
    ports: list[PortInfo]
    temperature: float | None = None
    success: bool = True
    error: str | None = None


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: str
    queue_length: int
    is_processing: bool


class ServiceInfoResponse(BaseModel):
    """Response for service info endpoint."""

    version: str
    udp_send_port: int
    udp_receive_port: int
    command_delay_seconds: float


class CachedDeviceState(BaseModel):
    """Cached device state from UDP broadcast."""

    host: str
    name: str
    ports: list[PortInfo]
    temperature: float | None = None
    mac: str | None = None


class BroadcastCacheResponse(BaseModel):
    """Response for broadcast cache endpoint."""

    device_count: int
    devices: list[CachedDeviceState]
