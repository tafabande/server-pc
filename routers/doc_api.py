import aiofiles
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from config import SHARED_FOLDER
from core.database import log_audit

router = APIRouter(prefix="/api/docs", tags=["Docs"])

class SaveDocRequest(BaseModel):
    content: str

@router.get("/{filename:path}")
async def read_doc(filename: str):
    """Read raw text of a document for the Quill editor."""
    filepath = (SHARED_FOLDER / filename).resolve()

    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
        
    ext = filepath.suffix.lower()
    if ext not in {".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported for inline editing")

    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
        content = await f.read()
        
    return {"content": content, "filename": filename}

@router.post("/{filename:path}")
async def write_doc(filename: str, request: SaveDocRequest, req: Request):
    """Write text back to document and log to SQLite."""
    filepath = (SHARED_FOLDER / filename).resolve()

    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
        
    ext = filepath.suffix.lower()
    if ext not in {".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported for inline editing")

    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(request.content)
        
    # Log the audit trail
    ip_address = req.client.host if req.client else "unknown"
    log_audit(ip_address, filename, "Edited")
        
    return {"status": "ok", "message": "Document saved successfully"}
