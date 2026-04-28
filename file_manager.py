"""
StreamDrop — File Manager
Handles uploads, downloads, gallery listing, thumbnails, and deletion.
"""

import os
import re
import logging
import mimetypes
from pathlib import Path
from datetime import datetime
from PIL import Image
import cv2
import aiofiles
from fastapi import UploadFile
from config import SHARED_FOLDER, THUMB_DIR, LOG_DIR, THUMB_SIZE, ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

logger = logging.getLogger("streamdrop.files")

# Chunk size for reading uploads (1 MB)
CHUNK_SIZE = 1024 * 1024


def ensure_dirs():
    """Create shared, thumbnail, and log directories if they don't exist."""
    SHARED_FOLDER.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Shared folder: {SHARED_FOLDER}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and weird characters.
    Preserves the original extension.
    """
    # Strip directory components
    filename = Path(filename).name
    # Remove anything that's not alphanumeric, dash, underscore, dot, or space
    filename = re.sub(r'[^\w\-. ]', '_', filename)
    # Collapse multiple underscores/spaces
    filename = re.sub(r'[_ ]+', '_', filename).strip('_')
    # Ensure it's not empty
    if not filename or filename == '.':
        filename = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return filename


def _is_allowed(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def _get_file_type(filename: str) -> str:
    """Determine file type category from extension."""
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"}:
        return "image"
    elif ext in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}:
        return "video"
    elif ext in {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}:
        return "audio"
    elif ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}:
        return "document"
    elif ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "archive"
    elif ext in {".py", ".js", ".html", ".css", ".ts", ".java", ".cpp", ".c", ".h",
                 ".txt", ".md", ".csv", ".json", ".xml"}:
        return "text"
    else:
        return "other"


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _deduplicate_filename(filepath: Path) -> Path:
    """If file exists, append (1), (2), etc."""
    if not filepath.exists():
        return filepath
    stem = filepath.stem
    ext = filepath.suffix
    parent = filepath.parent
    counter = 1
    while True:
        new_path = parent / f"{stem}({counter}){ext}"
        if not new_path.exists():
            return new_path
        counter += 1


# ── Upload ──────────────────────────────────────────────


async def save_upload(file: UploadFile) -> dict:
    """
    Save an uploaded file to the shared folder using chunked writing.
    Returns file metadata dict.
    """
    filename = sanitize_filename(file.filename or "unnamed_file")

    if not _is_allowed(filename):
        raise ValueError(f"File type not allowed: {Path(filename).suffix}")

    filepath = _deduplicate_filename(SHARED_FOLDER / filename)
    total_written = 0

    async with aiofiles.open(filepath, "wb") as out_file:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_written += len(chunk)
            if total_written > MAX_UPLOAD_BYTES:
                # Clean up partial file
                await out_file.close()
                filepath.unlink(missing_ok=True)
                raise ValueError(
                    f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024*1024)} MB"
                )
            await out_file.write(chunk)

    logger.info(f"📥 Uploaded: {filepath.name} ({_format_size(total_written)})")

    # Generate thumbnail in background
    _generate_thumbnail(filepath)

    return _file_info(filepath)


# ── Gallery Listing ─────────────────────────────────────


def list_files() -> list[dict]:
    """List all files in the shared folder with metadata."""
    files = []
    for item in sorted(SHARED_FOLDER.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if item.is_file() and not item.name.startswith('.'):
            files.append(_file_info(item))
    return files


def _file_info(filepath: Path) -> dict:
    """Build metadata dict for a file."""
    stat = filepath.stat()
    file_type = _get_file_type(filepath.name)
    mime, _ = mimetypes.guess_type(filepath.name)

    info = {
        "name": filepath.name,
        "size": stat.st_size,
        "size_formatted": _format_size(stat.st_size),
        "type": file_type,
        "mime": mime or "application/octet-stream",
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "download_url": f"/api/download/{filepath.name}",
        "serve_url": f"/shared/{filepath.name}",
        "playable": file_type in {"video", "audio"},
        "stream_url": f"/api/stream/media/{filepath.name}" if file_type in {"video", "audio"} else None,
    }

    # Add thumbnail URL if available
    thumb_path = THUMB_DIR / f"{filepath.stem}_thumb.jpg"
    if thumb_path.exists():
        info["thumbnail_url"] = f"/shared/.thumbs/{filepath.stem}_thumb.jpg"
    elif file_type == "image":
        info["thumbnail_url"] = info["serve_url"]

    return info


# ── Thumbnails ──────────────────────────────────────────


def _generate_thumbnail(filepath: Path):
    """Generate a thumbnail for images and videos."""
    try:
        file_type = _get_file_type(filepath.name)
        thumb_path = THUMB_DIR / f"{filepath.stem}_thumb.jpg"

        if file_type == "image":
            with Image.open(filepath) as img:
                img.thumbnail(THUMB_SIZE)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=70)

        elif file_type == "video":
            cap = cv2.VideoCapture(str(filepath))
            ret, frame = cap.read()
            cap.release()
            if ret:
                # Resize to thumbnail
                h, w = frame.shape[:2]
                scale = min(THUMB_SIZE[0] / w, THUMB_SIZE[1] / h)
                new_w, new_h = int(w * scale), int(h * scale)
                thumb = cv2.resize(frame, (new_w, new_h))
                cv2.imwrite(str(thumb_path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])

    except Exception as e:
        logger.warning(f"Thumbnail generation failed for {filepath.name}: {e}")


# ── Deletion ────────────────────────────────────────────


def delete_file(filename: str) -> bool:
    """
    Safely delete a file from the shared folder.
    Returns True if deleted, raises ValueError on path traversal.
    """
    filename = sanitize_filename(filename)
    filepath = (SHARED_FOLDER / filename).resolve()

    # Path traversal check
    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise ValueError("Invalid file path")

    if not filepath.exists():
        return False

    filepath.unlink()

    # Also remove thumbnail
    thumb_path = THUMB_DIR / f"{filepath.stem}_thumb.jpg"
    thumb_path.unlink(missing_ok=True)

    logger.info(f"🗑️ Deleted: {filename}")
    return True
