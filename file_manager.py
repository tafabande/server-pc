"""
StreamDrop — File Manager
Handles uploads, downloads, gallery listing, thumbnails, and deletion.
"""

import os
import re
import logging
import mimetypes
import hashlib
import shutil
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
SUBTITLE_EXTENSIONS = {".vtt", ".srt"}


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


async def save_upload(file: UploadFile, subpath: str = "") -> dict:
    """
    Save an uploaded file to a specific subfolder.
    Returns file metadata dict.
    """
    filename = sanitize_filename(file.filename or "unnamed_file")

    if not _is_allowed(filename):
        raise ValueError(f"File type not allowed: {Path(filename).suffix}")

    target_dir = (SHARED_FOLDER / subpath).resolve()
    # Path traversal protection
    if not str(target_dir).startswith(str(SHARED_FOLDER)):
        target_dir = SHARED_FOLDER
    
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = _deduplicate_filename(target_dir / filename)
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

    # No longer generating thumbnails in background here
    # get_thumbnail API will handle it on-demand

    return _file_info(filepath)


# ── Gallery Listing ─────────────────────────────────────


def list_files(subpath: str = "") -> list[dict]:
    """List files and folders in a specific subpath of the shared folder."""
    # Clean the path to prevent absolute path escapes or traversal
    subpath = subpath.lstrip("/\\")
    target_dir = (SHARED_FOLDER / subpath).resolve()
    
    logger.info(f"Listing files in: {target_dir} (subpath: '{subpath}')")

    # Path traversal protection
    if not str(target_dir).startswith(str(SHARED_FOLDER)):
        logger.warning(f"Path traversal attempt blocked: {target_dir}")
        target_dir = SHARED_FOLDER
        subpath = ""

    items = []
    if not target_dir.exists():
        logger.error(f"Directory not found: {target_dir}")
        return []
    
    if not target_dir.is_dir():
        logger.error(f"Not a directory: {target_dir}")
        return []

    try:
        from favorites_manager import load_favorites
        favorites = load_favorites()

        with os.scandir(target_dir) as it:
            # Sort: Directories first, then by modification time
            entries = list(it)
            logger.info(f"Found {len(entries)} entries in {target_dir}")
            entries.sort(key=lambda e: (not e.is_dir(), -e.stat().st_mtime))
            
            for entry in entries:
                # Skip hidden files and system folders
                if entry.name.startswith('.') or entry.name in {".cache", ".logs", "thumbs"}:
                    continue
                
                rel_path = Path(entry.path).relative_to(SHARED_FOLDER).as_posix()
                
                if entry.is_dir():
                    items.append({
                        "name": entry.name,
                        "filename": rel_path, # Full relative path
                        "type": "folder",
                        "size": 0,
                        "size_formatted": "Folder",
                        "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                        "is_dir": True,
                        "is_favorite": rel_path in favorites
                    })
                else:
                    info = _file_info(Path(entry.path), favorites=favorites)
                    items.append(info)
                        
    except Exception as e:
        logger.error(f"Failed to list files in {subpath}: {e}")
    
    return items


def _file_info(filepath: Path, favorites: list[str] = None) -> dict:
    """Build metadata dict for a file."""
    # Get path relative to SHARED_FOLDER for internal tracking
    rel_path = filepath.relative_to(SHARED_FOLDER).as_posix()
    stat = filepath.stat()
    file_type = _get_file_type(filepath.name)
    mime, _ = mimetypes.guess_type(filepath.name)
    
    # Check favorite status
    if favorites is None:
        from favorites_manager import load_favorites
        favorites = load_favorites()
    
    is_favorite = rel_path in favorites

    info = {
        "name": filepath.name,
        "filename": rel_path,  # Full relative path for API calls
        "size": stat.st_size,
        "size_formatted": _format_size(stat.st_size),
        "type": file_type,
        "mime": mime or "application/octet-stream",
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "download_url": f"/api/download/{rel_path}",
        "serve_url": f"/shared/{rel_path}",
        "playable": file_type in {"video", "audio"},
        "stream_url": f"/api/stream/media/{rel_path}" if file_type in {"video", "audio"} else None,
        "subtitles_url": None,
        "is_dir": False,
        "is_favorite": is_favorite
    }

    # Point to the on-demand thumbnail API
    if file_type in {"image", "video"}:
        info["thumbnail_url"] = f"/api/thumbnail/{rel_path}"
    else:
        info["thumbnail_url"] = None

    # Subtitle detection
    if file_type == "video":
        for ext in SUBTITLE_EXTENSIONS:
            sub_file = filepath.with_suffix(ext)
            if sub_file.exists():
                sub_rel_path = sub_file.relative_to(SHARED_FOLDER).as_posix()
                info["subtitles_url"] = f"/shared/{sub_rel_path}"
                break

    return info


# ── Thumbnails ──────────────────────────────────────────


async def get_or_generate_thumbnail(rel_path: str) -> Path:
    """Entry point for the thumbnail API. Ensures thumbnail exists and returns path."""
    filepath = (SHARED_FOLDER / rel_path).resolve()
    
    # Path traversal check
    if not str(filepath).startswith(str(SHARED_FOLDER)):
        return None
        
    if not filepath.exists() or not filepath.is_file():
        return None
        
    path_hash = hashlib.md5(rel_path.encode()).hexdigest()
    thumb_path = THUMB_DIR / f"{path_hash}.jpg"
    
    if thumb_path.exists():
        return thumb_path
        
    # CRITICAL FIX: Push the blocking FFmpeg/CV2 call to a separate thread
    import asyncio
    await asyncio.to_thread(_generate_thumbnail, filepath)
    return thumb_path

