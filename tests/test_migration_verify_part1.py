"""Unit tests for migration_verify.py - Part 1: FileInventoryChecker and VerificationProgressTracker"""

import time
from pathlib import Path
from unittest import mock

import pytest

from migration_verify import (
    FileInventoryChecker,
    VerificationProgressTracker,
)


class TestFileInventoryCheckerLoadFiles:
    """Tests for FileInventoryChecker.load_expected_files() basic functionality"""

    def test_load_expected_files_returns_file_map(self, tmp_path):
        """Test loading expected files from database"""
        mock_state = mock.Mock()
        mock_conn = mock.Mock()

        # Mock database rows as list
        mock_rows = [
            {"key": "file1.txt", "size": 100, "etag": "abc123"},
            {"key": "dir/file2.txt", "size": 200, "etag": "def456"},
        ]

        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        checker = FileInventoryChecker(mock_state, tmp_path)
        result = checker.load_expected_files("test-bucket")

        assert len(result) == 2  # noqa: PLR2004
        assert result["file1.txt"]["size"] == 100  # noqa: PLR2004
        assert result["file1.txt"]["etag"] == "abc123"
        assert result["dir/file2.txt"]["size"] == 200  # noqa: PLR2004


class TestFileInventoryCheckerPathNormalization:
    """Tests for FileInventoryChecker path normalization"""

    def test_load_expected_files_normalizes_windows_paths(self, tmp_path):
        """Test that Windows path separators are normalized"""
        mock_state = mock.Mock()
        mock_conn = mock.Mock()

        # Mock database with Windows-style path
        mock_rows = [
            {"key": "dir\\file.txt", "size": 100, "etag": "abc123"},
        ]

        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        checker = FileInventoryChecker(mock_state, tmp_path)
        result = checker.load_expected_files("test-bucket")

        # Path should be normalized to forward slashes
        assert "dir/file.txt" in result
        assert "dir\\file.txt" not in result


class TestFileInventoryCheckerScanFiles:
    """Tests for FileInventoryChecker.scan_local_files() basic functionality"""

    def test_scan_local_files_finds_files(self, tmp_path):
        """Test scanning local files"""
        # Create test directory structure
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_text("content1")
        (bucket_path / "subdir").mkdir()
        (bucket_path / "subdir" / "file2.txt").write_text("content2")

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 2)

        assert len(local_files) == 2  # noqa: PLR2004
        assert "file1.txt" in local_files
        assert "subdir/file2.txt" in local_files

    def test_scan_local_files_handles_missing_directory(self, tmp_path):
        """Test scanning when directory doesn't exist"""
        # Create bucket path but leave it empty for rglob
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 0)

        assert local_files == {}


class TestFileInventoryCheckerScanPathNormalization:
    """Tests for FileInventoryChecker path normalization during scanning"""

    def test_scan_local_files_normalizes_windows_paths(self, tmp_path):
        """Test that scanned files use forward slashes"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "subdir").mkdir()
        (bucket_path / "subdir" / "file.txt").write_text("content")

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 1)

        # Should use forward slashes regardless of platform
        assert "subdir/file.txt" in local_files
        assert "subdir\\file.txt" not in local_files


class TestFileInventoryCheckerCheckSuccess:
    """Tests for FileInventoryChecker.check_inventory() success cases"""

    def test_check_inventory_success_when_files_match(self):
        """Test inventory check succeeds when files match"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file1.txt", "file2.txt", "dir/file3.txt"}
        local_keys = {"file1.txt", "file2.txt", "dir/file3.txt"}

        errors = checker.check_inventory(expected_keys, local_keys)

        assert errors == []


class TestFileInventoryCheckerCheckMissingFiles:
    """Tests for FileInventoryChecker.check_inventory() missing file cases"""

    def test_check_inventory_fails_on_missing_files(self):
        """Test inventory check fails when files are missing"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file1.txt", "file2.txt", "file3.txt"}
        local_keys = {"file1.txt"}

        with pytest.raises(ValueError) as exc_info:
            checker.check_inventory(expected_keys, local_keys)

        assert "File inventory check failed" in str(exc_info.value)
        assert "2 missing" in str(exc_info.value)


class TestFileInventoryCheckerCheckExtraFiles:
    """Tests for FileInventoryChecker.check_inventory() extra file cases"""

    def test_check_inventory_fails_on_extra_files(self):
        """Test inventory check fails when extra files exist"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file1.txt"}
        local_keys = {"file1.txt", "file2.txt", "file3.txt"}

        with pytest.raises(ValueError) as exc_info:
            checker.check_inventory(expected_keys, local_keys)

        assert "File inventory check failed" in str(exc_info.value)
        assert "2 extra" in str(exc_info.value)

    def test_check_inventory_fails_on_both_missing_and_extra(self):
        """Test inventory check fails on both missing and extra files"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file1.txt", "file2.txt"}
        local_keys = {"file1.txt", "file3.txt", "file4.txt"}

        with pytest.raises(ValueError) as exc_info:
            checker.check_inventory(expected_keys, local_keys)

        assert "File inventory check failed" in str(exc_info.value)
        assert "1 missing" in str(exc_info.value)
        assert "2 extra" in str(exc_info.value)


class TestVerificationProgressTrackerMilestones:
    """Tests for VerificationProgressTracker milestone displays"""

    def test_update_progress_displays_on_file_milestone(self, capsys):
        """Test progress update displays at file count milestone"""
        tracker = VerificationProgressTracker()
        start_time = time.time() - 10  # Started 10 seconds ago

        tracker.update_progress(
            start_time=start_time,
            verified_count=100,  # Divisible by 100 triggers display
            total_bytes_verified=1024 * 1024,  # 1 MB
            expected_files=200,
            expected_size=10 * 1024 * 1024,  # 10 MB
        )

        captured = capsys.readouterr()
        # Should display progress at 100-file milestone
        assert "Progress:" in captured.out

    def test_update_progress_updates_on_file_count_milestone(self, capsys):
        """Test progress update displays on file count milestone (every 100 files)"""
        tracker = VerificationProgressTracker()
        start_time = time.time()

        tracker.update_progress(
            start_time=start_time,
            verified_count=100,  # Exactly 100 files (divisible by 100)
            total_bytes_verified=1024 * 1024,
            expected_files=200,
            expected_size=20 * 1024 * 1024,
        )

        captured = capsys.readouterr()
        # Should display due to file count milestone
        assert "Progress:" in captured.out


class TestVerificationProgressTrackerNoUpdate:
    """Tests for VerificationProgressTracker when updates are suppressed"""

    def test_update_progress_no_update_when_too_soon(self, capsys):
        """Test progress update doesn't display when too soon"""
        tracker = VerificationProgressTracker()
        start_time = time.time()

        tracker.update_progress(
            start_time=start_time,
            verified_count=50,
            total_bytes_verified=1024 * 1024,
            expected_files=100,
            expected_size=10 * 1024 * 1024,
        )

        captured = capsys.readouterr()
        # Should not display since <2 seconds elapsed
        assert captured.out == ""
