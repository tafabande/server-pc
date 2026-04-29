"""
StreamDrop — HLS Transcoding Worker
Converts video files to HLS (HTTP Live Streaming) format using FFmpeg.

Key design decisions:
  - Strict GOP (Group of Pictures) size: -g 48 at 24fps = keyframe every 2 seconds.
    This guarantees the browser player can seek to ANY timestamp instantly
    without buffering artifacts ("perfect scrubbing").
  - Output stored in TRANSCODE_DIR (isolated from SHARED_FOLDER).
    This allows SHARED_FOLDER to be read-only in Docker, protecting source media.
  - HLS segment duration: 2 seconds (matches GOP size).
  - VOD playlist type: allows the player to seek anywhere in the timeline.
"""

import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from workers.celery_app import celery_app

logger = logging.getLogger("streamdrop.hls_worker")

# FFmpeg HLS settings
HLS_SEGMENT_DURATION = 2      # Seconds per .ts segment
GOP_SIZE = 48                  # Keyframe every 2s @ 24fps (auto-scaled by FFmpeg to match fps)
HLS_PLAYLIST_TYPE = "vod"     # Seekable, finite playlist


def _get_hls_output_dir(rel_path: str) -> Path:
    """
    Deterministic output directory for HLS files, OUTSIDE the media root.
    Uses MD5 hash of the relative path to avoid filename collisions.
    """
    import hashlib
    from config import TRANSCODE_DIR
    path_hash = hashlib.md5(rel_path.encode()).hexdigest()
    return TRANSCODE_DIR / path_hash


def _build_ffmpeg_command(input_path: str, output_dir: Path) -> list[str]:
    """
    Build the FFmpeg command for HLS transcoding.
    Enforces strict GOP for perfect scrubbing.
    """
    playlist_path = output_dir / "index.m3u8"
    segment_pattern = output_dir / "seg%04d.ts"

    return [
        "ffmpeg",
        "-y",                          # Overwrite output
        "-i", input_path,              # Input file
        # Video settings
        "-c:v", "libx264",             # H.264 for maximum browser compatibility
        "-preset", "fast",             # Encoding speed vs. compression tradeoff
        "-crf", "23",                  # Constant Rate Factor (quality)
        "-profile:v", "high",
        "-level", "4.0",
        # GOP settings (THE KEY to perfect scrubbing)
        "-g", str(GOP_SIZE),           # Keyframe every GOP_SIZE frames
        "-keyint_min", str(GOP_SIZE),  # Minimum keyframe interval = GOP size
        "-sc_threshold", "0",          # Disable scene-change keyframes (breaks strict GOP)
        # Audio settings
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",                    # Downmix to stereo for universal compatibility
        # HLS output settings
        "-f", "hls",
        "-hls_time", str(HLS_SEGMENT_DURATION),
        "-hls_playlist_type", HLS_PLAYLIST_TYPE,
        "-hls_segment_filename", str(segment_pattern),
        str(playlist_path),
    ]


# ── Celery Task ────────────────────────────────────────────────────────────────

@celery_app.task(
    name="workers.hls_worker.transcode_to_hls",
    bind=True,
    max_retries=2,
    time_limit=3600,  # 1 hour max (for very large files)
    soft_time_limit=3500,
)
def transcode_to_hls(self, rel_path: str, abs_path: str | None = None):
    """
    Celery task: transcode a video to HLS and update MediaMetadata.
    Can be called with just rel_path (abs_path derived from config).
    """
    try:
        asyncio.run(_transcode(rel_path, abs_path))
    except Exception as exc:
        logger.error(f"HLS transcode failed for {rel_path}: {exc}")
        raise self.retry(exc=exc, countdown=120)


async def _transcode(rel_path: str, abs_path: str | None):
    """Core async transcode logic."""
    from config import SHARED_FOLDER
    from sqlalchemy import select
    from core.database import AsyncSessionFactory
    from db.models import MediaMetadata

    if abs_path is None:
        abs_path = str((SHARED_FOLDER / rel_path).resolve())

    input_path = Path(abs_path)
    if not input_path.exists():
        logger.error(f"Source file not found: {abs_path}")
        return

    # Check if already transcoded
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path == rel_path)
        )
        meta = result.scalar_one_or_none()
        if meta and meta.is_hls_ready and meta.hls_path:
            hls_playlist = Path(meta.hls_path)
            if hls_playlist.exists():
                logger.info(f"⏭️  Already transcoded: {rel_path}")
                return

    # Prepare output directory (OUTSIDE shared folder — read-only safe)
    output_dir = _get_hls_output_dir(rel_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    playlist_path = output_dir / "index.m3u8"

    # Build and run FFmpeg
    cmd = _build_ffmpeg_command(abs_path, output_dir)
    logger.info(f"🎬 Starting HLS transcode: {rel_path} → {output_dir}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace")[-500:] if stderr else "unknown"
        logger.error(f"FFmpeg failed for {rel_path}: {error_msg}")
        # Clean up partial output
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        raise RuntimeError(f"FFmpeg exited with code {proc.returncode}")

    if not playlist_path.exists():
        raise RuntimeError(f"FFmpeg finished but playlist not created: {playlist_path}")

    logger.info(f"✅ HLS ready: {rel_path} → {playlist_path}")

    # Update database
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path == rel_path)
        )
        meta = result.scalar_one_or_none()

        if meta is None:
            meta = MediaMetadata(rel_path=rel_path)
            db.add(meta)

        meta.is_hls_ready = True
        meta.hls_path = str(playlist_path)
        meta.transcoded_at = datetime.now(timezone.utc)
        await db.commit()


# ── Sync entry point (for Celery worker calling from non-async context) ────────

def transcode_sync(rel_path: str, abs_path: str | None = None):
    """Direct synchronous call for testing with Celery in ALWAYS_EAGER mode."""
    asyncio.run(_transcode(rel_path, abs_path))
