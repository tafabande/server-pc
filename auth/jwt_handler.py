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
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from fastapi import HTTPException, status

from config import JWT_EXPIRE_HOURS  # config.py loads .env at import time

logger = logging.getLogger("streamdrop.jwt")

COOKIE_NAME = "streamdrop_session"

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

if not SECRET_KEY:
    raise ValueError("CRITICAL: SECRET_KEY is missing from .env file!")


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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises jose.JWTError on invalid / expired tokens.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session, signature verification failed",
        )



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
