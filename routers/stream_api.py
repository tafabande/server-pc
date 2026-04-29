"""
StreamDrop — Stream API Router
Handles media streaming: byte-range for raw files, HLS for transcoded content,
and live desktop/webcam streaming.

HLS-first routing: if a file has been transcoded (is_hls_ready=True),
the stream endpoint redirects to its HLS playlist for perfect scrubbing.
"""

import aiofiles
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SHARED_FOLDER, TRANSCODE_DIR
from core.database import get_db, MediaMetadata
from streaming import stream_manager
from auth.rbac import get_current_user, require_role, UserContext

router = APIRouter(prefix="/api/stream", tags=["Stream"])


# ── Live Streaming ─────────────────────────────────────────────────────────────

@router.get("/video")
def video_feed(user: UserContext = Depends(get_current_user)):
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")
    return StreamingResponse(
        stream_manager.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/audio")
def audio_feed(user: UserContext = Depends(get_current_user)):
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")
    return StreamingResponse(
        stream_manager.generate_audio(),
        media_type="audio/wav",
    )


@router.post("/start", dependencies=[Depends(require_role("admin", "family"))])
async def stream_start():
    stream_manager.start()
    return {"status": "ok", "mode": stream_manager.mode, "running": True, "quality": stream_manager.quality}


@router.post("/stop", dependencies=[Depends(require_role("admin", "family"))])
async def stream_stop():
    stream_manager.stop()
    return {"status": "ok", "running": False}


@router.post("/toggle", dependencies=[Depends(require_role("admin", "family"))])
async def stream_toggle():
    new_mode = stream_manager.toggle()
    return {"status": "ok", "mode": new_mode, "running": stream_manager.is_running}


# ── HLS Segments ──────────────────────────────────────────────────────────────

@router.get("/hls/{filename:path}/{segment:path}")
async def hls_stream(filename: str, segment: str):
    """Serve HLS playlists and .ts segments from the isolated TRANSCODE_DIR."""
    from core.workers import _get_hls_output_dir
    hls_dir = _get_hls_output_dir(filename)

    segment_path = (hls_dir / segment).resolve()

    # Ensure no path traversal outside TRANSCODE_DIR
    if not str(segment_path).startswith(str(TRANSCODE_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not segment_path.exists():
        raise HTTPException(status_code=404, detail="HLS segment not found")

    if segment.endswith(".m3u8"):
        return FileResponse(segment_path, media_type="application/vnd.apple.mpegurl")
    elif segment.endswith(".ts"):
        return FileResponse(segment_path, media_type="video/mp2t")
    else:
        raise HTTPException(status_code=400, detail="Invalid HLS segment type")


# ── Media Streaming (HLS-first, byte-range fallback) ─────────────────────────

@router.get("/media/{filename:path}")
async def stream_media(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Smart media streaming endpoint:
    1. Check if HLS transcode is ready → redirect to HLS playlist (perfect scrubbing).
    2. Otherwise → serve with byte-range streaming (good enough for most files).

    Note: /api/stream/media/* is in PUBLIC_PREFIXES so unauthenticated cast
    devices can still stream. RBAC is not enforced here by design.
    """
    filepath = (SHARED_FOLDER / filename).resolve()

    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Check for HLS-ready transcode
    try:
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path == filename)
        )
        meta = result.scalar_one_or_none()
        if meta and meta.is_hls_ready and meta.hls_path:
            playlist = Path(meta.hls_path)
            if playlist.exists():
                # Redirect to HLS playlist for perfect scrubbing
                hls_url = f"/api/stream/hls/{filename}/index.m3u8"
                return RedirectResponse(url=hls_url, status_code=302)
    except Exception:
        pass  # DB unavailable — fall through to byte-range

    # Byte-range streaming fallback
    file_size = filepath.stat().st_size
    range_header = request.headers.get("range")

    start = 0
    end = file_size - 1
    status_code = 200

    if range_header:
        import re
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
            status_code = 206

    if start >= file_size or end >= file_size or start > end:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024  # 1MB

    async def chunk_generator(file_path, start_byte, end_byte, chunk_sz):
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start_byte)
            bytes_left = end_byte - start_byte + 1
            while bytes_left > 0:
                read_size = min(chunk_sz, bytes_left)
                chunk = await f.read(read_size)
                if not chunk:
                    break
                yield chunk
                bytes_left -= len(chunk)

    content_type, _ = mimetypes.guess_type(filename)
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Type": content_type or "application/octet-stream",
    }

    # Track stream latency for Prometheus
    try:
        from core.main import STREAM_LATENCY
        import time
        _t = time.monotonic()
    except Exception:
        _t = None

    return StreamingResponse(
        chunk_generator(filepath, start, end, chunk_size),
        status_code=status_code,
        headers=headers,
    )
