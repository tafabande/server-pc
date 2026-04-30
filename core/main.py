"""
StreamDrop — Main Application Entry Point
Enterprise Edition: JWT auth, RBAC, SQLAlchemy, Prometheus metrics.

Startup sequence:
  1. Initialize DB tables (CREATE IF NOT EXISTS).
  2. Seed admin user from .env if no users exist.
  3. Start background workers (Celery health check).
  4. Register service via mDNS.
  5. Expose Prometheus metrics endpoint.
"""

import time
import socket
import logging
import logging.handlers
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST


from config import HOST, PORT, SHARED_FOLDER, STATIC_DIR, LOG_DIR, TRANSCODE_DIR
from core.security import auth_middleware
from core.discovery import ServiceDiscovery, get_local_ip, get_server_url, generate_qr_code

# Routers
from routers.stream_api import router as stream_router
from routers.file_api import router as file_router
from routers.doc_api import router as doc_router
from routers.auth_api import router as auth_router
from routers.media_api import router as media_router

# Core & Workers
from core.socket_manager import manager
from core.workers import transcode_to_hls
from core.streaming import stream_manager

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRANSCODE_DIR.mkdir(parents=True, exist_ok=True)

log_formatter = logging.Formatter(
    fmt="%(asctime)s │ %(name)-24s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

file_handler = logging.handlers.RotatingFileHandler(
    filename=LOG_DIR / "streamdrop.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("streamdrop")

# ── Prometheus Metrics ─────────────────────────────────────────────────────────
ACTIVE_CONNECTIONS = Gauge(
    "streamdrop_active_ws_connections",
    "Number of active WebSocket connections",
)
PLAY_EVENTS_COUNTER = Counter(
    "streamdrop_play_events_total",
    "Total play events fired",
    ["event_type"],
)
UPLOAD_BYTES_COUNTER = Counter(
    "streamdrop_upload_bytes_total",
    "Total bytes uploaded",
)
STREAM_LATENCY = Histogram(
    "streamdrop_stream_latency_seconds",
    "Byte-range stream request latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
HTTP_REQUESTS = Counter(
    "streamdrop_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# ── Startup State ──────────────────────────────────────────────────────────────
_start_time = time.time()
_discovery = ServiceDiscovery()


# (Seeding logic moved to core.database.bootstrap_system)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from core.database import bootstrap_system
    await bootstrap_system()

    _discovery.register()
    # start_compression_worker() # Disabled in favor of core.workers

    ip = get_local_ip()
    url = get_server_url(ip)
    logger.info("=" * 60)
    logger.info("🚀 StreamDrop Enterprise Edition!")
    logger.info(f"   Local:   http://localhost:{PORT}")
    logger.info(f"   Network: {url}")
    logger.info(f"   Metrics: http://localhost:{PORT}/metrics")
    logger.info("=" * 60)

    yield

    # Shutdown
    stream_manager.stop()
    _discovery.unregister()
    logger.info("👋 StreamDrop stopped.")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="StreamDrop",
    description="Enterprise LAN Media Hub — Stream, Share & Collaborate",
    version="4.0.0",
    lifespan=lifespan,
)

# Middleware (order matters: auth runs before CORS)
app.middleware("http")(auth_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file mounts
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# SHARED_FOLDER mounted for direct file serving (legacy /shared/ URLs)
# In Docker, this volume is read-only — the mount remains functional for GET.
app.mount("/shared", StaticFiles(directory=str(SHARED_FOLDER)), name="shared")

# Routers
app.include_router(auth_router)
app.include_router(stream_router)
app.include_router(file_router)
app.include_router(doc_router)
app.include_router(media_router)


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json", include_in_schema=False)
async def get_manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
async def get_sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


# ── Status & QR ────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def status():
    ip = get_local_ip()
    return {
        "hostname": socket.gethostname(),
        "ip": ip,
        "port": PORT,
        "url": get_server_url(ip),
        "uptime_seconds": int(time.time() - _start_time),
        "version": "4.0.0",
        "stream": {
            "running": stream_manager.is_running,
            "mode": stream_manager.mode,
            "quality": stream_manager.quality,
        },
        "connections": manager.client_count,
    }


@app.get("/api/qr")
async def qr_code():
    png_bytes = generate_qr_code()
    return Response(content=png_bytes, media_type="image/png")


# ── Prometheus Metrics Endpoint ────────────────────────────────────────────────

@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape endpoint. Listed in PUBLIC_PREFIXES so no auth needed."""
    # Update live gauges
    ACTIVE_CONNECTIONS.set(manager.client_count)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    try:
        await manager.connect(websocket)
        ACTIVE_CONNECTIONS.set(manager.client_count)
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        ACTIVE_CONNECTIONS.set(manager.client_count)
    except Exception:
        await manager.disconnect(websocket)
        ACTIVE_CONNECTIONS.set(manager.client_count)


# ── Clipboard ──────────────────────────────────────────────────────────────────

from pydantic import BaseModel


class ClipboardRequest(BaseModel):
    text: str


@app.get("/api/clipboard")
async def get_clipboard():
    return {"text": manager.clipboard_text}


@app.post("/api/clipboard")
async def set_clipboard(body: ClipboardRequest):
    manager.clipboard_text = body.text
    await manager.broadcast({"type": "clipboard", "text": body.text, "source": "api"})
    return {"status": "ok", "text": body.text}


# ── Shutdown ───────────────────────────────────────────────────────────────────

@app.post("/api/shutdown")
def shutdown_server():
    from auth.rbac import get_current_user
    import threading, os
    logger.info("🛑 Shutdown requested from UI.")

    def suicide():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=suicide, daemon=True).start()
    return {"status": "ok", "message": "Shutting down"}

