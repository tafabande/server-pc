"""
StreamDrop — SQLAlchemy ORM Models
Defines all database tables using async-compatible declarative base.
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
    ForeignKey, Text, Enum as SAEnum, BigInteger, Index,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all models."""
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"    # Full access: read, write, delete, shutdown, transcode
    family = "family"  # Read + upload; no delete, no shutdown
    guest = "guest"    # Read-only; path-restricted to GUEST_ROOT_PATH


class PlayEventType(str, enum.Enum):
    play = "play"
    pause = "pause"
    scrub = "scrub"
    complete = "complete"


# ── Tables ────────────────────────────────────────────────────────────────────

class User(Base):
    """
    A registered user with a role.
    The first admin is seeded from .env ADMIN_USERNAME / ADMIN_PASSWORD on startup.
    Additional users can be created via the admin API.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.guest)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    play_events = relationship("PlayEvent", back_populates="user", lazy="dynamic")


class MediaMetadata(Base):
    """
    ffprobe-extracted metadata for indexed media files.
    Populated as a background task on upload / index scan.
    """
    __tablename__ = "media_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rel_path = Column(String(1024), unique=True, nullable=False, index=True)
    # Video streams
    video_codec = Column(String(32), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    frame_rate = Column(Float, nullable=True)
    bitrate_kbps = Column(Integer, nullable=True)
    # Audio streams
    audio_codec = Column(String(32), nullable=True)
    audio_channels = Column(Integer, nullable=True)
    audio_sample_rate = Column(Integer, nullable=True)
    # Container
    duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    has_hdr = Column(Boolean, default=False)
    # HLS transcode status
    is_hls_ready = Column(Boolean, default=False, nullable=False)
    hls_path = Column(String(1024), nullable=True)
    # Timestamps
    indexed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    transcoded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    play_events = relationship("PlayEvent", back_populates="media", lazy="dynamic")

    @property
    def resolution_label(self) -> str:
        """Human-readable resolution label, e.g. '4K', '1080p'."""
        if self.height is None:
            return "Unknown"
        if self.height >= 2160:
            return "4K"
        if self.height >= 1080:
            return "1080p"
        if self.height >= 720:
            return "720p"
        if self.height >= 480:
            return "480p"
        return f"{self.height}p"

    @property
    def duration_label(self) -> str:
        """Human-readable duration, e.g. '1:23:45'."""
        if self.duration_seconds is None:
            return ""
        secs = int(self.duration_seconds)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class PlayEvent(Base):
    """
    Analytics event fired when a user interacts with a media file.
    Powers Grafana "Most Watched" dashboards and per-user history.
    user_id is nullable to support unauthenticated guest plays.
    """
    __tablename__ = "play_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    media_id = Column(Integer, ForeignKey("media_metadata.id", ondelete="CASCADE"), nullable=True, index=True)
    # Fallback path for files not yet in MediaMetadata
    media_path = Column(String(1024), nullable=True)
    event_type = Column(SAEnum(PlayEventType), nullable=False, default=PlayEventType.play)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="play_events")
    media = relationship("MediaMetadata", back_populates="play_events")


class AuditLog(Base):
    """
    General purpose audit trail for system events (file edits, admin actions).
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    action = Column(String(128), nullable=False)    # e.g. "Edited", "Deleted", "Login"
    resource = Column(String(1024), nullable=True)  # e.g. "document.txt"
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User")
