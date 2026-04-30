"""
StreamDrop — Security Core
Handles authentication middleware and password hashing.
"""

import logging
import bcrypt
from fastapi import Request
from fastapi.responses import JSONResponse

from auth.jwt_handler import COOKIE_NAME, decode_token
from auth.redis_client import get_session_user_id
from auth.rbac import UserContext

logger = logging.getLogger("streamdrop.security")

# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        password_bytes = plain.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False



# ── Routes that bypass authentication ─────────────────────────────────────────
PUBLIC_PATHS = {
    "/",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/logout",
    "/api/status",
    "/api/qr",
    "/manifest.json",
    "/sw.js",
}
PUBLIC_PREFIXES = (
    "/static/",
    "/docs",
    "/openapi",
    "/favicon",
    "/ws",
    "/metrics",
    "/api/stream/media/",
    "/shared/",
)


# ── Middleware ────────────────────────────────────────────────────────────────

async def auth_middleware(request: Request, call_next):
    """
    FastAPI middleware that:
    1. Passes public routes through.
    2. Validates JWT from HttpOnly cookie.
    3. Cross-checks against Redis session store.
    4. Attaches UserContext to request.state.user.
    """
    path = request.url.path

    # Always pass public routes through
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return _unauthorized("No session cookie. Please log in.")

    # Step 1: Verify JWT signature and expiry (pure cryptography, no DB hit)
    try:
        payload = decode_token(token)
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            return _unauthorized(e.detail)
        return _unauthorized(f"Invalid or expired session: {e}")

    user_id_str = payload.get("sub")
    username = payload.get("username", "unknown")
    role = payload.get("role", "guest")

    if not user_id_str:
        return _unauthorized("Malformed token: missing subject.")

    # Step 2: Cross-check Redis to support logout-on-all-devices
    try:
        stored_uid = await get_session_user_id(token)
        if stored_uid is None:
            # Session was never stored or has been invalidated/expired
            return _unauthorized("Session expired or invalidated. Please log in again.")
        if stored_uid != int(user_id_str):
            return _unauthorized("Session invalidated.")
    except Exception:
        # Redis unreachable — fall back to JWT-only validation
        pass

    # Attach user context for RBAC dependencies
    request.state.user = UserContext(
        user_id=int(user_id_str),
        username=username,
        role=role,
    )

    return await call_next(request)


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
    )
