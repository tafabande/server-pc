"""
StreamDrop — FFprobe Metadata Worker
Extracts codec, resolution, bitrate, audio tracks, and duration from media files.
Stores results in the MediaMetadata table for rich UI display and HLS routing.

Designed to run:
  1. As a Celery task (background, non-blocking).
  2. As a direct async call from upload handlers (await probe_file_async(...)).
  3. Via Celery beat for re-processing pending files.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from workers.celery_app import celery_app

logger = logging.getLogger("streamdrop.ffprobe")


# ── Core ffprobe logic (sync, runs in worker process) ─────────────────────────

def _run_ffprobe(abs_path: str) -> Optional[dict]:
    """
    Run ffprobe on the given file and return parsed JSON.
    Returns None if ffprobe is not installed or the file is not a media file.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(abs_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.debug(f"ffprobe returned non-zero for {abs_path}: {result.stderr[:200]}")
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        logger.warning("ffprobe not found. Install FFmpeg to enable metadata extraction.")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out for {abs_path}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"ffprobe output parse error for {abs_path}: {e}")
        return None


def _parse_ffprobe_output(data: dict, file_size_bytes: int) -> dict:
    """
    Parse raw ffprobe JSON into a clean metadata dict.
    """
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), None
    )
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    first_audio = audio_streams[0] if audio_streams else None

    # Duration: prefer format-level (more accurate for containers like MKV)
    duration = None
    raw_duration = fmt.get("duration") or (video_stream or {}).get("duration")
    if raw_duration:
        try:
            duration = float(raw_duration)
        except (ValueError, TypeError):
            pass

    # Frame rate: rational string like "30000/1001" or "30/1"
    frame_rate = None
    raw_fps = (video_stream or {}).get("avg_frame_rate", "")
    if raw_fps and "/" in raw_fps:
        try:
            num, den = raw_fps.split("/")
            if int(den) > 0:
                frame_rate = round(int(num) / int(den), 3)
        except (ValueError, ZeroDivisionError):
            pass

    # Bitrate in kbps
    bitrate_kbps = None
    raw_bitrate = fmt.get("bit_rate") or (video_stream or {}).get("bit_rate")
    if raw_bitrate:
        try:
            bitrate_kbps = int(int(raw_bitrate) / 1000)
        except (ValueError, TypeError):
            pass

    # HDR detection: check color_transfer tag
    has_hdr = False
    if video_stream:
        color_transfer = video_stream.get("color_transfer", "")
        has_hdr = color_transfer in {"smpte2084", "arib-std-b67", "smpte428"}

    return {
        "video_codec": (video_stream or {}).get("codec_name"),
        "width": (video_stream or {}).get("width"),
        "height": (video_stream or {}).get("height"),
        "frame_rate": frame_rate,
        "bitrate_kbps": bitrate_kbps,
        "audio_codec": (first_audio or {}).get("codec_name"),
        "audio_channels": (first_audio or {}).get("channels"),
        "audio_sample_rate": int((first_audio or {}).get("sample_rate", 0) or 0) or None,
        "duration_seconds": duration,
        "file_size_bytes": file_size_bytes,
        "has_hdr": has_hdr,
    }


# ── Celery Task ────────────────────────────────────────────────────────────────

@celery_app.task(name="workers.ffprobe_worker.probe_file", bind=True, max_retries=3)
def probe_file(self, rel_path: str, abs_path: str):
    """
    Celery task: extract ffprobe metadata and store in MediaMetadata table.
    """
    import asyncio
    try:
        asyncio.run(_probe_and_store(rel_path, abs_path))
    except Exception as exc:
        logger.error(f"probe_file failed for {rel_path}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="workers.ffprobe_worker.probe_pending_files")
def probe_pending_files():
    """
    Celery beat task: find media files without metadata and probe them.
    """
    import asyncio
    asyncio.run(_probe_all_pending())


# ── Async helpers (used by FastAPI upload handler directly) ───────────────────

async def probe_file_async(rel_path: str, abs_path: str):
    """
    Async wrapper for direct use from FastAPI (runs ffprobe in threadpool).
    Does NOT block the event loop.
    """
    import asyncio
    await asyncio.to_thread(_probe_and_store_sync, rel_path, abs_path)


def _probe_and_store_sync(rel_path: str, abs_path: str):
    """Synchronous version for threadpool execution."""
    import asyncio
    asyncio.run(_probe_and_store(rel_path, abs_path))


async def _probe_and_store(rel_path: str, abs_path: str):
    """Core logic: probe + upsert MediaMetadata row."""
    from sqlalchemy import select
    from core.database import AsyncSessionFactory
    from db.models import MediaMetadata

    path = Path(abs_path)
    if not path.exists():
        logger.warning(f"File not found for probing: {abs_path}")
        return

    logger.info(f"🔍 Probing: {rel_path}")
    raw = _run_ffprobe(abs_path)
    if raw is None:
        logger.debug(f"ffprobe returned no data for {rel_path}")
        return

    meta = _parse_ffprobe_output(raw, path.stat().st_size)

    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path == rel_path)
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = MediaMetadata(rel_path=rel_path, **meta)
            db.add(row)
        else:
            for key, value in meta.items():
                setattr(row, key, value)

        await db.commit()
        logger.info(
            f"✅ Metadata stored: {rel_path} "
            f"[{meta.get('video_codec', '?')} {meta.get('width')}x{meta.get('height')} "
            f"{meta.get('duration_seconds', 0):.1f}s]"
        )


async def _probe_all_pending():
    """Find all media files missing metadata and dispatch probe tasks."""
    from sqlalchemy import select
    from core.database import AsyncSessionFactory
    from db.models import MediaMetadata
    from config import SHARED_FOLDER
    from file_manager import _get_file_type

    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}

    async with AsyncSessionFactory() as db:
        result = await db.execute(select(MediaMetadata.rel_path))
        indexed = {row[0] for row in result.fetchall()}

    for path in SHARED_FOLDER.rglob("*"):
        if path.suffix.lower() in VIDEO_EXTS and not path.name.startswith("."):
            rel = path.relative_to(SHARED_FOLDER).as_posix()
            if rel not in indexed:
                probe_file.delay(rel, str(path))
                logger.info(f"📤 Dispatched probe for: {rel}")
