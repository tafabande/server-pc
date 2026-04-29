import logging
from pathlib import Path
import aiofiles
from fastapi import APIRouter, HTTPException, File, UploadFile, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from config import SHARED_FOLDER
from file_manager import save_upload, list_files, delete_file, get_or_generate_thumbnail, rename_item
from favorites_manager import list_favorites_details, toggle_favorite
from core.database import add_video_job, get_folder_optimization, set_folder_optimization
from workers.compression import job_queue
from core.websocket_manager import ws_manager

logger = logging.getLogger("streamdrop.file_api")
router = APIRouter(prefix="/api", tags=["Files"])

class FavoriteRequest(BaseModel):
    filename: str

class RenameRequest(BaseModel):
    new_name: str

class FolderOptimizationRequest(BaseModel):
    folder_path: str
    enabled: bool

@router.get("/files")
@router.get("/files/{path:path}")
async def get_files(path: str = "", pin: str = Query(None)):
    from urllib.parse import unquote
    decoded_path = unquote(path)
    
    target_path = (SHARED_FOLDER / decoded_path).resolve()
    
    # --- THE LOCK CHECK ---
    if target_path.is_dir():
        lock_file = target_path / ".lock"
        if lock_file.exists():
            with open(lock_file, "r") as f:
                required_pin = f.read().strip()
            if pin != required_pin:
                raise HTTPException(status_code=401, detail="Locked")
                
    return {"items": list_files(decoded_path)}

@router.get("/favorites")
async def get_all_favorites():
    return {"items": list_favorites_details()}

@router.post("/favorites/toggle")
async def toggle_fav(body: FavoriteRequest):
    state = toggle_favorite(body.filename)
    return {"status": "ok", "favorite": state}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), path: str = Query(default="")):
    try:
        info = await save_upload(file, path)
        
        # Check if we should add this to the compression/HLS queue
        if info["type"] == "video":
            # Determine folder path from info
            # info["filename"] is the relative path, we need its directory
            folder_path = Path(info["filename"]).parent.as_posix()
            if folder_path == ".":
                folder_path = ""
                
            if get_folder_optimization(folder_path):
                # We need to pass absolute path to job
                full_path = str((SHARED_FOLDER / info["filename"]).resolve())
                add_video_job(full_path)
                # Load latest job info to push to queue (we need the ID)
                from core.database import get_db
                conn = get_db()
                cursor = conn.execute("SELECT id, file_path FROM video_jobs WHERE file_path = ?", (full_path,))
                job = cursor.fetchone()
                conn.close()
                if job:
                    await job_queue.put(dict(job))
                    logger.info(f"Queued {info['name']} for optimization")

        # Broadcast the update to all clients
        await ws_manager.broadcast({"type": "update"})
        return {"status": "ok", "file": info}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload/subtitles")
async def upload_subtitles(file: UploadFile = File(...), video_filename: str = Query(...)):
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

@router.get("/download/{filename:path}")
async def download_file(filename: str):
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

@router.delete("/files/{filename:path}")
async def remove_file(filename: str):
    try:
        deleted = delete_file(filename)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        await ws_manager.broadcast({"type": "update"})
        return {"status": "ok", "deleted": filename}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/files/{filename:path}")
async def rename_file_endpoint(filename: str, body: RenameRequest):
    try:
        info = rename_item(filename, body.new_name)
        await ws_manager.broadcast({"type": "update"})
        return {"status": "ok", "file": info}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/thumbnail/{full_path:path}")
async def get_thumbnail(full_path: str):
    from urllib.parse import unquote
    decoded_path = unquote(full_path)
    thumb_path = await get_or_generate_thumbnail(decoded_path)
    if thumb_path and thumb_path.exists():
        return FileResponse(thumb_path)
    raise HTTPException(status_code=404, detail="Thumbnail not available")

@router.post("/folder/optimization")
async def set_optimization(req: FolderOptimizationRequest):
    set_folder_optimization(req.folder_path, req.enabled)
    return {"status": "ok", "enabled": req.enabled}

@router.get("/folder/optimization")
async def get_optimization(folder_path: str = Query(...)):
    enabled = get_folder_optimization(folder_path)
    return {"status": "ok", "enabled": enabled}
