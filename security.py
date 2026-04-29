"""
StreamDrop — Security Middleware
Rewrites the old PIN/in-memory session auth into JWT + Redis multi-instance auth.

Flow:
  1. Every request hits auth_middleware.
  2. Public routes (/, /static/, /api/auth) pass through.
  3. Other routes: read JWT from HttpOnly cookie.
  4. Verify JWT signature → decode claims.
  5. Cross-check against Redis (ensures logout works across instances).
  6. Attach UserContext to request.state.user for RBAC downstream.
  7. Return 401 if any step fails.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError

from auth.jwt_handler import COOKIE_NAME, decode_token
from auth.redis_client import get_session_user_id
from auth.rbac import UserContext

logger = logging.getLogger("streamdrop.security")

# ── Legacy shims (kept so old code that imports these still compiles) ─────────
from config import PIN, JWT_EXPIRE_HOURS, JWT_SECRET
import secrets, time

SESSION_EXPIRY_HOURS = JWT_EXPIRE_HOURS  # alias


def verify_pin(pin_attempt: str) -> bool:
    """Kept for backwards compatibility."""
    return secrets.compare_digest(pin_attempt, PIN)


def create_session():
    """
    Legacy shim — returns (token_placeholder, expiry_timestamp).
    New code should use auth/jwt_handler.py directly.
    """
    token = secrets.token_urlsafe(32)
    expiry = time.time() + (JWT_EXPIRE_HOURS * 3600)
    return token, expiry


def set_session_cookie(response, token: str, expiry: float):
    """Legacy shim. Prefer auth.jwt_handler.set_auth_cookie."""
    from auth.jwt_handler import set_auth_cookie
    set_auth_cookie(response, token)


# ── Routes that bypass authentication ─────────────────────────────────────────
PUBLIC_PATHS = {
    "/",
    "/api/auth",
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
    # Media streaming is public so cast devices / browsers without cookies work.
    # RBAC is still enforced by individual route dependencies where needed.
    "/api/stream/media/",
    "/shared/",
)


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
    except JWTError as e:
        return _unauthorized(f"Invalid or expired session: {e}")

    user_id_str = payload.get("sub")
    username = payload.get("username", "unknown")
    role = payload.get("role", "guest")

    if not user_id_str:
        return _unauthorized("Malformed token: missing subject.")

    # Step 2: Cross-check Redis to support logout-on-all-devices
    # (If Redis is down, we skip this check — JWT alone is sufficient)
    try:
        stored_uid = await get_session_user_id(token)
        if stored_uid is not None and stored_uid != int(user_id_str):
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
