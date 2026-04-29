import aiofiles
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from pathlib import Path
from config import SHARED_FOLDER
from streaming import stream_manager
import mimetypes

router = APIRouter(prefix="/api/stream", tags=["Stream"])

@router.get("/video")
def video_feed():
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")
    return StreamingResponse(
        stream_manager.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@router.get("/audio")
def audio_feed():
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")
    return StreamingResponse(
        stream_manager.generate_audio(),
        media_type="audio/wav",
    )

@router.post("/start")
async def stream_start():
    stream_manager.start()
    return {"status": "ok", "mode": stream_manager.mode, "running": True, "quality": stream_manager.quality}

@router.post("/stop")
async def stream_stop():
    stream_manager.stop()
    return {"status": "ok", "running": False}

@router.post("/toggle")
async def stream_toggle():
    new_mode = stream_manager.toggle()
    return {"status": "ok", "mode": new_mode, "running": stream_manager.is_running}

@router.get("/hls/{filename:path}/{segment:path}")
async def hls_stream(filename: str, segment: str):
    """Serve HLS playlists and segments."""
    hls_dir = (SHARED_FOLDER / f"{filename}.hls").resolve()
    
    if not str(hls_dir).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
        
    segment_path = hls_dir / segment
    if not segment_path.exists():
        raise HTTPException(status_code=404, detail="HLS segment not found")
        
    if segment.endswith(".m3u8"):
        return FileResponse(segment_path, media_type="application/vnd.apple.mpegurl")
    elif segment.endswith(".ts"):
        return FileResponse(segment_path, media_type="video/mp2t")
    else:
        raise HTTPException(status_code=400, detail="Invalid HLS segment")

@router.get("/media/{filename:path}")
async def stream_media(filename: str, request: Request):
    """Byte-Range streaming endpoint for media files."""
    filepath = (SHARED_FOLDER / filename).resolve()

    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

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
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    chunk_size = 1024 * 1024  # 1MB chunks

    async def chunk_generator(file_path, start_byte, end_byte, chunk_size):
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start_byte)
            bytes_left = end_byte - start_byte + 1
            while bytes_left > 0:
                read_size = min(chunk_size, bytes_left)
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

    return StreamingResponse(
        chunk_generator(filepath, start, end, chunk_size),
        status_code=status_code,
        headers=headers,
    )
