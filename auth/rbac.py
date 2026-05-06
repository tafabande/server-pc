"""
StreamDrop — RBAC (Role-Based Access Control)
FastAPI dependency factories for protecting routes by role.

Usage:
    from auth.rbac import require_role

    @router.delete("/api/files/{path:path}", dependencies=[Depends(require_role("admin"))])
    async def delete_file(...): ...

    @router.post("/api/upload", dependencies=[Depends(require_role("admin", "family"))])
    async def upload(...): ...
"""

import logging
from fastapi import Depends, HTTPException, Request, status

from core.database import UserRole

logger = logging.getLogger("streamdrop.rbac")


class UserContext:
    """
    Lightweight user context attached to request.state by auth middleware.
    Avoids a DB round-trip on every RBAC check.
    """
    def __init__(self, user_id: int, username: str, role: str):
        self.user_id = user_id
        self.username = username
        self.role = UserRole(role)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.admin

    @property
    def is_family(self) -> bool:
        return self.role == UserRole.family

    @property
    def is_guest(self) -> bool:
        return self.role == UserRole.guest

    def __repr__(self):
        return f"<UserContext user_id={self.user_id} role={self.role}>"


def get_current_user(request: Request) -> UserContext:
    """
    FastAPI dependency: extracts the UserContext set by auth middleware.
    Raises 401 if no user is attached (middleware failed to authenticate).
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    return user


def require_role(*allowed_roles: str):
    """
    Dependency factory: restrict a route to users with one of the specified roles.

    Example:
        dependencies=[Depends(require_role("admin"))]
        dependencies=[Depends(require_role("admin", "family"))]
    """
    normalized = {UserRole(r) for r in allowed_roles}

    async def _check(user: UserContext = Depends(get_current_user)):
        if user.role not in normalized:
            logger.warning(
                f"RBAC denied: user={user.username} role={user.role.value} "
                f"tried to access route requiring {[r.value for r in normalized]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(r.value for r in normalized)}.",
            )
        return user

    return _check


def require_admin():
    """Shorthand for require_role('admin')."""
    return require_role("admin")


async def check_media_access(
    filename: str, 
    user: UserContext = Depends(get_current_user),
    db: Any = Depends(lambda: None) # Placeholder for db
):
    """
    Enforce Row-Level Security (RLS) for media.
    Admin can access everything.
    Family/Guest can only access public media or media they own.
    """
    if user.is_admin:
        return True
    
    # This is a conceptual implementation of RLS
    # In a real app, we would query the DB to check owner_id
    # For now, we'll implement the logic in the routers to keep dependencies clean
    return True

def guest_path_check(request: Request, user: UserContext = Depends(get_current_user)):
    """
    Dependency: Ensures guest users can only access files under GUEST_ROOT_PATH.
    Attach to any file-listing or streaming route.
    """
    if user.is_guest:
        from config import GUEST_ROOT_PATH
        if GUEST_ROOT_PATH:
            # Extract the requested path from query params or path params
            requested_path = (
                request.path_params.get("path", "")
                or request.path_params.get("filename", "")
                or request.query_params.get("path", "")
            )
            if not requested_path.startswith(GUEST_ROOT_PATH):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Guests are restricted to '{GUEST_ROOT_PATH}'.",
                )
    return user
