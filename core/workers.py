"""
StreamDrop — Core Background Workers
Handles long-running tasks like FFmpeg transcoding and HLS segmenting
using asyncio.to_thread to keep the event loop unblocked.
"""

import asyncio
import logging
import subprocess
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache
from sqlalchemy import select

from config import TRANSCODE_DIR, SHARED_FOLDER
from core.database import AsyncSessionFactory, MediaMetadata

logger = logging.getLogger("streamdrop.workers")

# ── Hardware Acceleration Detection ───────────────────────────────────────────

@lru_cache(maxsize=1)
def detect_hardware_acceleration() -> list[str]:
    """Detect available hardware acceleration and return FFmpeg flags."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hwaccels"],
            capture_output=True,
            text=True,
            timeout=5
        )

        hwaccels = result.stdout.lower()

        # Priority order: NVENC (NVIDIA) > QSV (Intel) > VAAPI (Linux) > None
        if "cuda" in hwaccels:
            logger.info("✓ NVIDIA NVENC hardware acceleration detected")
            return ["-hwaccel", "cuda", "-c:v", "h264_nvenc", "-preset", "p4"]
        elif "qsv" in hwaccels:
            logger.info("✓ Intel QSV hardware acceleration detected")
            return ["-hwaccel", "qsv", "-c:v", "h264_qsv", "-preset", "fast"]
        elif "vaapi" in hwaccels:
            logger.info("✓ VAAPI hardware acceleration detected")
            return ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]
        else:
            logger.info("ℹ No hardware acceleration available, using software encoding")
            return []

    except Exception as e:
        logger.warning(f"Failed to detect hardware acceleration: {e}")
        return []

def _get_hls_output_dir(rel_path: str) -> Path:
    """Deterministic output directory for HLS files."""
    path_hash = hashlib.md5(rel_path.encode()).hexdigest()
    return TRANSCODE_DIR / path_hash

def _run_ffmpeg_hls(input_path: str, output_dir: Path):
    """
    Synchronous FFmpeg execution with hardware acceleration.
    Intended to be run in a separate thread via asyncio.to_thread.
    """
    playlist_path = output_dir / "index.m3u8"
    segment_pattern = output_dir / "seg%04d.ts"

    # Detect hardware acceleration (cached)
    hwaccel_flags = detect_hardware_acceleration()

    # Adaptive CRF based on source quality
    crf = 23  # Default
    try:
        probe_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-of", "json", input_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        probe_data = json.loads(probe_result.stdout)
        source_bitrate = int(probe_data.get("format", {}).get("bit_rate", 5000000))

        # Higher CRF for lower bitrate sources (more compression)
        crf = 28 if source_bitrate < 2_000_000 else 23
    except Exception as e:
        logger.debug(f"Could not probe source bitrate: {e}")

    # Build FFmpeg command
    base_cmd = ["ffmpeg", "-y"]

    if hwaccel_flags:
        base_cmd.extend(hwaccel_flags[:2])  # Add hwaccel flags but not codec yet

    cmd = [
        *base_cmd,
        "-i", input_path,
    ]

    # Add video codec flags
    if hwaccel_flags and len(hwaccel_flags) > 2:
        # Hardware encoding
        cmd.extend(hwaccel_flags[2:])  # Add codec flags
    else:
        # Software encoding
        cmd.extend(["-c:v", "libx264", "-preset", "faster", "-crf", str(crf)])

    # Common flags
    cmd.extend([
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(segment_pattern),
        str(playlist_path)
    ])

    logger.info(f"🎬 Starting HLS transcode: {Path(input_path).name}")
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"✓ HLS transcode complete: {Path(input_path).name}")
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
