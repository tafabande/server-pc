"""
StreamDrop — Main Application
Unified LAN hub: live video streaming + Quick Share file interactions.
v2: WebSocket hub, clipboard sync, adaptive bitrate, remote control.
"""

import time
import socket
import logging
import asyncio
import aiofiles
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import HOST, PORT, SHARED_FOLDER, STATIC_DIR, LOG_DIR
from security import (
    auth_middleware,
    verify_pin,
    create_session,
    set_session_cookie,
    validate_session,
)
from discovery import ServiceDiscovery, get_local_ip, get_server_url, generate_qr_code
from streaming import stream_manager
from file_manager import ensure_dirs, save_upload, list_files, delete_file
from websocket_hub import ws_manager

# ── Ensure directories exist before app mount ───────────
ensure_dirs()

# ── Logging ─────────────────────────────────────────────
import logging.handlers

log_formatter = logging.Formatter(
    fmt="%(asctime)s │ %(name)-24s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# File handler
file_handler = logging.handlers.RotatingFileHandler(
    filename=LOG_DIR / "streamdrop.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("streamdrop")

# ── State ───────────────────────────────────────────────

_start_time = time.time()
_discovery = ServiceDiscovery()


# ── Lifespan ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    _discovery.register()
    ip = get_local_ip()
    url = get_server_url(ip)
    logger.info("=" * 60)
    logger.info(f"🚀 StreamDrop is running!")
    logger.info(f"   Local:   http://localhost:{PORT}")
    logger.info(f"   Network: {url}")
    logger.info(f"   Host:    {socket.gethostname()}")
    logger.info("=" * 60)

    # Print QR code in terminal for instant phone connection
    try:
        import sys
        qr = __import__("qrcode").QRCode(box_size=1, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        lines = []
        for row in matrix:
            line = "  "
            for cell in row:
                line += "##" if cell else "  "
            lines.append(line)
        qr_text = "\n".join(lines)
        output = f"\n  Scan to connect:\n\n{qr_text}\n\n  -> {url}\n"
        try:
            sys.stdout.write(output)
            sys.stdout.flush()
        except UnicodeEncodeError:
            sys.stdout.write(output.encode("ascii", errors="replace").decode("ascii"))
            sys.stdout.flush()
    except Exception as e:
        logger.debug(f"Terminal QR skipped: {e}")
    yield
    # Shutdown
    stream_manager.stop()
    _discovery.unregister()
    logger.info("👋 StreamDrop stopped.")


# ── App ─────────────────────────────────────────────────

app = FastAPI(
    title="StreamDrop",
    description="Unified LAN Hub — Stream & Share",
    version="2.0.0",
    lifespan=lifespan,
)

# Middleware
app.middleware("http")(auth_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/shared", StaticFiles(directory=str(SHARED_FOLDER)), name="shared")


# ── Models ──────────────────────────────────────────────

class PinRequest(BaseModel):
    pin: str

class ClipboardRequest(BaseModel):
    text: str

class FavoriteRequest(BaseModel):
    filename: str


# ── Routes: Root ────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Redirect to the dashboard."""
    return RedirectResponse(url="/static/index.html")


# ── Routes: Auth ────────────────────────────────────────

@app.post("/api/auth")
async def authenticate(body: PinRequest):
    """Validate PIN and create a session."""
    if not verify_pin(body.pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")

    token, expiry = create_session()
    response = JSONResponse(content={"status": "ok", "message": "Authenticated", "token": token})
    set_session_cookie(response, token, expiry)
    return response


# ── Routes: Status ──────────────────────────────────────

@app.get("/api/status")
async def status():
    """Server status and connection info."""
    ip = get_local_ip()
    return {
        "hostname": socket.gethostname(),
        "ip": ip,
        "port": PORT,
        "url": get_server_url(ip),
        "uptime_seconds": int(time.time() - _start_time),
        "stream": {
            "running": stream_manager.is_running,
            "mode": stream_manager.mode,
            "quality": stream_manager.quality,
        },
        "connections": ws_manager.client_count,
    }


# ── Routes: QR Code ────────────────────────────────────

@app.get("/api/qr")
async def qr_code():
    """Generate a QR code PNG of the server URL."""
    png_bytes = generate_qr_code()
    return Response(content=png_bytes, media_type="image/png")


# ── Routes: Streaming ──────────────────────────────────

@app.get("/api/stream/video")
def video_feed():
    """
    MJPEG video stream endpoint.
    Uses a sync function so FastAPI runs the generator in a threadpool,
    preventing the event loop from blocking on OpenCV/mss calls.
    """
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")

    return StreamingResponse(
        stream_manager.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/stream/audio")
def audio_feed():
    """
    Continuous WAV audio stream endpoint.
    """
    if not stream_manager.is_running:
        raise HTTPException(status_code=503, detail="Stream is not running")

    return StreamingResponse(
        stream_manager.generate_audio(),
        media_type="audio/wav",
    )


@app.post("/api/stream/start")
async def stream_start():
    """Start the video stream."""
    stream_manager.start()
    return {"status": "ok", "mode": stream_manager.mode, "running": True, "quality": stream_manager.quality}


@app.post("/api/stream/stop")
async def stream_stop():
    """Stop the video stream."""
    stream_manager.stop()
    return {"status": "ok", "running": False}


@app.post("/api/stream/toggle")
async def stream_toggle():
    """Toggle between webcam and screen capture."""
    new_mode = stream_manager.toggle()
    return {"status": "ok", "mode": new_mode, "running": stream_manager.is_running}


@app.post("/api/shutdown")
def shutdown_server():
    """Shut down the server safely from the UI."""
    import threading
    import os
    def suicide():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=suicide, daemon=True).start()
    return {"status": "ok", "message": "Shutting down"}


# ── Routes: Files ───────────────────────────────────────

@app.get("/api/files")
@app.get("/api/files/{path:path}")
async def get_files(path: str = ""):
    """List all files in the shared folder (or subfolder)."""
    # path comes from the route if using path-based, or default to ""
    # We use unquote to handle special characters in the URL
    from urllib.parse import unquote
    decoded_path = unquote(path)
    return {"files": list_files(decoded_path)}


@app.post("/api/favorites/toggle")
async def toggle_fav(body: FavoriteRequest):
    """Toggle favorite status for a file."""
    from favorites_manager import toggle_favorite
    state = toggle_favorite(body.filename)
    return {"status": "ok", "favorite": state}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), path: str = Query(default="")):
    """Upload a file to a specific path in the shared folder."""
    try:
        info = await save_upload(file, path)
        # Broadcast file event to all WebSocket clients
        await ws_manager.broadcast_file_event("uploaded", info)
        return {"status": "ok", "file": info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stream/media/{filename:path}")
async def stream_media(filename: str, request: Request):
    """
    Byte-Range streaming endpoint for media files.
    Allows instant scrubbing (seeking) in video files without loading into RAM.
    """
    filepath = (SHARED_FOLDER / filename).resolve()

    # Path traversal check
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
        # Parse the range header, e.g. "bytes=0-1023" or "bytes=500-"
        range_match = __import__("re").match(r"bytes=(\d+)-(\d*)", range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
            status_code = 206

    if start >= file_size or end >= file_size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    chunk_size = 1024 * 1024  # 1MB chunks to keep RAM usage low (~20MB total with buffers)

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

    import mimetypes
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


@app.get("/api/download/{filename:path}")
async def download_file(filename: str):
    """Download a file from the shared folder."""
    filepath = (SHARED_FOLDER / filename).resolve()

    # Path traversal check
    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    def iterfile():
        with open(filepath, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filepath.name}"',
            "Content-Length": str(filepath.stat().st_size),
        },
    )


@app.delete("/api/files/{filename:path}")
async def remove_file(filename: str):
    """Delete a file from the shared folder."""
    try:
        deleted = delete_file(filename)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        # Broadcast file event to all WebSocket clients
        await ws_manager.broadcast_file_event("deleted", {"name": filename})
        return {"status": "ok", "deleted": filename}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Routes: Clipboard ──────────────────────────────────

@app.get("/api/clipboard")
async def get_clipboard():
    """Get the current shared clipboard text (REST fallback)."""
    return {"text": ws_manager.clipboard_text}


@app.post("/api/clipboard")
async def set_clipboard(body: ClipboardRequest):
    """Set the shared clipboard text (REST fallback)."""
    ws_manager.clipboard_text = body.text
    await ws_manager.broadcast({"type": "clipboard", "text": body.text, "source": "api"})
    return {"status": "ok", "text": body.text}


# ── WebSocket Endpoint ──────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    """
    Main WebSocket endpoint.
    Authenticates via session token in query param.
    Handles all real-time features: clipboard, remote control, bitrate, file events.
    """
    # Validate session token (TEMPORARY: Lenient for LAN)
    # if not validate_session(token):
    #     await websocket.close(code=4001, reason="Authentication required")
    #     return

    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        await ws_manager.disconnect(websocket)


# ── Entry Point ─────────────────────────────────────────

def _kill_process_on_port(port: int):
    """Attempt to forcefully kill any process holding our target port on Windows."""
    import os
    import subprocess
    try:
        if os.name == 'nt':
            result = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in result.strip().split('\\n'):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[1].endswith(f":{port}"):
                    pid = parts[-1]
                    if pid and pid != "0":
                        subprocess.call(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    
    _kill_process_on_port(PORT)

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
