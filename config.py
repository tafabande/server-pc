"""
StreamDrop — Central Configuration
Loads settings from .env with sensible defaults.
Supports both normal Python and PyInstaller frozen (.exe) mode.
"""

import os
import sys
import secrets
from pathlib import Path
from dotenv import load_dotenv

# When frozen (exe), use the exe's directory; otherwise use script dir
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Load .env from the same folder as the exe/script
load_dotenv(BASE_DIR / ".env")

# ── Paths ──────────────────────────────────────────────
SHARED_FOLDER = Path(
    os.getenv("SHARED_FOLDER", os.getcwd())
).expanduser().resolve()
LOG_DIR = SHARED_FOLDER / ".logs"

# HLS / transcode cache — kept SEPARATE from media root so
# SHARED_FOLDER can be mounted read-only in Docker.
# Wiping this dir clears all HLS caches without touching source media.
TRANSCODE_DIR = Path(
    os.getenv("TRANSCODE_DIR", str(BASE_DIR / ".cache" / "transcodes"))
).expanduser().resolve()

# Static files: bundled inside the exe via PyInstaller _MEIPASS
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = Path(sys._MEIPASS)
    STATIC_DIR = _BUNDLE_DIR / "static"
else:
    STATIC_DIR = BASE_DIR / "static"

# ── Network ────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── Authentication ─────────────────────────────────────
# Legacy PIN (kept for backwards-compat during transition)
PIN = os.getenv("PIN", "1234")

# Admin credentials — used to seed the first admin user on startup
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

# JWT signing secret — auto-generate a strong one if not set in .env
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(64))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

SESSION_EXPIRY_HOURS = JWT_EXPIRE_HOURS  # alias for legacy code

# RBAC path restriction for guest role
# Guests are confined to this subpath of SHARED_FOLDER (default: no restriction)
GUEST_ROOT_PATH = os.getenv("GUEST_ROOT_PATH", "")

# ── Database ───────────────────────────────────────────
# Default: async SQLite for local dev. Override with PostgreSQL DSN for prod.
# Example: postgresql+asyncpg://user:pass@postgres:5432/streamdrop
_DATA_DIR = SHARED_FOLDER / ".data"
_DATA_DIR.mkdir(exist_ok=True, parents=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{_DATA_DIR / 'streamdrop.db'}"
)

# ── Redis ──────────────────────────────────────────────
# Used for multi-instance session sync and Celery broker/backend.
# Falls back to in-memory dict if Redis is unreachable (dev mode).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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
THUMB_DIR = SHARED_FOLDER / "thumbs"

# ── Service Discovery ─────────────────────────────────
SERVICE_NAME = os.getenv("SERVICE_NAME", "StreamDrop")
