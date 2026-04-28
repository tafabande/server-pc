"""
StreamDrop — Main Application
Unified LAN hub: live video streaming + Quick Share file interactions.
"""

import time
import socket
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import HOST, PORT, SHARED_FOLDER, STATIC_DIR
from security import (
    auth_middleware,
    verify_pin,
    create_session,
    set_session_cookie,
)
from discovery import ServiceDiscovery, get_local_ip, get_server_url, generate_qr_code
from streaming import stream_manager
from file_manager import ensure_dirs, save_upload, list_files, delete_file

# ── Logging ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-24s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("streamdrop")

# ── Ensure directories exist before app mount ───────────
ensure_dirs()

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
    yield
    # Shutdown
    stream_manager.stop()
    _discovery.unregister()
    logger.info("👋 StreamDrop stopped.")


# ── App ─────────────────────────────────────────────────

app = FastAPI(
    title="StreamDrop",
    description="Unified LAN Hub — Stream & Share",
    version="1.0.0",
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
    response = JSONResponse(content={"status": "ok", "message": "Authenticated"})
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
        },
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


@app.post("/api/stream/start")
async def stream_start():
    """Start the video stream."""
    stream_manager.start()
    return {"status": "ok", "mode": stream_manager.mode, "running": True}


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


# ── Routes: Files ───────────────────────────────────────

@app.get("/api/files")
async def get_files():
    """List all files in the shared folder."""
    return {"files": list_files()}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to the shared folder."""
    try:
        info = await save_upload(file)
        return {"status": "ok", "file": info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        return {"status": "ok", "deleted": filename}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
