"""
StreamDrop — Streaming API Integration Tests
Tests byte-range streaming and HLS routing behavior.
"""

import io
import shutil
from pathlib import Path

import pytest
from httpx import AsyncClient


# Removed global mark to allow individual async control


class TestByteRangeStreaming:
    """Test the byte-range streaming endpoint with a real file."""

    async def _put_video_in_shared(self, test_video: Path) -> str:
        """Copy test video to SHARED_FOLDER and return relative path."""
        from config import SHARED_FOLDER
        dest = SHARED_FOLDER / "stream_test.mp4"
        shutil.copy2(test_video, dest)
        return "stream_test.mp4"

    @pytest.mark.asyncio
    async def test_full_stream_returns_200(
        self, client: AsyncClient, admin_token: str, test_video: Path
    ):
        if not shutil.which("ffprobe"):
            pytest.skip("FFmpeg not available")
        rel = await self._put_video_in_shared(test_video)
        resp = await client.get(
            f"/api/stream/media/{rel}",
            cookies={"streamdrop_session": admin_token},
        )
        # 200 (full) or 302 (redirect to HLS if already transcoded)
        assert resp.status_code in (200, 302)

    @pytest.mark.asyncio
    async def test_range_request_returns_206(
        self, client: AsyncClient, admin_token: str, test_video: Path
    ):
        if not shutil.which("ffprobe"):
            pytest.skip("FFmpeg not available")
        rel = await self._put_video_in_shared(test_video)
        resp = await client.get(
            f"/api/stream/media/{rel}",
            headers={"Range": "bytes=0-1023"},
            cookies={"streamdrop_session": admin_token},
        )
        # 206 partial content or 302 HLS redirect
        assert resp.status_code in (206, 302)
        if resp.status_code == 206:
            assert "Content-Range" in resp.headers
            assert resp.headers["Content-Range"].startswith("bytes 0-")

    @pytest.mark.asyncio
    async def test_invalid_range_returns_416(
        self, client: AsyncClient, admin_token: str, test_video: Path
    ):
        if not shutil.which("ffprobe"):
            pytest.skip("FFmpeg not available")
        rel = await self._put_video_in_shared(test_video)
        file_size = (Path(test_video).stat().st_size)
        # Request beyond file end
        resp = await client.get(
            f"/api/stream/media/{rel}",
            headers={"Range": f"bytes={file_size + 1}-{file_size + 100}"},
            cookies={"streamdrop_session": admin_token},
        )
        # 416 Range Not Satisfiable or 302 HLS redirect (either is acceptable)
        assert resp.status_code in (416, 302)

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_404(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.get(
            "/api/stream/media/definitely_does_not_exist.mp4",
            cookies={"streamdrop_session": admin_token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_in_stream_blocked(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.get(
            "/api/stream/media/../../etc/passwd",
            cookies={"streamdrop_session": admin_token},
        )
        assert resp.status_code in (403, 404)


class TestStreamControl:
    """Test live stream start/stop endpoints (RBAC enforcement)."""

    @pytest.mark.asyncio
    async def test_guest_cannot_start_stream(
        self, client: AsyncClient, guest_token: str
    ):
        resp = await client.post(
            "/api/stream/start",
            cookies={"streamdrop_session": guest_token},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_stop_stream(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.post(
            "/api/stream/stop",
            cookies={"streamdrop_session": admin_token},
        )
        # 200 OK (stream was already stopped) — just checking RBAC passes
        assert resp.status_code == 200
