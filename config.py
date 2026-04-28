"""
StreamDrop — Central Configuration
Loads settings from .env with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
SHARED_FOLDER = Path(
    os.getenv("SHARED_FOLDER", str(Path.home() / "StreamDrop" / "Shared"))
).expanduser().resolve()
STATIC_DIR = BASE_DIR / "static"

# ── Network ────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── Security ───────────────────────────────────────────
PIN = os.getenv("PIN", "1234")
SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))

# ── Streaming ──────────────────────────────────────────
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "75"))
STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", "1280"))
STREAM_HEIGHT = int(os.getenv("STREAM_HEIGHT", "720"))
STREAM_FPS = int(os.getenv("STREAM_FPS", "30"))

# ── Uploads ────────────────────────────────────────────
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico",
    # Videos
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
    # Audio
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".md", ".csv", ".json", ".xml",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # Code
    ".py", ".js", ".html", ".css", ".ts", ".java", ".cpp", ".c", ".h",
}

# ── Thumbnails ─────────────────────────────────────────
THUMB_SIZE = (200, 200)
THUMB_DIR = SHARED_FOLDER / ".thumbs"

# ── Service Discovery ─────────────────────────────────
SERVICE_NAME = os.getenv("SERVICE_NAME", "StreamDrop")
