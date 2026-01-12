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
    exclude_from_auto_onoff = Column(Boolean, default=False, nullable=False)

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
