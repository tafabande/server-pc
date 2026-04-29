"""
StreamDrop — Media Analytics API Router
Handles play event logging, per-user history, and popularity analytics.
Powers Grafana "Most Watched by Role" dashboards.

Endpoints:
  POST /api/media/event     — Log a play/pause/scrub/complete event
  GET  /api/media/history   — Current user's last N events
  GET  /api/media/popular   — Top N most-played files (admin only)
  POST /api/media/transcode — Manually trigger HLS transcode (admin only)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, PlayEvent, PlayEventType, MediaMetadata, User
from auth.rbac import get_current_user, require_role, UserContext

logger = logging.getLogger("streamdrop.media_api")
router = APIRouter(prefix="/api/media", tags=["Media Analytics"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PlayEventRequest(BaseModel):
    media_path: str = Field(..., description="Relative path of the media file")
    event_type: PlayEventType = PlayEventType.play
    position: float = Field(0.0, description="Resume position in seconds")


class TranscodeRequest(BaseModel):
    rel_path: str = Field(..., description="Relative path of the video to transcode")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/event")
async def log_event(
    body: PlayEventRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log a media interaction event for analytics.
    Called by the frontend player on play, pause, scrub, and completion.
    """
    # Resolve media_id if the file is indexed
    result = await db.execute(
        select(MediaMetadata.id).where(MediaMetadata.rel_path == body.media_path)
    )
    media_id = result.scalar_one_or_none()

    event = PlayEvent(
        user_id=user.user_id,
        media_id=media_id,
        media_path=body.media_path,
        event_type=body.event_type,
        resume_position_seconds=body.position,
    )
    db.add(event)
    # Commit is handled by get_db dependency

    # Increment Prometheus counter
    try:
        from core.main import PLAY_EVENTS_COUNTER
        PLAY_EVENTS_COUNTER.labels(event_type=body.event_type.value).inc()
    except Exception:
        pass

    return {"status": "ok", "event_type": body.event_type.value}


@router.get("/history")
async def get_history(
    limit: int = 50,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's last N play events."""
    result = await db.execute(
        select(PlayEvent)
        .where(PlayEvent.user_id == user.user_id)
        .order_by(desc(PlayEvent.timestamp))
        .limit(limit)
    )
    events = result.scalars().all()
    return {
        "events": [
            {
                "id": e.id,
                "media_path": e.media_path,
                "event_type": e.event_type.value,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]
    }


@router.get("/popular", dependencies=[Depends(require_role("admin", "family"))])
async def get_popular(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    Top N most-played media files by play event count.
    Powers the 'Most Watched' Grafana dashboard panel.
    """
    result = await db.execute(
        select(
            PlayEvent.media_path,
            func.count(PlayEvent.id).label("play_count"),
        )
        .where(PlayEvent.event_type == PlayEventType.play)
        .group_by(PlayEvent.media_path)
        .order_by(desc("play_count"))
        .limit(limit)
    )
    rows = result.fetchall()
    return {
        "popular": [
            {"media_path": row.media_path, "play_count": row.play_count}
            for row in rows
        ]
    }


@router.get("/popular-by-role", dependencies=[Depends(require_role("admin"))])
async def get_popular_by_role(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Netflix-style analytics: top plays grouped by user role.
    Data source for Grafana 'Most Watched by Role' dashboard.
    """
    result = await db.execute(
        select(
            User.role,
            PlayEvent.media_path,
            func.count(PlayEvent.id).label("play_count"),
        )
        .join(User, PlayEvent.user_id == User.id, isouter=True)
        .where(PlayEvent.event_type == PlayEventType.play)
        .group_by(User.role, PlayEvent.media_path)
        .order_by(desc("play_count"))
        .limit(limit)
    )
    rows = result.fetchall()
    return {
        "by_role": [
            {
                "role": row.role.value if row.role else "guest",
                "media_path": row.media_path,
                "play_count": row.play_count,
            }
            for row in rows
        ]
    }


@router.post("/transcode", dependencies=[Depends(require_role("admin"))])
async def trigger_transcode(body: TranscodeRequest):
    """
    Manually trigger HLS transcoding for a specific video file. Admin-only.
    Returns immediately — the job runs asynchronously in the Celery worker.
    """
    from config import SHARED_FOLDER
    abs_path = str((SHARED_FOLDER / body.rel_path).resolve())

    if not (SHARED_FOLDER / body.rel_path).exists():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        from core.workers import transcode_to_hls
        # Run in background via asyncio
        import asyncio
        asyncio.create_task(transcode_to_hls(body.rel_path))
        return {"status": "ok", "message": f"Transcode started for: {body.rel_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcode failed to start: {e}")
