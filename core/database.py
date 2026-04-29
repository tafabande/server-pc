"""
StreamDrop — Async Database Engine & Session Factory
Replaces the old raw sqlite3 module with SQLAlchemy async ORM.

Provides:
  - async engine (PostgreSQL or SQLite depending on DATABASE_URL)
  - AsyncSession factory via get_db() FastAPI dependency
  - init_db() to create all tables on startup
  - Legacy helpers (add_video_job, etc.) for backwards compatibility
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from config import DATABASE_URL

logger = logging.getLogger("streamdrop.database")

# ── Engine ────────────────────────────────────────────────────────────────────
# connect_args only applies to SQLite (thread-check is not needed async)
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # Set True for SQL query logging during debugging
    pool_pre_ping=True,  # Reconnect if DB connection dropped
    connect_args=_connect_args,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI Dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields an AsyncSession and commits/rolls back automatically.
    Usage:
        @router.get("/something")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Schema Creation ───────────────────────────────────────────────────────────

async def init_db():
    """Create all tables. Safe to call on every startup (CREATE IF NOT EXISTS)."""
    from db.models import Base  # import here to avoid circular imports
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables initialized.")


# ── Legacy Compatibility Helpers ──────────────────────────────────────────────
# These thin wrappers allow old code (routers, workers) to keep working
# while we migrate to using the ORM directly.

async def add_video_job(file_path: str):
    """Queue a video file for HLS transcoding (via Celery worker)."""
    from workers.celery_app import celery_app
    try:
        celery_app.send_task("workers.hls_worker.transcode_to_hls", args=[file_path])
        logger.info(f"📤 Dispatched HLS transcode job: {file_path}")
    except Exception as e:
        logger.warning(f"Celery unavailable, skipping transcode job: {e}")


async def get_media_metadata(rel_path: str, db: AsyncSession):
    """Fetch MediaMetadata for a given relative path, or None."""
    from sqlalchemy import select
    from db.models import MediaMetadata
    result = await db.execute(
        select(MediaMetadata).where(MediaMetadata.rel_path == rel_path)
    )
    return result.scalar_one_or_none()


async def log_play_event(
    db: AsyncSession,
    media_path: str,
    event_type: str = "play",
    user_id: int | None = None,
):
    """Insert a PlayEvent row for analytics."""
    from db.models import PlayEvent, PlayEventType, MediaMetadata
    from sqlalchemy import select

    # Try to resolve media_id
    media_result = await db.execute(
        select(MediaMetadata.id).where(MediaMetadata.rel_path == media_path)
    )
    media_id = media_result.scalar_one_or_none()

    event = PlayEvent(
        user_id=user_id,
        media_id=media_id,
        media_path=media_path,
        event_type=PlayEventType(event_type),
    )
    db.add(event)
    # Caller is responsible for commit (handled by get_db dependency)


# ── Folder optimization (legacy shim) ─────────────────────────────────────────
# Kept for routers/file_api.py backwards compatibility.
# Uses a simple in-memory dict since folder optimization state is ephemeral.
_folder_optimization: dict[str, bool] = {}


def set_folder_optimization(folder_path: str, enabled: bool):
    _folder_optimization[folder_path] = enabled


def get_folder_optimization(folder_path: str) -> bool:
    return _folder_optimization.get(folder_path, False)

async def log_audit(
    db: AsyncSession,
    action: str,
    resource: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
):
    """Insert an AuditLog row for system events."""
    from db.models import AuditLog
    log = AuditLog(
        user_id=user_id,
        ip_address=ip_address,
        action=action,
        resource=resource,
    )
    db.add(log)
    # Commit handled by caller or dependency