def _generate_thumbnail(filepath: Path):
    """Generate a thumbnail for images and videos."""
    try:
        if not filepath.exists() or not filepath.is_file():
            return
            
        rel_path = filepath.relative_to(SHARED_FOLDER).as_posix()
        file_type = _get_file_type(filepath.name)
        
        import hashlib
        path_hash = hashlib.md5(rel_path.encode()).hexdigest()
        thumb_path = THUMB_DIR / f"{path_hash}.jpg"

        if thumb_path.exists():
            return

        THUMB_DIR.mkdir(parents=True, exist_ok=True)

        if file_type == "image":
            from PIL import Image
            with Image.open(filepath) as img:
                img.thumbnail(THUMB_SIZE)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=70)
                logger.info(f"✅ Image thumbnail generated: {thumb_path.name}")

        elif file_type == "video":
            # 1. Try FFmpeg
            import subprocess
            try:
                cmd = [
                    "ffmpeg", "-y", "-ss", "1", "-i", str(filepath),
                    "-vframes", "1", "-s", f"{THUMB_SIZE[0]}x{THUMB_SIZE[1]}",
                    "-f", "image2", str(thumb_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
                if thumb_path.exists():
                    logger.info(f"✅ Video thumbnail generated via FFmpeg: {thumb_path.name}")
                    return
            except Exception as e:
                logger.debug(f"FFmpeg failed for {filepath.name}, falling back to OpenCV")

            # 2. Try OpenCV
            try:
                import cv2
                cap = cv2.VideoCapture(str(filepath))
                cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
                ret, frame = cap.read()
                if ret:
                    h, w = frame.shape[:2]
                    scale = min(THUMB_SIZE[0] / w, THUMB_SIZE[1] / h)
                    new_w, new_h = int(w * scale), int(h * scale)
                    thumb = cv2.resize(frame, (new_w, new_h))
                    cv2.imwrite(str(thumb_path), thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    logger.info(f"✅ Video thumbnail generated via OpenCV: {thumb_path.name}")
                cap.release()
            except Exception as cv_err:
                logger.warning(f"Both FFmpeg and CV2 failed for {filepath.name}: {cv_err}")

    except Exception as e:
        logger.warning(f"Thumbnail generation error for {filepath.name}: {e}")


# ── Deletion ────────────────────────────────────────────


def delete_file(filename: str) -> bool:
    """
    Safely delete a file from the shared folder.
    Returns True if deleted, raises ValueError on path traversal.
    """
    # Use relative path as-is, but ensure it's safe
    filepath = (SHARED_FOLDER / filename).resolve()

    # Path traversal check
    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise ValueError("Invalid file path")

    if not filepath.exists():
        return False

    # Also remove thumbnail using the same hash logic
    import hashlib
    rel_path = filepath.relative_to(SHARED_FOLDER).as_posix()
    path_hash = hashlib.md5(rel_path.encode()).hexdigest()
    thumb_path = THUMB_DIR / f"{path_hash}.jpg"
    thumb_path.unlink(missing_ok=True)

    if filepath.is_dir():
        import shutil
        shutil.rmtree(filepath)
    else:
        filepath.unlink()

    logger.info(f"🗑️ Deleted: {rel_path}")
    return True


def rename_item(rel_path: str, new_name: str) -> dict:
    """
    Rename a file or directory in the shared folder.
    Returns the updated file info.
    """
    old_path = (SHARED_FOLDER / rel_path).resolve()
    
    # Path traversal check
    if not str(old_path).startswith(str(SHARED_FOLDER)):
        raise ValueError("Invalid file path")
    
    if not old_path.exists():
        raise FileNotFoundError(f"Item not found: {rel_path}")
    
    # Sanitize new name but keep extension if it's a file
    new_name = sanitize_filename(new_name)
    if old_path.is_file():
        # Ensure we don't strip the new extension if the user provided one, 
        # or keep the old one if they didn't.
        if not Path(new_name).suffix:
            new_name += old_path.suffix
            
    new_path = old_path.parent / new_name
    
    if new_path.exists():
        raise ValueError(f"An item with the name '{new_name}' already exists.")
    
    # Also handle thumbnail rename/move if it's a file
    if old_path.is_file():
        old_rel = old_path.relative_to(SHARED_FOLDER).as_posix()
        old_hash = hashlib.md5(old_rel.encode()).hexdigest()
        old_thumb = THUMB_DIR / f"{old_hash}.jpg"
        
        old_path.rename(new_path)
        
        # New thumbnail hash will be different, so just delete the old one
        if old_thumb.exists():
            old_thumb.unlink()
    else:
        old_path.rename(new_path)
        
    logger.info(f"📝 Renamed: {rel_path} -> {new_path.relative_to(SHARED_FOLDER).as_posix()}")
    
    # Return info for the new path
    if new_path.is_file():
        return _file_info(new_path)
    else:
        # Folder info
        favorites = []
        try:
            from favorites_manager import load_favorites
            favorites = load_favorites()
        except: pass
        
        new_rel_path = new_path.relative_to(SHARED_FOLDER).as_posix()
        return {
            "name": new_path.name,
            "filename": new_rel_path,
            "type": "folder",
            "size": 0,
            "size_formatted": "Folder",
            "modified": datetime.fromtimestamp(new_path.stat().st_mtime).isoformat(),
            "is_dir": True,
            "is_favorite": new_rel_path in favorites
        }
