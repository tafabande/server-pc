"""
StreamDrop — Core Background Workers
Handles long-running tasks like FFmpeg transcoding and HLS segmenting
using asyncio.to_thread to keep the event loop unblocked.
"""

import asyncio
import logging
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select

from config import TRANSCODE_DIR, SHARED_FOLDER
from core.database import AsyncSessionFactory, MediaMetadata

logger = logging.getLogger("streamdrop.workers")

def _get_hls_output_dir(rel_path: str) -> Path:
    """Deterministic output directory for HLS files."""
    path_hash = hashlib.md5(rel_path.encode()).hexdigest()
    return TRANSCODE_DIR / path_hash

def _run_ffmpeg_hls(input_path: str, output_dir: Path):
    """
    Synchronous FFmpeg execution. 
    Intended to be run in a separate thread via asyncio.to_thread.
    """
    playlist_path = output_dir / "index.m3u8"
    segment_pattern = output_dir / "seg%04d.ts"
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-f", "hls", "-hls_time", "2", "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(segment_pattern),
        str(playlist_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg HLS failed: {e.stderr}")
        raise

async def transcode_to_hls(rel_path: str):
    """
    Async wrapper for HLS transcoding.
    Checks DB state, runs FFmpeg in thread, and updates metadata.
    """
    abs_path = (SHARED_FOLDER / rel_path).resolve()
    if not abs_path.exists():
        logger.error(f"File not found for transcoding: {rel_path}")
        return

    # 1. Check if already done
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(MediaMetadata).where(MediaMetadata.rel_path == rel_path))
        meta = result.scalar_one_or_none()
        if meta and meta.is_hls_ready:
            if Path(meta.hls_path).exists():
                return

    # 2. Prepare output
    output_dir = _get_hls_output_dir(rel_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Execute FFmpeg in thread
    logger.info(f"🎬 Starting HLS Transcode: {rel_path}")
    try:
        await asyncio.to_thread(_run_ffmpeg_hls, str(abs_path), output_dir)
    except Exception as e:
        logger.error(f"Transcode failed: {e}")
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        return

    # 4. Update Database
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(MediaMetadata).where(MediaMetadata.rel_path == rel_path))
        meta = result.scalar_one_or_none()
        if not meta:
            meta = MediaMetadata(rel_path=rel_path)
            db.add(meta)
        
        meta.is_hls_ready = True
        meta.hls_path = str(output_dir / "index.m3u8")
        meta.transcoded_at = datetime.now(timezone.utc)
        await db.commit()
    
    logger.info(f"✅ HLS Ready: {rel_path}")
