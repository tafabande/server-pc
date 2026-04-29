"""
StreamDrop — Authentication API Router
Handles login (PIN → JWT cookie), logout, and current user info.

Endpoints:
  POST /api/auth        — Log in with username + password (or legacy PIN)
  POST /api/auth/logout — Invalidate session
  GET  /api/auth/me     — Get current user info
  POST /api/auth/users  — Create a new user (admin only)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, User, UserRole, log_audit
from auth.jwt_handler import create_user_token, set_auth_cookie, clear_auth_cookie, COOKIE_NAME
from auth.redis_client import store_session, invalidate_session, invalidate_all_user_sessions
from auth.rbac import get_current_user, require_role, UserContext
from config import JWT_EXPIRE_HOURS

logger = logging.getLogger("streamdrop.auth_api")
router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── Password hashing ──────────────────────────────────────────────────────────
from core.security import hash_password, verify_password


# ── Request / Response Schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.guest


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("")
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with username + password.
    Returns a JWT stored in an HttpOnly cookie (no token in body for XSS safety).
    """
    result = await db.execute(
        select(User).where(User.username == body.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Create JWT
    token = create_user_token(user.id, user.username, user.role.value)

    # Store in Redis for multi-instance session validation
    await store_session(token, user.id, ttl_seconds=JWT_EXPIRE_HOURS * 3600)

    # Set HttpOnly cookie
    set_auth_cookie(response, token)

    # Log Audit
    await log_audit(
        db=db,
        user_id=user.id,
        action_type="LOGIN",
        details={"ip": request.client.host if request.client else "unknown"}
    )

    logger.info(f"✅ Login: user={user.username} role={user.role.value}")
    return {
        "status": "ok",
        "message": "Authenticated",
        "user": {"id": user.id, "username": user.username, "role": user.role.value},
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Invalidate the current session cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        await invalidate_session(token)
    clear_auth_cookie(response)
    return {"status": "ok", "message": "Logged out."}


@router.get("/me")
async def get_me(user: UserContext = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the currently authenticated user's profile."""
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "id": db_user.id,
        "username": db_user.username,
        "role": db_user.role.value,
        "created_at": db_user.created_at.isoformat(),
        "last_login": db_user.last_login.isoformat() if db_user.last_login else None,
    }


@router.post("/users", dependencies=[Depends(require_role("admin"))])
async def create_user(body: CreateUserRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user. Admin-only."""
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' already exists.")

    new_user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(new_user)
    await db.flush()  # Get the ID without full commit (get_db handles commit)

    logger.info(f"👤 Created user: {body.username} ({body.role.value})")
    return {
        "status": "ok",
        "user": {"id": new_user.id, "username": new_user.username, "role": new_user.role.value},
    }


@router.delete("/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Deactivate a user account and invalidate all their sessions. Admin-only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.is_active = False
    await invalidate_all_user_sessions(user_id)
    logger.info(f"🚫 Deactivated user: {user.username}")
    return {"status": "ok", "message": f"User '{user.username}' deactivated."}


@router.get("/users", dependencies=[Depends(require_role("admin"))])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all users. Admin-only."""
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role.value,
                "is_active": u.is_active,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]
    }
