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

from config import DATABASE_URL, DATA_DIR

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
    
    # --- Profile Metadata ---
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    preferences = Column(JSON, default={"theme": "dark", "autoplay": True})

    play_events = relationship("PlayEvent", back_populates="user", lazy="dynamic")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

class MediaMetadata(Base):
    __tablename__ = "media_metadata"
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
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

    @property
    def resolution_label(self) -> str:
        if not self.width or not self.height:
            return "Unknown"
        if self.height >= 2160: return "4K"
        if self.height >= 1080: return "1080p"
        if self.height >= 720: return "720p"
        return f"{self.height}p"

    @property
    def duration_label(self) -> str:
        if not self.duration_seconds:
            return "00:00"
        mins, secs = divmod(int(self.duration_seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

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

    user = relationship("User", foreign_keys=[user_id])

class PasswordResetToken(Base):
    """Password reset tokens for account recovery."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)  # hashed token
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reset_tokens")

# ── FastAPI Dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# ── Schema Creation & Seeding ─────────────────────────────────────────────────

async def bootstrap_system():
    """
    Bootstrap the system: 
    1. Create all tables.
    2. Run the migration system for schema updates.
    3. Seed initial admin user if none exists.
    """
    from core.migrations import run_migrations
    
    # Ensure initial tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Run formal migrations
    await run_migrations()
    
    # Check for existing users and seed admin if empty
    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(select(func.count()).select_from(User))
            user_count = result.scalar()
        except Exception as e:
            logger.error(f"❌ Error checking user count: {e}")
            user_count = 0

        if user_count == 0:
            from config import ADMIN_USERNAME, ADMIN_PASSWORD
            from core.security import hash_password
            admin = User(
                username=ADMIN_USERNAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role=UserRole.admin,
            )
            db.add(admin)
            await db.commit()
            logger.info(f"🌱 Initialized database and seeded admin: '{ADMIN_USERNAME}'")
        else:
            logger.info("✅ Database tables verified.")

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


# -- Folder Optimization Settings ----------------------------------------------

_OPTIM_FILE = DATA_DIR / "folder_optim.json"

def _load_optim():
    if not _OPTIM_FILE.exists():
        return {}
    try:
        import json
        with open(_OPTIM_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_optim(data):
    try:
        import json
        with open(_OPTIM_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def get_folder_optimization(folder_path: str) -> bool:
    """Check if HLS optimization is enabled for a folder."""
    data = _load_optim()
    return data.get(folder_path, False)

def set_folder_optimization(folder_path: str, enabled: bool):
    """Enable/disable HLS optimization for a folder."""
    data = _load_optim()
    data[folder_path] = enabled
    _save_optim(data)

