"""
StreamDrop — Async Database Engine & Session Factory
Provides:
  - async engine (PostgreSQL or SQLite depending on DATABASE_URL)
  - AsyncSession factory via get_db() FastAPI dependency
  - init_db() to create all tables on startup
  - SQLAlchemy models (User, MediaMetadata, PlayEvent, AuditLog)
"""

import logging
import enum
import uuid
from datetime import datetime
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float,
    ForeignKey, Text, Enum as SAEnum, BigInteger, JSON,
    select, func
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from config import DATABASE_URL

logger = logging.getLogger("streamdrop.database")

# ── Engine ────────────────────────────────────────────────────────────────────
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Models ────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base for all models."""
    pass

class UserRole(str, enum.Enum):
    admin = "admin"
    family = "family"
    guest = "guest"

class PlayEventType(str, enum.Enum):
    play = "play"
    pause = "pause"
    scrub = "scrub"
    complete = "complete"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.guest)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    play_events = relationship("PlayEvent", back_populates="user", lazy="dynamic")

class MediaMetadata(Base):
    __tablename__ = "media_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rel_path = Column(String(1024), unique=True, nullable=False, index=True)
    video_codec = Column(String(32), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    frame_rate = Column(Float, nullable=True)
    bitrate_kbps = Column(Integer, nullable=True)
    audio_codec = Column(String(32), nullable=True)
    audio_channels = Column(Integer, nullable=True)
    audio_sample_rate = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    has_hdr = Column(Boolean, default=False)
    is_hls_ready = Column(Boolean, default=False, nullable=False)
    hls_path = Column(String(1024), nullable=True)
    indexed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    transcoded_at = Column(DateTime(timezone=True), nullable=True)

    play_events = relationship("PlayEvent", back_populates="media", lazy="dynamic")

class PlayEvent(Base):
    """
    Telemetry data: High-volume, low-stakes.
    Used for Resume Playback and analytics.
    """
    __tablename__ = "play_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    media_id = Column(Integer, ForeignKey("media_metadata.id", ondelete="CASCADE"), nullable=True, index=True)
    media_path = Column(String(1024), nullable=True) # Fallback path
    event_type = Column(SAEnum(PlayEventType), nullable=False, default=PlayEventType.play)
    resume_position_seconds = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", back_populates="play_events")
    media = relationship("MediaMetadata", back_populates="play_events")

class AuditLog(Base):
    """
    Security/Integrity data: Low-volume, high-stakes.
    Used for tracking sensitive actions like file deletions or RBAC changes.
    """
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type = Column(String(64), nullable=False)  # e.g., "DOC_EDIT", "FILE_DELETE", "LOGIN"
    target_resource = Column(String(1024), nullable=True) # e.g., /shared/finances.txt
    details = Column(JSON, nullable=True) # JSONB content
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User")

# ── FastAPI Dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# ── Schema Creation ───────────────────────────────────────────────────────────

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables initialized.")

# ── Logging Helpers ───────────────────────────────────────────────────────────

async def log_play_event(
    db: AsyncSession,
    media_path: str,
    resume_pos: float = 0.0,
    user_id: int | None = None,
):
    """Insert a PlayEvent row for resume playback/analytics."""
    media_result = await db.execute(
        select(MediaMetadata.id).where(MediaMetadata.rel_path == media_path)
    )
    media_id = media_result.scalar_one_or_none()

    event = PlayEvent(
        user_id=user_id,
        media_id=media_id,
        resume_position_seconds=resume_pos,
    )
    db.add(event)

async def log_audit(
    db: AsyncSession,
    action_type: str,
    target_resource: str | None = None,
    details: dict[str, Any] | None = None,
    user_id: int | None = None,
):
    """Insert an AuditLog row for security/integrity events."""
    log = AuditLog(
        user_id=user_id,
        action_type=action_type,
        target_resource=target_resource,
        details=details,
    )
    db.add(log)

