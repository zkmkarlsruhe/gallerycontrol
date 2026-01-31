# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Satellite(Base):
    """Satellite relay for devices in NATed/closed networks."""

    __tablename__ = "satellites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(64), nullable=False, unique=True)  # SHA-256
    status = Column(String(20), default="pending", nullable=False)  # pending/approved/offline
    hostname = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    exhibitions = relationship("Exhibition", back_populates="satellite")

    # Indexes
    __table_args__ = (
        Index("idx_satellites_api_key_hash", "api_key_hash"),
        Index("idx_satellites_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Satellite(id={self.id}, name='{self.name}', status='{self.status}')>"


class Exhibition(Base):
    """Exhibition model."""

    __tablename__ = "exhibitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    schedules_enabled = Column(Boolean, default=False, nullable=False)  # Enable schedules feature
    satellite_id = Column(
        UUID(as_uuid=True),
        ForeignKey("satellites.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    artworks = relationship("Artwork", back_populates="exhibition", cascade="all, delete-orphan")
    satellite = relationship("Satellite", back_populates="exhibitions")

    # Indexes
    __table_args__ = (Index("idx_exhibitions_satellite", "satellite_id"),)

    def __repr__(self) -> str:
        return f"<Exhibition(id={self.id}, name='{self.name}', enabled={self.enabled})>"


class Artwork(Base):
    """Artwork model."""

    __tablename__ = "artworks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    exhibition_id = Column(UUID(as_uuid=True), ForeignKey("exhibitions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    protection_config = Column(JSON, nullable=True)  # Protection rules for overuse prevention
    accepting_triggers = Column(Boolean, default=False, nullable=False)  # Gate for fast-lane API
    timeslice_enabled = Column(Boolean, default=False, nullable=False)  # Enable time slice protection
    schedules_enabled = Column(Boolean, default=False, nullable=False)  # Enable schedules feature
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    exhibition = relationship("Exhibition", back_populates="artworks")
    devices = relationship("Device", back_populates="artwork", cascade="all, delete-orphan")
    protection_state = relationship(
        "ArtworkProtectionState",
        back_populates="artwork",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (Index("idx_artworks_exhibition", "exhibition_id"),)

    def __repr__(self) -> str:
        return f"<Artwork(id={self.id}, name='{self.name}', enabled={self.enabled})>"


class Device(Base):
    """Device model (formerly 'unit')."""

    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    artwork_id = Column(UUID(as_uuid=True), ForeignKey("artworks.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    device_type = Column(String(50), nullable=False)  # 'pjlink', 'netio', 'anel', 'shell'
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=True)

    # Control flags
    enabled = Column(Boolean, default=True, nullable=False)
    automation_enabled = Column(Boolean, default=True, nullable=False)
    schedules_enabled = Column(Boolean, default=False, nullable=False)  # Enable schedules feature
    use_satellite = Column(Boolean, default=False, nullable=False)  # Route via exhibition satellite

    # Configuration (device-specific JSON)
    config = Column(JSON, default=dict, nullable=False)

    # State management
    state = Column(Integer, default=-1, nullable=False)  # -1=error, 0=off, 1=on, 2=cooling, 3=warming
    last_checked_at = Column(DateTime, nullable=True)
    next_check_allowed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # DNS resolution (all device types)
    resolved = Column(String(255), nullable=True)  # Resolved hostname or IP
    resolved_at = Column(DateTime, nullable=True)  # When DNS was last resolved

    # Cached device info (MAC, model, firmware, etc.)
    cached_info = Column(JSON, nullable=True)  # Cached device identity info
    cached_info_at = Column(DateTime, nullable=True)  # When cache was last updated

    # Asset linking (PJLink only)
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    artwork = relationship("Artwork", back_populates="devices")
    command_logs = relationship("CommandLog", back_populates="device")
    state_changes = relationship("StateChangeLog", back_populates="device", cascade="all, delete-orphan")
    asset = relationship("Asset", back_populates="devices")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_devices_artwork", "artwork_id"),
        Index("idx_devices_enabled", "enabled"),
        Index("idx_devices_type", "device_type"),
        Index("idx_devices_asset", "asset_id"),
        UniqueConstraint("host", "port", "device_type", name="unique_device"),
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, name='{self.name}', type='{self.device_type}', state={self.state})>"


class CommandLog(Base):
    """Command execution log."""

    __tablename__ = "command_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    command = Column(String(50), nullable=False)  # 'on', 'off', 'state'
    source = Column(String(50), nullable=False)  # 'web', 'fast', 'admin', 'verification'
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    device = relationship("Device", back_populates="command_logs")

    # Indexes
    __table_args__ = (
        Index("idx_command_log_device", "device_id"),
        Index("idx_command_log_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<CommandLog(id={self.id}, command='{self.command}', success={self.success})>"


class Credential(Base):
    """Credential store for device authentication."""

    __tablename__ = "credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "museumstechnik"
    credential_type = Column(String(20), nullable=False, default="shell")  # shell, pjlink, netio, anel
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (Index("idx_credentials_type", "credential_type"),)

    def __repr__(self) -> str:
        return f"<Credential(id={self.id}, name='{self.name}', type='{self.credential_type}')>"


class ShellTemplate(Base):
    """Shell command template for reusable device configurations."""

    __tablename__ = "shell_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status_command = Column(Text, nullable=True)
    status_on_pattern = Column(String(255), nullable=True)
    status_off_pattern = Column(String(255), nullable=True)
    on_command = Column(Text, nullable=True)
    off_command = Column(Text, nullable=True)
    actions = Column(JSON, nullable=True)  # Array of {name, cmd} for custom actions
    onoff_mode = Column(Boolean, default=True, nullable=False)  # True=ON/OFF mode, False=Actions mode
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ShellTemplate(id={self.id}, name='{self.name}')>"


class StateChangeLog(Base):
    """State change log - records actual device state transitions."""

    __tablename__ = "state_change_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    # Denormalized for historical accuracy - captures artwork/exhibition at log time
    artwork_id = Column(UUID(as_uuid=True), nullable=True)
    exhibition_id = Column(UUID(as_uuid=True), nullable=True)
    previous_state = Column(Integer, nullable=False)  # -1=error, 0=off, 1=on, 2=cooling, 3=warming
    new_state = Column(Integer, nullable=False)
    trigger = Column(String(50), nullable=False)  # 'polling', 'command', 'verification'
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    device = relationship("Device", back_populates="state_changes")

    # Indexes
    __table_args__ = (
        Index("idx_state_change_device", "device_id"),
        Index("idx_state_change_timestamp", "timestamp"),
        Index("idx_state_change_new_state", "new_state"),
        Index("idx_state_change_exhibition", "exhibition_id"),
    )

    def __repr__(self) -> str:
        return f"<StateChangeLog(id={self.id}, {self.previous_state} -> {self.new_state}, trigger='{self.trigger}')>"


class DeviceOperationLog(Base):
    """Detailed device operation log for debugging with raw responses."""

    __tablename__ = "device_operation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    # Denormalized for historical accuracy - captures artwork/exhibition at log time
    artwork_id = Column(UUID(as_uuid=True), nullable=True)
    exhibition_id = Column(UUID(as_uuid=True), nullable=True)
    operation_type = Column(String(20), nullable=False)  # 'state_query', 'power_on', 'power_off', 'action'
    source = Column(String(20), nullable=False)  # 'polling', 'web', 'fast', 'verification'
    success = Column(Boolean, nullable=False)
    state_before = Column(Integer, nullable=True)
    state_after = Column(Integer, nullable=True)
    raw_request = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    device = relationship("Device", backref="operation_logs")

    # Indexes
    __table_args__ = (
        Index("idx_device_op_log_device", "device_id"),
        Index("idx_device_op_log_timestamp", "timestamp"),
        Index("idx_device_op_log_success", "success"),
        Index("idx_device_op_log_type", "operation_type"),
        Index("idx_device_op_log_exhibition", "exhibition_id"),
    )

    def __repr__(self) -> str:
        return f"<DeviceOperationLog(id={self.id}, op='{self.operation_type}', success={self.success})>"


class Asset(Base):
    """Projector asset for tracking lamp hours across onboard/offboard cycles.

    Only used for PJLink devices. Asset number is extracted from hostname.
    All device details (manufacturer, model, lamp hours) come from PJLink queries.
    """

    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_number = Column(String(50), unique=True, nullable=False)  # e.g., "100018987"
    hostname = Column(String(255), nullable=True)  # Full resolved hostname
    hostname_manual = Column(Boolean, default=False, nullable=False)  # True if user manually set hostname
    notes = Column(Text, nullable=True)  # Optional human notes
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    lamp_history = relationship("LampHoursLog", back_populates="asset", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="asset")

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, asset_number='{self.asset_number}')>"


class LampHoursLog(Base):
    """Lamp hours history log for projector assets.

    Records lamp hours at key events: onboard, power_on, offboard.
    Keeps history even after device is offboarded.
    """

    __tablename__ = "lamp_hours_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)

    lamp_hours = Column(Integer, nullable=False)
    event_type = Column(String(20), nullable=False)  # 'onboard', 'power_on', 'offboard'

    # Denormalized context at time of recording (for historical accuracy)
    exhibition_name = Column(String(255), nullable=True)
    artwork_name = Column(String(255), nullable=True)
    device_name = Column(String(255), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    asset = relationship("Asset", back_populates="lamp_history")

    # Indexes
    __table_args__ = (
        Index("idx_lamp_hours_asset", "asset_id"),
        Index("idx_lamp_hours_timestamp", "timestamp"),
        Index("idx_lamp_hours_event", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<LampHoursLog(id={self.id}, asset={self.asset_id}, hours={self.lamp_hours}, event='{self.event_type}')>"


class ScheduledJob(Base):
    """Unified scheduled job for cron-based and one-shot execution.

    Handles both system maintenance tasks (asset_linker, log_cleanup, etc.)
    and device automation (turn projector on at 9am, or one-shot delayed tasks).

    For recurring jobs: cron_expression is required, run_once=False
    For one-shot jobs: cron_expression is None, run_once=True, use next_run_at
    """

    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    job_type = Column(String(20), nullable=False)  # 'system' or 'device'
    cron_expression = Column(String(100), nullable=True)  # Nullable for one-shot jobs

    # One-shot support
    run_once = Column(Boolean, default=False, nullable=False)  # True for one-shot tasks
    executed_at = Column(DateTime, nullable=True)  # When one-shot was executed (for cleanup)

    # Target flexibility for device/artwork/exhibition
    target_type = Column(String(20), default="device", nullable=False)  # device, artwork, exhibition
    target_id = Column(UUID(as_uuid=True), nullable=True)  # Generic target UUID (no FK)

    # Device job fields (kept for backward compat with device targets)
    target_device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
    )
    action_type = Column(String(20), nullable=True)  # 'on', 'off', 'action'
    action_name = Column(String(100), nullable=True)  # For shell device actions

    # System job fields
    task_name = Column(String(50), nullable=True)  # 'asset_linker', 'log_cleanup', etc.
    task_config = Column(JSON, nullable=True)  # Task-specific configuration

    # State
    enabled = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    last_success = Column(Boolean, nullable=True)
    last_error = Column(Text, nullable=True)
    last_duration_ms = Column(Integer, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    # Resiliency
    fail_count = Column(Integer, default=0, nullable=False)
    backoff_until = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    target_device = relationship("Device", backref="scheduled_jobs")
    execution_logs = relationship(
        "ScheduledJobLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="desc(ScheduledJobLog.executed_at)",
    )

    # Indexes
    __table_args__ = (
        Index(
            "idx_scheduled_jobs_enabled_next_run",
            "enabled",
            "next_run_at",
            postgresql_where=text("enabled = true"),
        ),
        Index("idx_scheduled_jobs_job_type", "job_type"),
        Index(
            "idx_scheduled_jobs_device",
            "target_device_id",
            postgresql_where=text("target_device_id IS NOT NULL"),
        ),
        Index(
            "idx_scheduled_jobs_task_name",
            "task_name",
            postgresql_where=text("task_name IS NOT NULL"),
        ),
        Index(
            "idx_scheduled_jobs_one_shot_pending",
            "run_once",
            "executed_at",
            postgresql_where=text("run_once = true AND executed_at IS NULL"),
        ),
        Index(
            "idx_scheduled_jobs_one_shot_executed",
            "run_once",
            "executed_at",
            postgresql_where=text("run_once = true AND executed_at IS NOT NULL"),
        ),
    )

    @property
    def circuit_open(self) -> bool:
        """Circuit is open after 5 consecutive failures."""
        return self.fail_count >= 5

    @property
    def is_pending_one_shot(self) -> bool:
        """True if this is a pending one-shot job."""
        return self.run_once and self.executed_at is None

    def __repr__(self) -> str:
        return f"<ScheduledJob(id={self.id}, name='{self.name}', type='{self.job_type}', enabled={self.enabled})>"


class ScheduledJobLog(Base):
    """Execution history for scheduled jobs."""

    __tablename__ = "scheduled_job_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scheduled_at = Column(DateTime, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    result = Column(JSON, nullable=True)  # Task result data for system jobs

    # Relationships
    job = relationship("ScheduledJob", back_populates="execution_logs")

    # Indexes
    __table_args__ = (
        Index("idx_scheduled_job_logs_job_executed", "job_id", "executed_at"),
    )

    def __repr__(self) -> str:
        return f"<ScheduledJobLog(id={self.id}, job={self.job_id}, success={self.success})>"


class ArtworkProtectionState(Base):
    """Runtime state for artwork protection tracking.

    Stores the current protection state for artworks with protection_config enabled.
    Tracks running status, cooldown periods, and time-slice budget usage.

    Protection config schema (stored in Artwork.protection_config):
        New simplified format:
        {
            "slice_window": "15m",       # Time window duration
            "slice_budget": "7m",        # Max runtime per window
            "max_runtime": "2m30s",      # Max continuous runtime
            "min_runtime": "30s",        # Min runtime per activation
            "cooldown": "2m",            # Rest time after forced stop
            "force_completion": false,   # Ignore OFF until max_runtime
        }

        Legacy format (still supported):
        {
            "time_slices": [
                {"window": 15, "max": 7},   # max 7 min per 15-min chunk
            ],
            "max_runtime": 150,        # seconds continuous runtime
            "cooldown": 120,           # seconds forced rest after max_runtime
            "force_completion": false, # if true, ignore OFF until max_runtime
            "min_budget_to_start": 60  # won't start if budget < this (seconds)
        }
    """

    __tablename__ = "artwork_protection_states"

    artwork_id = Column(
        UUID(as_uuid=True),
        ForeignKey("artworks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_running = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime, nullable=True)  # When current run started
    cooldown_until = Column(DateTime, nullable=True)  # Active cooldown period end
    time_slice_usage = Column(JSON, default=dict, nullable=False)  # {"15": 420, "60": 1200}
    last_window_reset = Column(JSON, default=dict, nullable=False)  # {"15": "2024-...", "60": "..."}
    desired_state = Column(String(10), default="off", nullable=False)  # Sensor's desired state
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    artwork = relationship("Artwork", back_populates="protection_state")

    def __repr__(self) -> str:
        return f"<ArtworkProtectionState(artwork_id={self.artwork_id}, is_running={self.is_running})>"
