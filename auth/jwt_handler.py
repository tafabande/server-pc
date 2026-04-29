"""
StreamDrop — JWT Handler
Creates and verifies HS256 JWTs for stateless authentication.

Design choices:
- HttpOnly cookie ONLY (no localStorage) for XSS safety.
- The cookie is set by the login endpoint and read by middleware.
- No Authorization header support — the browser attaches the cookie automatically
  to every same-origin fetch(), so zero frontend code changes are needed.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS

logger = logging.getLogger("streamdrop.jwt")

COOKIE_NAME = "streamdrop_session"


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Sign a JWT with the given payload.
    Always adds an 'exp' (expiry) claim.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=JWT_EXPIRE_HOURS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises jose.JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def create_user_token(user_id: int, username: str, role: str) -> str:
    """
    Convenience wrapper: create a token with standard StreamDrop claims.
    """
    return create_access_token({
        "sub": str(user_id),
        "username": username,
        "role": role,
    })


def set_auth_cookie(response, token: str):
    """
    Attach the JWT as a secure, HttpOnly cookie to the response.
    - httponly=True  → JS cannot read it (XSS protection)
    - samesite="lax" → Sent on same-origin + top-level navigations
    - secure=False   → LAN-only, no HTTPS required
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True behind an HTTPS reverse proxy
        path="/",
    )


def clear_auth_cookie(response):
    """Delete the session cookie on logout."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
