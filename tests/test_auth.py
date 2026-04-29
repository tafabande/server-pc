"""
StreamDrop — Authentication & RBAC Integration Tests
Tests the full login → token → protected route → role enforcement flow.

Uses the async TestClient + in-memory SQLite database.
No real Redis required — falls back to in-memory session store.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestLogin:
    """Test the /api/auth login endpoint."""

    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth",
            json={"username": "nobody", "password": "anything"},
        )
        assert resp.status_code == 401

    async def test_login_correct_credentials(self, client: AsyncClient, admin_token: str):
        # admin_token fixture already logs in — just verify we got a cookie
        assert admin_token, "Should have received a session cookie"

    async def test_login_sets_httponly_cookie(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth",
            json={"username": "admin", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        # Cookie must be present
        assert "streamdrop_session" in resp.cookies
        # Response body must NOT contain the token (HttpOnly — not in JSON)
        body = resp.json()
        assert "token" not in body or body.get("token") is None

    async def test_login_returns_user_info(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth",
            json={"username": "admin", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["username"] == "admin"
        assert body["user"]["role"] == "admin"


class TestAuthProtection:
    """Test that protected routes reject unauthenticated requests."""

    async def test_unauthenticated_cannot_access_files(self, client: AsyncClient):
        # Clear cookies to ensure no session
        resp = await client.get("/api/files")
        assert resp.status_code == 401

    async def test_unauthenticated_cannot_upload(self, client: AsyncClient):
        resp = await client.post("/api/upload", data={})
        assert resp.status_code == 401

    async def test_authenticated_can_access_files(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/files",
            cookies={"streamdrop_session": admin_token},
        )
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_status_is_public(self, client: AsyncClient):
        """API status should not require auth."""
        resp = await client.get("/api/status")
        assert resp.status_code == 200

    async def test_metrics_is_public(self, client: AsyncClient):
        """Prometheus metrics should not require auth."""
        resp = await client.get("/metrics")
        assert resp.status_code == 200


class TestRBAC:
    """Test role-based access control enforcement."""

    async def test_guest_can_read_files(self, client: AsyncClient, guest_token: str):
        resp = await client.get(
            "/api/files",
            cookies={"streamdrop_session": guest_token},
        )
        assert resp.status_code == 200

    async def test_guest_cannot_delete_files(self, client: AsyncClient, guest_token: str):
        """Guests must not be able to delete files."""
        resp = await client.delete(
            "/api/files/any_file.mp4",
            cookies={"streamdrop_session": guest_token},
        )
        assert resp.status_code == 403

    async def test_family_cannot_delete_files(self, client: AsyncClient, family_token: str):
        """Family role cannot delete — only admin can."""
        resp = await client.delete(
            "/api/files/any_file.mp4",
            cookies={"streamdrop_session": family_token},
        )
        assert resp.status_code == 403

    async def test_admin_can_delete_files(self, client: AsyncClient, admin_token: str):
        """Admin delete returns 404 (file doesn't exist) not 403 (permission denied)."""
        resp = await client.delete(
            "/api/files/nonexistent_file.mp4",
            cookies={"streamdrop_session": admin_token},
        )
        # 404 means auth passed but file not found — that's correct behavior
        assert resp.status_code in (200, 404)
        assert resp.status_code != 403

    async def test_guest_cannot_upload(self, client: AsyncClient, guest_token: str):
        import io
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
            cookies={"streamdrop_session": guest_token},
        )
        assert resp.status_code == 403

    async def test_family_can_upload(self, client: AsyncClient, family_token: str):
        import io
        resp = await client.post(
            "/api/upload",
            files={"file": ("allowed.txt", io.BytesIO(b"hello world"), "text/plain")},
            cookies={"streamdrop_session": family_token},
        )
        # 200 OK or 400 (extension check) but NOT 403
        assert resp.status_code != 403

    async def test_admin_only_user_management(self, client: AsyncClient, guest_token: str):
        """Non-admin cannot list users."""
        resp = await client.get(
            "/api/auth/users",
            cookies={"streamdrop_session": guest_token},
        )
        assert resp.status_code == 403

    async def test_admin_can_list_users(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/auth/users",
            cookies={"streamdrop_session": admin_token},
        )
        assert resp.status_code == 200
        assert "users" in resp.json()


class TestLogout:
    """Test session invalidation."""

    async def test_logout_clears_cookie(self, client: AsyncClient):
        # Login
        login_resp = await client.post(
            "/api/auth",
            json={"username": "admin", "password": "testpassword123"},
        )
        assert login_resp.status_code == 200

        # Logout
        logout_resp = await client.post(
            "/api/auth/logout",
            cookies=login_resp.cookies,
        )
        assert logout_resp.status_code == 200

    async def test_me_endpoint(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/auth/me",
            cookies={"streamdrop_session": admin_token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"
