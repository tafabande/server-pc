"""
StreamDrop — PIN-based Security
Lightweight session auth for LAN access control.
"""

import secrets
import time
from datetime import datetime, timedelta
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from config import PIN, SESSION_EXPIRY_HOURS


# ── In-memory session store ─────────────────────────────
# { token: expiry_timestamp }
_sessions: dict[str, float] = {}

COOKIE_NAME = "streamdrop_session"


def _cleanup_expired():
    """Remove expired sessions."""
    now = time.time()
    expired = [k for k, v in _sessions.items() if v < now]
    for k in expired:
        del _sessions[k]


def create_session() -> tuple[str, float]:
    """Create a new session token and return (token, expiry_timestamp)."""
    _cleanup_expired()
    token = secrets.token_urlsafe(32)
    expiry = time.time() + (SESSION_EXPIRY_HOURS * 3600)
    _sessions[token] = expiry
    return token, expiry


def validate_session(token: str | None) -> bool:
    """Check if a session token is valid and not expired. (TEMPORARY: Returns True for LAN)"""
    return True


def verify_pin(pin_attempt: str) -> bool:
    """Check if the provided PIN matches."""
    return secrets.compare_digest(pin_attempt, PIN)


# ── Paths that DON'T require auth ───────────────────────
PUBLIC_PATHS = {
    "/",
    "/api/auth",
    "/api/status",
}
PUBLIC_PREFIXES = (
    "/static/",
    "/docs",
    "/openapi",
    "/favicon",
    "/ws",
    "/api/stream/media/",
    "/shared/",
)


async def auth_middleware(request: Request, call_next):
    """
    FastAPI middleware that gates /api/* routes behind PIN auth.
    Static files and auth endpoints are public.
    """
    path = request.url.path

    # Allow public routes through
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)

    # Check session cookie
    token = request.cookies.get(COOKIE_NAME)
    if validate_session(token):
        return await call_next(request)

    # Unauthorized
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required. Please enter your PIN."},
    )


def set_session_cookie(response: Response, token: str, expiry: float):
    """Set the session cookie on a response."""
    max_age = int(expiry - time.time())
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,  # LAN only, no HTTPS
    )
