"""
StreamDrop — Authentication API Router
Handles user login (JWT cookie), logout, registration, and user management.

Endpoints:
  POST /api/auth/login    — Log in with username + password
  POST /api/auth/logout   — Invalidate session
  POST /api/auth/register — Self-register a new guest account
  GET  /api/auth/verify   — Verify current session & return user context
  GET  /api/auth/me       — Get current user profile
  POST /api/auth/users    — Create a new user (admin only)
"""

import logging
import hashlib
import secrets
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, User, UserRole, log_audit, AuditLog, MediaMetadata, PlayEvent, PasswordResetToken
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


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.guest

class UpdateUserRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login")
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

    await db.commit()

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

@router.get("/verify")
async def verify_session(user: UserContext = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found.")
    
    name = db_user.display_name or db_user.username
    avatar = db_user.avatar_url or f"https://api.dicebear.com/7.x/avataaars/svg?seed={name}"
    
    return {
        "id": db_user.id,
        "username": db_user.username,
        "display_name": name,
        "role": db_user.role.value,
        "avatar_url": avatar,
        "preferences": db_user.preferences
    }

@router.post("/register")
async def register(body: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' already exists.")

    new_user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=UserRole.guest,
        last_login=datetime.now(timezone.utc)
    )
    db.add(new_user)
    await db.flush()

    token = create_user_token(new_user.id, new_user.username, new_user.role.value)
    await store_session(token, new_user.id, ttl_seconds=JWT_EXPIRE_HOURS * 3600)
    set_auth_cookie(response, token)

    await log_audit(
        db=db,
        user_id=new_user.id,
        action_type="REGISTER",
        details={"ip": request.client.host if request.client else "unknown"}
    )

    await db.commit()

    logger.info(f"✨ New user registered: {new_user.username}")
    return {
        "status": "ok",
        "message": "Account created",
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
    await log_audit(
        db=db,
        action_type="USER_CREATE",
        target_resource=body.username,
        details={"role": body.role.value}
    )
    return {
        "status": "ok",
        "user": {"id": new_user.id, "username": new_user.username, "role": new_user.role.value},
    }


@router.patch("/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def update_user(user_id: int, body: UpdateUserRequest, db: AsyncSession = Depends(get_db)):
    """Update user role or status. Admin-only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if body.role is not None:
        user.role = body.role
    
    if body.is_active is not None:
        user.is_active = body.is_active
        if not user.is_active:
            await invalidate_all_user_sessions(user_id)

    logger.info(f"👤 Updated user: {user.username} (active={user.is_active}, role={user.role.value})")
    await log_audit(
        db=db,
        action_type="USER_UPDATE",
        target_resource=user.username,
        user_id=user_id,
        details={"role": user.role.value, "is_active": user.is_active}
    )
    return {"status": "ok", "user": {"id": user.id, "username": user.username, "role": user.role.value, "is_active": user.is_active}}


@router.delete("/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Hard delete a user. Admin-only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    await invalidate_all_user_sessions(user_id)
    await db.delete(user)
    logger.info(f"🗑️ Deleted user: {user.username}")
    await log_audit(
        db=db,
        action_type="USER_DELETE",
        target_resource=user.username,
        details={"user_id": user_id}
    )
    return {"status": "ok", "message": f"User '{user.username}' deleted."}


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

@router.get("/audit", dependencies=[Depends(require_role("admin"))])
async def get_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Fetch recent audit logs. Admin-only."""
    result = await db.execute(
        select(AuditLog, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.all()
    return {
        "logs": [
            {
                "id": log.AuditLog.id,
                "timestamp": log.AuditLog.timestamp.isoformat(),
                "user": log.username or "System",
                "action": log.AuditLog.action_type,
                "resource": log.AuditLog.target_resource,
                "details": log.AuditLog.details
            }
            for log in logs
        ]
    }


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset token."""
    email_or_username = request.get("email_or_username")
    if not email_or_username:
        raise HTTPException(400, "Email or username required")

    # Find user
    result = await db.execute(
        select(User).where(
            or_(User.username == email_or_username)
        )
    )
    user = result.scalar_one_or_none()

    # Always return success (don't leak user existence)
    if not user:
        logger.warning(f"Password reset requested for non-existent user: {email_or_username}")
        return {"message": "If account exists, reset instructions will be sent"}

    # Generate token
    raw_token = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw_token.encode()).hexdigest()

    # Invalidate old tokens
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .where(PasswordResetToken.used == False)
        .values(used=True)
    )

    # Create new token
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    db.add(reset_token)
    await db.commit()

    # In production, send email here
    # For development mode ONLY, log the token (insecure but practical for LAN dev)
    if os.getenv("ENV") == "development":
        logger.warning(f"🔧 DEV ONLY - Password reset token for {user.username}: {raw_token}")
        logger.warning(f"🔧 DEV ONLY - Reset URL: http://localhost:8000/reset-password?token={raw_token}")
    else:
        logger.info(f"Password reset requested for user ID: {user.id}")

    return {"message": "If account exists, reset instructions have been sent. Check your server logs in development mode."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token."""
    token = request.get("token")
    new_password = request.get("new_password")

    if not token or not new_password:
        raise HTTPException(400, "Token and new password required")

    if len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    # Hash token
    hashed = hashlib.sha256(token.encode()).hexdigest()

    # Find valid token
    result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token == hashed)
        .where(PasswordResetToken.used == False)
        .where(PasswordResetToken.expires_at > datetime.now(timezone.utc))
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise HTTPException(400, "Invalid or expired token")

    # Get user
    result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    # Update password
    user.hashed_password = hash_password(new_password)
    reset_token.used = True

    await db.commit()

    # Log audit
    await log_audit(db, user.id, "password_reset", details={"via": "reset_token"})

    logger.info(f"Password reset successful for user: {user.username}")

    return {"message": "Password reset successful"}


@router.patch("/me", response_model=dict)
async def update_profile(
    updates: dict,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's profile."""
    allowed_fields = {"display_name", "avatar_url", "preferences"}

    # Get user
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    for key, value in updates.items():
        if key not in allowed_fields:
            raise HTTPException(400, f"Cannot update field: {key}")
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "preferences": user.preferences
    }


@router.get("/me/preferences")
async def get_preferences(current_user: UserContext = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get user preferences."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user.preferences or {}


@router.patch("/me/preferences")
async def update_preferences(
    preferences: dict,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user preferences (merge with existing)."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    current_prefs = user.preferences or {}
    current_prefs.update(preferences)
    user.preferences = current_prefs

    await db.commit()

    return user.preferences


@router.get("/stats", dependencies=[Depends(require_role("admin"))])
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Fetch system statistics. Admin-only."""
    users_count = await db.scalar(select(func.count()).select_from(User))
    media_count = await db.scalar(select(func.count()).select_from(MediaMetadata))
    plays_count = await db.scalar(select(func.count()).select_from(PlayEvent))
    audit_count = await db.scalar(select(func.count()).select_from(AuditLog))

    # Get storage stats
    result = await db.execute(select(func.sum(MediaMetadata.file_size_bytes)))
    total_bytes = result.scalar() or 0

    return {
        "total_users": users_count,
        "total_media": media_count,
        "total_plays": plays_count,
        "audit_count": audit_count,
        "total_storage_bytes": total_bytes
    }
