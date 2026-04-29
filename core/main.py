import time
import socket
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Adjust import paths for the root level config and discovery, or assume we run from project root
import sys
from pathlib import Path
# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import HOST, PORT, SHARED_FOLDER, STATIC_DIR, LOG_DIR
from security import auth_middleware, verify_pin, create_session, set_session_cookie
from discovery import ServiceDiscovery, get_local_ip, get_server_url, generate_qr_code

# Routers
from routers.stream_api import router as stream_router
from routers.file_api import router as file_router
from routers.doc_api import router as doc_router

# Core & Workers
from core.websockets import ws_manager
from workers.compression import start_worker as start_compression_worker
from streaming import stream_manager

import logging.handlers

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
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("streamdrop")

_start_time = time.time()
_discovery = ServiceDiscovery()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _discovery.register()
    
    # Start background workers
    start_compression_worker()
    
    ip = get_local_ip()
    url = get_server_url(ip)
    logger.info("=" * 60)
    logger.info(f"🚀 StreamDrop is running (Modular Architecture)!")
    logger.info(f"   Local:   http://localhost:{PORT}")
    logger.info(f"   Network: {url}")
    logger.info("=" * 60)

    yield
    
    # Shutdown
    stream_manager.stop()
    _discovery.unregister()
    logger.info("👋 StreamDrop stopped.")

app = FastAPI(
    title="StreamDrop",
    description="Unified LAN Hub — Stream & Share",
    version="3.0.0",
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

# Mounts
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/shared", StaticFiles(directory=str(SHARED_FOLDER)), name="shared")

# Include Routers
app.include_router(stream_router)
app.include_router(file_router)
app.include_router(doc_router)

# Root / Frontend
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/manifest.json", include_in_schema=False)
async def get_manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
async def get_sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")

# Auth
from pydantic import BaseModel
class PinRequest(BaseModel):
    pin: str

@app.post("/api/auth")
async def authenticate(body: PinRequest):
    if not verify_pin(body.pin):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid PIN")
    token, expiry = create_session()
    response = JSONResponse(content={"status": "ok", "message": "Authenticated", "token": token})
    set_session_cookie(response, token, expiry)
    return response

# Status
@app.get("/api/status")
async def status():
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

@app.get("/api/qr")
async def qr_code():
    png_bytes = generate_qr_code()
    return Response(content=png_bytes, media_type="image/png")

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
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

# Clipboard Endpoints
class ClipboardRequest(BaseModel):
    text: str

@app.get("/api/clipboard")
async def get_clipboard():
    return {"text": ws_manager.clipboard_text}

@app.post("/api/clipboard")
async def set_clipboard(body: ClipboardRequest):
    ws_manager.clipboard_text = body.text
    await ws_manager.broadcast({"type": "clipboard", "text": body.text, "source": "api"})
    return {"status": "ok", "text": body.text}

@app.post("/api/shutdown")
def shutdown_server():
    import threading, os
    logger.info("🛑 Shutdown requested from UI.")
    def suicide():
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=suicide, daemon=True).start()
    return {"status": "ok", "message": "Shutting down"}

def _kill_process_on_port(port: int):
    import os, subprocess
    try:
        if os.name == 'nt':
            result = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in result.strip().split('\n'):
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
        "core.main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=True,
    )
