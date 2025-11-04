"""Unit tests for DriveChecker in migrate_v2.py.

Tests cover:
- DriveChecker initialization
- check_available with various scenarios (parent exists, permission denied, etc.)
- Edge cases for DriveChecker
"""

from pathlib import Path
from unittest import mock

import pytest

from migrate_v2 import DriveChecker


class TestDriveChecker:
    """Tests for DriveChecker class."""

    def test_initialization(self, tmp_path):
        """DriveChecker initializes with base path."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)
        assert checker.base_path == base_path

    def test_check_available_parent_does_not_exist(self, tmp_path, capsys):
        """check_available exits when parent directory does not exist."""
        # Create a path whose parent doesn't exist
        base_path = tmp_path / "nonexistent" / "s3_backup"
        checker = DriveChecker(base_path)

        with pytest.raises(SystemExit) as exc_info:
            checker.check_available()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "DRIVE NOT AVAILABLE" in captured.out
        assert "Expected:" in captured.out

    def test_check_available_parent_exists_creates_directory(self, tmp_path):
        """check_available creates base directory when parent exists."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Should not raise
        checker.check_available()

        # Directory should be created
        assert base_path.exists()
        assert base_path.is_dir()

    def test_check_available_directory_already_exists(self, tmp_path):
        """check_available succeeds if directory already exists."""
        base_path = tmp_path / "s3_backup"
        base_path.mkdir(parents=True)

        checker = DriveChecker(base_path)

        # Should not raise
        checker.check_available()
        assert base_path.exists()

    def test_check_available_permission_denied(self, tmp_path, capsys, monkeypatch):
        """check_available exits when directory creation raises PermissionError."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Mock mkdir to raise PermissionError
        with mock.patch.object(Path, "mkdir", side_effect=PermissionError()):
            with pytest.raises(SystemExit) as exc_info:
                checker.check_available()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "PERMISSION DENIED" in captured.out
        assert "Cannot write to destination:" in captured.out


class TestDriveCheckerEdgeCases:
    """Tests for edge cases in DriveChecker."""

    def test_check_available_creates_single_subdirectory(self, tmp_path):
        """check_available creates single subdirectory under existing parent."""
        nested_path = tmp_path / "s3_backup"
        checker = DriveChecker(nested_path)

        checker.check_available()

        # Directory should be created
        assert nested_path.exists()
        # Parent must already exist (requirement of check_available)
        assert nested_path.parent.exists()

    def test_check_available_idempotent(self, tmp_path):
        """check_available can be called multiple times safely."""
        base_path = tmp_path / "s3_backup"
        checker = DriveChecker(base_path)

        # Call twice
        checker.check_available()
        checker.check_available()

        # Should still exist
        assert base_path.exists()
