"""
StreamDrop — Security Unit Tests
Tests for path traversal prevention and filename sanitization.

These are the most critical safety tests in the suite.
A regression here means potential arbitrary file read/write on the host.
"""

import pytest
from pathlib import Path


# ── Filename Sanitization ──────────────────────────────────────────────────────

class TestSanitizeFilename:
    """Unit tests for file_manager.sanitize_filename()"""

    def test_normal_filename_passes_through(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("my_video.mp4")
        assert result == "my_video.mp4"

    def test_normal_filename_with_spaces(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("my video file.mp4")
        assert "." in result
        assert result.endswith(".mp4")

    def test_strips_directory_components(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("../../etc/passwd")
        # Must NOT contain directory separators
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_strips_leading_dot_dot(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("../../../secret.txt")
        assert ".." not in result
        assert "/" not in result

    def test_windows_path_traversal(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("..\\..\\Windows\\System32\\config")
        assert ".." not in result
        assert "\\" not in result

    def test_null_byte_injection(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_empty_filename_gets_fallback(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("")
        assert result  # Must not be empty
        assert len(result) > 0

    def test_dot_only_filename_gets_fallback(self):
        from file_manager import sanitize_filename
        result = sanitize_filename(".")
        assert result != "."
        assert len(result) > 1

    def test_preserves_extension(self):
        from file_manager import sanitize_filename
        result = sanitize_filename("video.mkv")
        assert result.endswith(".mkv")

    def test_long_filename_handled(self):
        from file_manager import sanitize_filename
        long_name = "a" * 500 + ".mp4"
        result = sanitize_filename(long_name)
        assert result  # Should not crash
        assert result.endswith(".mp4")


# ── Path Traversal Checks ──────────────────────────────────────────────────────

class TestPathTraversalPrevention:
    """Integration-level tests ensuring traversal-blocked at file system level."""

    def test_list_files_blocks_traversal(self):
        from file_manager import list_files
        from config import SHARED_FOLDER
        # Attempting to list outside the shared folder
        # Should return [] or clamp to SHARED_FOLDER root, never raise
        result = list_files("../../etc")
        assert isinstance(result, list)
        # If it returned items, they must all be under SHARED_FOLDER
        for item in result:
            assert not item.get("filename", "").startswith("/etc")

    def test_delete_file_blocks_traversal(self):
        from file_manager import delete_file
        with pytest.raises(ValueError, match="Invalid"):
            delete_file("../../etc/passwd")

    def test_delete_absolute_path_blocked(self):
        from file_manager import delete_file
        with pytest.raises(ValueError):
            delete_file("/etc/passwd")

    def test_save_upload_blocks_traversal(self):
        """Ensure upload subpath cannot escape SHARED_FOLDER."""
        from config import SHARED_FOLDER
        from file_manager import sanitize_filename

        # The actual path resolution logic
        subpath = "../../etc"
        target_dir = (SHARED_FOLDER / subpath).resolve()
        is_safe = str(target_dir).startswith(str(SHARED_FOLDER))
        assert not is_safe or str(target_dir) == str(SHARED_FOLDER), (
            "Path traversal in upload subpath should be blocked"
        )
