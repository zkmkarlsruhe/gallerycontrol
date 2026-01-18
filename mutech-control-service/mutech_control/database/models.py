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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Exhibition(Base):
    """Exhibition model."""

    __tablename__ = "exhibitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    artworks = relationship("Artwork", back_populates="exhibition", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Exhibition(id={self.id}, name='{self.name}', enabled={self.enabled})>"


class Artwork(Base):
    """Artwork model."""

    __tablename__ = "artworks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    exhibition_id = Column(UUID(as_uuid=True), ForeignKey("exhibitions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    exhibition = relationship("Exhibition", back_populates="artworks")
    devices = relationship("Device", back_populates="artwork", cascade="all, delete-orphan")

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

    # Configuration (device-specific JSON)
    config = Column(JSON, default=dict, nullable=False)

    # State management
    state = Column(Integer, default=-1, nullable=False)  # -1=error, 0=off, 1=on, 2=cooling, 3=warming
    last_checked_at = Column(DateTime, nullable=True)
    next_check_allowed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    artwork = relationship("Artwork", back_populates="devices")
    command_logs = relationship("CommandLog", back_populates="device")
    state_changes = relationship("StateChangeLog", back_populates="device", cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_devices_artwork", "artwork_id"),
        Index("idx_devices_enabled", "enabled"),
        Index("idx_devices_type", "device_type"),
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
