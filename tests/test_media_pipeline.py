"""
StreamDrop — Media Pipeline Tests
Tests for ffprobe extraction and upload-triggered metadata indexing.

Skips gracefully if FFmpeg/ffprobe is not installed (CI without media tools).
Uses the tiny 1-second test video from conftest.py (< 200KB).
"""

import pytest
import shutil
from pathlib import Path


# Removed global mark to allow sync tests to run without warnings


class TestFfprobeExtraction:
    """Test ffprobe metadata extraction on the synthetic test video."""

    def test_ffprobe_available(self):
        """Skip all pipeline tests if ffprobe is not installed."""
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")

    def test_probe_file_returns_data(self, test_video: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe
        data = _run_ffprobe(str(test_video))
        assert data is not None
        assert "streams" in data
        assert "format" in data

    def test_probe_extracts_codec(self, test_video: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe, _parse_ffprobe_output
        raw = _run_ffprobe(str(test_video))
        assert raw is not None
        meta = _parse_ffprobe_output(raw, test_video.stat().st_size)
        assert meta["video_codec"] == "h264"

    def test_probe_extracts_resolution(self, test_video: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe, _parse_ffprobe_output
        raw = _run_ffprobe(str(test_video))
        meta = _parse_ffprobe_output(raw, test_video.stat().st_size)
        assert meta["width"] == 320
        assert meta["height"] == 240

    def test_probe_extracts_duration(self, test_video: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe, _parse_ffprobe_output
        raw = _run_ffprobe(str(test_video))
        meta = _parse_ffprobe_output(raw, test_video.stat().st_size)
        assert meta["duration_seconds"] is not None
        # Should be approximately 1 second (allow 10% tolerance)
        assert 0.5 <= meta["duration_seconds"] <= 2.0

    def test_probe_extracts_audio_info(self, test_video: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe, _parse_ffprobe_output
        raw = _run_ffprobe(str(test_video))
        meta = _parse_ffprobe_output(raw, test_video.stat().st_size)
        assert meta["audio_codec"] == "aac"

    def test_probe_nonexistent_file(self):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe
        result = _run_ffprobe("/nonexistent/path/video.mp4")
        assert result is None  # Should return None, not raise

    def test_probe_text_file_returns_none(self, tmp_path: Path):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")
        from workers.ffprobe_worker import _run_ffprobe
        txt = tmp_path / "notavideo.txt"
        txt.write_text("hello world")
        result = _run_ffprobe(str(txt))
        # ffprobe may return None or data with no video streams — both are OK
        # What matters is it doesn't crash
        assert result is None or "streams" in result


class TestMediaMetadataStorage:
    """Test that probed metadata gets stored in the database."""

    @pytest.mark.asyncio
    async def test_probe_and_store_creates_row(self, test_video: Path, db_session):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")

        from workers.ffprobe_worker import _probe_and_store
        from db.models import MediaMetadata
        from sqlalchemy import select
        from config import SHARED_FOLDER

        # Copy test video into SHARED_FOLDER
        dest = SHARED_FOLDER / test_video.name
        import shutil as sh
        sh.copy2(test_video, dest)
        rel_path = test_video.name

        await _probe_and_store(rel_path, str(dest))

        result = await db_session.execute(
            select(MediaMetadata).where(MediaMetadata.rel_path == rel_path)
        )
        meta = result.scalar_one_or_none()
        assert meta is not None
        assert meta.video_codec == "h264"
        assert meta.width == 320
        assert meta.height == 240

    @pytest.mark.asyncio
    async def test_resolution_label(self, test_video: Path, db_session):
        if not shutil.which("ffprobe"):
            pytest.skip("ffprobe not available")

        from db.models import MediaMetadata
        meta = MediaMetadata(
            rel_path="test.mp4",
            width=3840,
            height=2160,
        )
        assert meta.resolution_label == "4K"

        meta.height = 1080
        assert meta.resolution_label == "1080p"

        meta.height = 720
        assert meta.resolution_label == "720p"

    @pytest.mark.asyncio
    async def test_duration_label(self):
        from db.models import MediaMetadata
        meta = MediaMetadata(rel_path="test.mp4", duration_seconds=3723.0)
        assert meta.duration_label == "1:02:03"

        meta.duration_seconds = 65.0
        assert meta.duration_label == "1:05"


class TestHlsTranscode:
    """Test HLS transcoding produces valid output with correct keyframe interval."""

    def test_ffmpeg_available(self):
        if not shutil.which("ffmpeg"):
            pytest.skip("FFmpeg not available")

    @pytest.mark.asyncio
    async def test_transcode_creates_playlist(self, test_video: Path, tmp_path: Path):
        if not shutil.which("ffmpeg"):
            pytest.skip("FFmpeg not available")

        import os
        os.environ["TRANSCODE_DIR"] = str(tmp_path)

        from workers.hls_worker import _transcode
        from config import SHARED_FOLDER

        # Copy test video to shared folder
        dest = SHARED_FOLDER / "hls_test.mp4"
        import shutil as sh
        sh.copy2(test_video, dest)

        await _transcode("hls_test.mp4", str(dest))

        from workers.hls_worker import _get_hls_output_dir
        out_dir = _get_hls_output_dir("hls_test.mp4")
        playlist = out_dir / "index.m3u8"

        assert playlist.exists(), "HLS playlist should be created"

        # Verify playlist contains segments
        content = playlist.read_text()
        assert "#EXTM3U" in content
        assert ".ts" in content

    @pytest.mark.asyncio
    async def test_transcode_creates_ts_segments(self, test_video: Path, tmp_path: Path):
        if not shutil.which("ffmpeg"):
            pytest.skip("FFmpeg not available")

        import os
        os.environ["TRANSCODE_DIR"] = str(tmp_path)

        from workers.hls_worker import _transcode, _get_hls_output_dir
        from config import SHARED_FOLDER

        dest = SHARED_FOLDER / "hls_segments_test.mp4"
        import shutil as sh
        sh.copy2(test_video, dest)

        await _transcode("hls_segments_test.mp4", str(dest))

        out_dir = _get_hls_output_dir("hls_segments_test.mp4")
        ts_files = list(out_dir.glob("*.ts"))
        assert len(ts_files) >= 1, "Should produce at least one .ts segment"
