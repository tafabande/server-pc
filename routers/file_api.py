"""
StreamDrop — File Management API Router
Handles gallery listing, uploads, downloads, thumbnails, favorites, and deletion.

RBAC enforcement:
  - GET  routes: all authenticated users (admin, family, guest)
  - POST routes: admin + family
  - DELETE/PATCH: admin only
"""

import logging
from pathlib import Path
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import SHARED_FOLDER
from core.database import get_db, get_folder_optimization, set_folder_optimization, MediaMetadata, log_audit
from core.file_manager import save_upload, list_files, delete_file, get_or_generate_thumbnail, rename_item
from core.favorites_manager import list_favorites_details, toggle_favorite
from core.websockets import manager
from auth.rbac import get_current_user, require_role, guest_path_check, UserContext

logger = logging.getLogger("streamdrop.file_api")
router = APIRouter(prefix="/api", tags=["Files"])


class FavoriteRequest(BaseModel):
    filename: str


class RenameRequest(BaseModel):
    new_name: str


class FolderOptimizationRequest(BaseModel):
    folder_path: str
    enabled: bool


async def _enrich_with_metadata(items: list[dict], db: AsyncSession) -> list[dict]:
    """
    Augment file listing dicts with rich ffprobe metadata from DB.
    Only enriches video files; returns all items unchanged if DB unavailable.
    """
    video_paths = [item["filename"] for item in items if item.get("type") == "video"]
    if not video_paths:
        return items

    try:
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path.in_(video_paths))
        )
        meta_map = {row.rel_path: row for row in result.scalars().all()}

        for item in items:
            meta = meta_map.get(item.get("filename"))
            if meta:
                item["rich_meta"] = {
                    "codec": meta.video_codec,
                    "resolution": meta.resolution_label,
                    "width": meta.width,
                    "height": meta.height,
                    "duration": meta.duration_label,
                    "duration_seconds": meta.duration_seconds,
                    "bitrate_kbps": meta.bitrate_kbps,
                    "audio_codec": meta.audio_codec,
                    "audio_channels": meta.audio_channels,
                    "has_hdr": meta.has_hdr,
                    "is_hls_ready": meta.is_hls_ready,
                    "hls_url": (
                        f"/api/stream/hls/{item['filename']}/index.m3u8"
                        if meta.is_hls_ready else None
                    ),
                }
            else:
                item["rich_meta"] = None
    except Exception as e:
        logger.warning(f"Could not enrich metadata: {e}")

    return items


# ── File Listing ──────────────────────────────────────────────────────────────

@router.get("/files")
@router.get("/files/{path:path}")
async def get_files(
    path: str = "",
    pin: str = Query(None),
    user: UserContext = Depends(guest_path_check),
    db: AsyncSession = Depends(get_db),
):
    from urllib.parse import unquote
    decoded_path = unquote(path)

    target_path = (SHARED_FOLDER / decoded_path).resolve()

    # Folder PIN lock (legacy feature — preserved)
    if target_path.is_dir():
        lock_file = target_path / ".lock"
        if lock_file.exists():
            with open(lock_file, "r") as f:
                required_pin = f.read().strip()
            if pin != required_pin:
                raise HTTPException(status_code=401, detail="Locked")

    items = list_files(decoded_path)
    items = await _enrich_with_metadata(items, db)
    return {"items": items}


# ── Favorites ──────────────────────────────────────────────────────────────────

@router.get("/favorites")
async def get_all_favorites(user: UserContext = Depends(get_current_user)):
    return {"items": list_favorites_details()}


@router.post("/favorites/toggle")
async def toggle_fav(
    body: FavoriteRequest,
    user: UserContext = Depends(get_current_user),
):
    state = toggle_favorite(body.filename)
    return {"status": "ok", "favorite": state}


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload", dependencies=[Depends(require_role("admin", "family"))])
async def upload_file(
    file: UploadFile = File(...),
    path: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    try:
        info = await save_upload(file, path)

        # Trigger ffprobe metadata extraction as a background task
        if info["type"] in {"video", "audio"}:
            import asyncio
            from workers.ffprobe_worker import probe_file_async
            asyncio.create_task(
                probe_file_async(info["filename"], str((SHARED_FOLDER / info["filename"]).resolve()))
            )

        if info["type"] == "video":
            folder_path = Path(info["filename"]).parent.as_posix()
            if folder_path == ".":
                folder_path = ""
            if get_folder_optimization(folder_path):
                from core.workers import transcode_to_hls
                asyncio.create_task(transcode_to_hls(info["filename"]))
                logger.info(f"📤 Started HLS transcode: {info['name']}")

        await log_audit(db, "FILE_UPLOAD", target_resource=info["filename"], user_id=user.user_id if hasattr(user, 'user_id') else None)
        await manager.broadcast({"type": "update"})
        return {"status": "ok", "file": info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload/subtitles", dependencies=[Depends(require_role("admin", "family"))])
async def upload_subtitles(
    file: UploadFile = File(...),
    video_filename: str = Query(...),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in {".srt", ".vtt"}:
        raise HTTPException(status_code=400, detail="Only .srt and .vtt files are allowed")

    video_path = SHARED_FOLDER / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    target_path = video_path.with_suffix(ext)
    async with aiofiles.open(target_path, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            await out_file.write(chunk)

    return {"status": "ok", "subtitles": target_path.name}


# ── Download ───────────────────────────────────────────────────────────────────

@router.get("/download/{filename:path}")
async def download_file(
    filename: str,
    user: UserContext = Depends(get_current_user),
):
    filepath = (SHARED_FOLDER / filename).resolve()
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


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/files/{filename:path}", dependencies=[Depends(require_role("admin"))])
async def remove_file(
    filename: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        deleted = delete_file(filename)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        
        await log_audit(db, "FILE_DELETE", target_resource=filename, user_id=user.user_id)
        await manager.broadcast({"type": "update"})
        return {"status": "ok", "deleted": filename}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Rename ─────────────────────────────────────────────────────────────────────

@router.patch("/files/{filename:path}", dependencies=[Depends(require_role("admin", "family"))])
async def rename_file_endpoint(filename: str, body: RenameRequest, user: UserContext = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        info = rename_item(filename, body.new_name)
        await log_audit(db, "FILE_RENAME", target_resource=filename, details={"to": body.new_name}, user_id=user.user_id)
        await manager.broadcast({"type": "update"})
        return {"status": "ok", "file": info}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Thumbnail ──────────────────────────────────────────────────────────────────

@router.get("/thumbnail/{full_path:path}")
async def get_thumbnail(
    full_path: str,
    user: UserContext = Depends(get_current_user),
):
    from urllib.parse import unquote
    decoded_path = unquote(full_path)
    thumb_path = await get_or_generate_thumbnail(decoded_path)
    if thumb_path and thumb_path.exists():
        return FileResponse(thumb_path)
    raise HTTPException(status_code=404, detail="Thumbnail not available")


# ── Folder Optimization ────────────────────────────────────────────────────────

@router.post("/folder/optimization", dependencies=[Depends(require_role("admin"))])
async def set_optimization(req: FolderOptimizationRequest):
    set_folder_optimization(req.folder_path, req.enabled)
    return {"status": "ok", "enabled": req.enabled}


@router.get("/folder/optimization")
async def get_optimization(
    folder_path: str = Query(...),
    user: UserContext = Depends(get_current_user),
):
    enabled = get_folder_optimization(folder_path)
    return {"status": "ok", "enabled": enabled}
