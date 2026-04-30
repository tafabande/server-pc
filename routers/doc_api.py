"""
StreamDrop — Document Editor API Router
Handles reading and writing text/markdown documents for the Quill editor.

RBAC enforcement:
  - GET: all authenticated users (guest check for path)
  - POST: admin + family
"""

import logging
import aiofiles
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import SHARED_FOLDER
from core.database import get_db, log_audit
from core.socket_manager import manager
from auth.rbac import get_current_user, require_role, guest_path_check, UserContext

logger = logging.getLogger("streamdrop.doc_api")
router = APIRouter(prefix="/api/docs", tags=["Docs"])


class SaveDocRequest(BaseModel):
    content: str


@router.get("/{filename:path}")
async def read_doc(
    filename: str,
    user: UserContext = Depends(guest_path_check),
):
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


@router.post("/{filename:path}", dependencies=[Depends(require_role("admin", "family"))])
async def write_doc(
    filename: str, 
    body: SaveDocRequest, 
    req: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Write text back to document and log to audit trail."""
    filepath = (SHARED_FOLDER / filename).resolve()

    if not str(filepath).startswith(str(SHARED_FOLDER)):
        raise HTTPException(status_code=403, detail="Access denied")
        
    ext = filepath.suffix.lower()
    if ext not in {".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported for inline editing")

    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(body.content)
        
    # Log the audit trail
    ip_address = req.client.host if req.client else "unknown"
    await log_audit(
        db=db,
        user_id=user.user_id,
        action_type="DOC_EDIT",
        target_resource=filename,
        details={"ip": ip_address, "size": len(body.content)}
    )
    
    # Broadcast update
    await manager.broadcast({"type": "update"})
        
    return {"status": "ok", "message": "Document saved successfully"}
