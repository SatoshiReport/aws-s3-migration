"""Comprehensive unit tests for migration_verify.py"""

import hashlib
import time
from pathlib import Path
from unittest import mock

import pytest

from migration_verify import (
    BucketDeleter,
    BucketVerifier,
    FileChecksumVerifier,
    FileInventoryChecker,
    VerificationProgressTracker,
)


class TestFileInventoryChecker:
    """Tests for FileInventoryChecker class"""

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

        assert len(result) == 2
        assert result["file1.txt"]["size"] == 100
        assert result["file1.txt"]["etag"] == "abc123"
        assert result["dir/file2.txt"]["size"] == 200

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

        assert len(local_files) == 2
        assert "file1.txt" in local_files
        assert "subdir/file2.txt" in local_files

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

    def test_scan_local_files_handles_missing_directory(self, tmp_path):
        """Test scanning when directory doesn't exist"""
        # Create bucket path but leave it empty for rglob
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 0)

        assert local_files == {}

    def test_check_inventory_success_when_files_match(self):
        """Test inventory check succeeds when files match"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file1.txt", "file2.txt", "dir/file3.txt"}
        local_keys = {"file1.txt", "file2.txt", "dir/file3.txt"}

        errors = checker.check_inventory(expected_keys, local_keys)

        assert errors == []

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


class TestVerificationProgressTracker:
    """Tests for VerificationProgressTracker class"""

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


class TestFileChecksumVerifier:
    """Tests for FileChecksumVerifier class"""

    def test_verify_files_integration_with_valid_files(self, tmp_path):
        """Test verification of valid single-part files"""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test content 1")
        file2 = tmp_path / "file2.txt"
        file2.write_bytes(b"test content 2")

        # Calculate MD5 hashes
        md5_1 = hashlib.md5(b"test content 1").hexdigest()
        md5_2 = hashlib.md5(b"test content 2").hexdigest()

        local_files = {"file1.txt": file1, "file2.txt": file2}
        expected_file_map = {
            "file1.txt": {"size": 14, "etag": md5_1},
            "file2.txt": {"size": 14, "etag": md5_2},
        }

        verifier = FileChecksumVerifier()
        results = verifier.verify_files(
            local_files=local_files,
            expected_file_map=expected_file_map,
            expected_files=2,
            expected_size=28,
        )

        assert results["verified_count"] == 2
        assert results["size_verified"] == 2
        assert results["checksum_verified"] == 2
        assert results["total_bytes_verified"] == 28

    def test_verify_single_file_with_size_mismatch(self, tmp_path):
        """Test verification fails on size mismatch"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content")

        local_files = {"file1.txt": file1}
        expected_file_map = {"file1.txt": {"size": 999, "etag": "abc123"}}
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_single_file("file1.txt", local_files, expected_file_map, stats)

        assert len(stats["verification_errors"]) == 1
        assert "size mismatch" in stats["verification_errors"][0]
        assert stats["verified_count"] == 0

    def test_verify_single_file_with_checksum_mismatch(self, tmp_path):
        """Test verification fails on checksum mismatch"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content")

        wrong_hash = "0" * 32

        local_files = {"file1.txt": file1}
        expected_file_map = {"file1.txt": {"size": 7, "etag": wrong_hash}}
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_single_file("file1.txt", local_files, expected_file_map, stats)

        assert len(stats["verification_errors"]) == 1
        assert "checksum mismatch" in stats["verification_errors"][0]
        assert stats["size_verified"] == 1
        assert stats["verified_count"] == 0

    def test_verify_multipart_file_with_hyphen_in_etag(self, tmp_path):
        """Test verification of multipart file (contains hyphen)"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"multipart content")

        local_files = {"file1.txt": file1}
        expected_file_map = {
            "file1.txt": {"size": 17, "etag": "abc123-2"}
        }  # Hyphen indicates multipart
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_single_file("file1.txt", local_files, expected_file_map, stats)

        # Multipart files are verified via SHA256 health check
        assert stats["verified_count"] == 1
        assert stats["checksum_verified"] == 1

    def test_verify_singlepart_file_succeeds(self, tmp_path):
        """Test verification of single-part file succeeds"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test")

        md5_hash = hashlib.md5(b"test").hexdigest()
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_singlepart_file("file1.txt", file1, md5_hash, stats)

        assert stats["verified_count"] == 1
        assert stats["checksum_verified"] == 1

    def test_verify_singlepart_file_fails_on_checksum_mismatch(self, tmp_path):
        """Test single-part verification fails on checksum mismatch"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test")

        wrong_hash = "0" * 32
        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_singlepart_file("file1.txt", file1, wrong_hash, stats)

        assert len(stats["verification_errors"]) == 1
        assert "checksum mismatch" in stats["verification_errors"][0]
        assert stats["verified_count"] == 0

    def test_verify_singlepart_file_handles_read_error(self, tmp_path):
        """Test single-part verification handles file read errors"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test")

        # Make file unreadable (remove read permissions)
        file1.chmod(0o000)

        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_singlepart_file("file1.txt", file1, "abc123", stats)

        # Restore permissions for cleanup
        file1.chmod(0o644)

        assert len(stats["verification_errors"]) == 1
        assert "checksum computation failed" in stats["verification_errors"][0]

    def test_verify_multipart_file_handles_read_error(self, tmp_path):
        """Test multipart verification handles file read errors"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test")

        # Make file unreadable
        file1.chmod(0o000)

        stats = {
            "verified_count": 0,
            "size_verified": 0,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_multipart_file("file1.txt", file1, stats)

        # Restore permissions for cleanup
        file1.chmod(0o644)

        assert len(stats["verification_errors"]) == 1
        assert "file health check failed" in stats["verification_errors"][0]

    def test_compute_etag_matches_valid_hash(self, tmp_path):
        """Test ETag computation matches provided hash"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test content")

        md5_hash = hashlib.md5(b"test content").hexdigest()

        verifier = FileChecksumVerifier()
        computed, is_match = verifier._compute_etag(file1, md5_hash)

        assert is_match is True
        assert computed == md5_hash

    def test_compute_etag_detects_mismatch(self, tmp_path):
        """Test ETag computation detects mismatches"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test content")

        wrong_hash = "0" * 32

        verifier = FileChecksumVerifier()
        computed, is_match = verifier._compute_etag(file1, wrong_hash)

        assert is_match is False
        assert computed != wrong_hash

    def test_compute_etag_strips_quotes_from_etag(self, tmp_path):
        """Test ETag computation handles quoted ETags from S3"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"test")

        md5_hash = hashlib.md5(b"test").hexdigest()
        quoted_etag = f'"{md5_hash}"'

        verifier = FileChecksumVerifier()
        computed, is_match = verifier._compute_etag(file1, quoted_etag)

        assert is_match is True

    def test_verify_files_raises_on_verification_errors(self, tmp_path):
        """Test verify_files raises exception on verification errors"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content")

        local_files = {"file1.txt": file1}
        expected_file_map = {"file1.txt": {"size": 999, "etag": "abc123"}}

        verifier = FileChecksumVerifier()

        with pytest.raises(ValueError) as exc_info:
            verifier.verify_files(
                local_files=local_files,
                expected_file_map=expected_file_map,
                expected_files=1,
                expected_size=999,
            )

        assert "Verification failed" in str(exc_info.value)

    def test_verify_files_handles_large_files(self, tmp_path):
        """Test verification handles large files with chunked reading"""
        # Create a 20 MB file (will be read in 8 MB chunks)
        file1 = tmp_path / "large_file.txt"
        chunk_size = 8 * 1024 * 1024
        file1.write_bytes(b"x" * (chunk_size * 2 + 1000))

        md5_hash = hashlib.md5()
        with open(file1, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                md5_hash.update(chunk)
        computed_hash = md5_hash.hexdigest()

        local_files = {"large_file.txt": file1}
        expected_file_map = {
            "large_file.txt": {"size": chunk_size * 2 + 1000, "etag": computed_hash}
        }

        verifier = FileChecksumVerifier()
        results = verifier.verify_files(
            local_files=local_files,
            expected_file_map=expected_file_map,
            expected_files=1,
            expected_size=chunk_size * 2 + 1000,
        )

        assert results["verified_count"] == 1
        assert results["checksum_verified"] == 1


class TestBucketVerifier:
    """Tests for BucketVerifier class"""

    def test_verify_bucket_integration_succeeds(self, tmp_path):
        """Test complete bucket verification workflow"""
        # Setup
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content1")

        md5_1 = hashlib.md5(b"content1").hexdigest()

        # Mock state
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 1,
            "total_size": 8,
        }

        mock_conn = mock.Mock()
        mock_rows = [
            {"key": "file1.txt", "size": 8, "etag": md5_1},
        ]
        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)
        results = verifier.verify_bucket("test-bucket")

        assert results["verified_count"] == 1
        assert results["local_file_count"] == 1
        assert results["checksum_verified"] == 1

    def test_verify_bucket_fails_when_local_path_missing(self, tmp_path):
        """Test verification fails when local path doesn't exist"""
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 1,
            "total_size": 100,
        }

        verifier = BucketVerifier(mock_state, tmp_path)

        with pytest.raises(FileNotFoundError):
            verifier.verify_bucket("nonexistent-bucket")

    def test_verify_bucket_fails_on_missing_files(self, tmp_path):
        """Test verification fails when files are missing"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content1")

        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 2,
            "total_size": 16,
        }

        mock_conn = mock.Mock()
        mock_rows = [
            {"key": "file1.txt", "size": 8, "etag": "abc123"},
            {"key": "file2.txt", "size": 8, "etag": "def456"},  # Missing locally
        ]
        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)

        with pytest.raises(ValueError) as exc_info:
            verifier.verify_bucket("test-bucket")

        assert "File inventory check failed" in str(exc_info.value)

    def test_verify_bucket_fails_on_checksum_mismatch(self, tmp_path):
        """Test verification fails on checksum mismatch"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content1")

        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 1,
            "total_size": 8,
        }

        mock_conn = mock.Mock()
        wrong_hash = "0" * 32
        mock_rows = [
            {"key": "file1.txt", "size": 8, "etag": wrong_hash},
        ]
        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)

        with pytest.raises(ValueError) as exc_info:
            verifier.verify_bucket("test-bucket")

        assert "Verification failed" in str(exc_info.value)


class TestBucketDeleter:
    """Tests for BucketDeleter class"""

    def test_delete_bucket_single_page(self):
        """Test deleting bucket with single page of objects"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 3}

        # Mock paginator with single page (list_object_versions format)
        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {
                "Versions": [
                    {"Key": "file1.txt", "VersionId": "v1"},
                    {"Key": "file2.txt", "VersionId": "v2"},
                    {"Key": "file3.txt", "VersionId": "v3"},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Verify delete_objects was called
        mock_s3.delete_objects.assert_called_once()
        call_args = mock_s3.delete_objects.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert len(call_args[1]["Delete"]["Objects"]) == 3
        # Verify VersionId is included
        assert all("VersionId" in obj for obj in call_args[1]["Delete"]["Objects"])

    def test_delete_bucket_multiple_pages(self):
        """Test deleting bucket with multiple pages of objects"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 6}

        # Mock paginator with multiple pages (list_object_versions format)
        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {
                "Versions": [
                    {"Key": "file1.txt", "VersionId": "v1"},
                    {"Key": "file2.txt", "VersionId": "v2"},
                ]
            },
            {
                "Versions": [
                    {"Key": "file3.txt", "VersionId": "v3"},
                    {"Key": "file4.txt", "VersionId": "v4"},
                ]
            },
            {
                "Versions": [
                    {"Key": "file5.txt", "VersionId": "v5"},
                    {"Key": "file6.txt", "VersionId": "v6"},
                ]
            },
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Verify delete_objects was called 3 times (once per page)
        assert mock_s3.delete_objects.call_count == 3

    def test_delete_bucket_handles_empty_pages(self):
        """Test deleting bucket handles pages with no Versions"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 2}

        # Mock paginator with mixed pages (list_object_versions format)
        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {"Versions": [{"Key": "file1.txt", "VersionId": "v1"}]},
            {},  # Empty page (no Versions key)
            {"Versions": [{"Key": "file2.txt", "VersionId": "v2"}]},
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Should only call delete_objects twice (skipping empty page)
        assert mock_s3.delete_objects.call_count == 2

    def test_delete_bucket_calls_delete_bucket_method(self):
        """Test that delete_bucket is called to remove empty bucket"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 1}

        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {"Versions": [{"Key": "file1.txt", "VersionId": "v1"}]}
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Verify delete_bucket was called
        mock_s3.delete_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_delete_bucket_formats_object_keys_correctly(self):
        """Test that object keys are formatted correctly for deletion"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 2}

        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {
                "Versions": [
                    {"Key": "path/to/file1.txt", "VersionId": "v1"},
                    {"Key": "path/to/file2.txt", "VersionId": "v2"},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Verify keys and version IDs are in correct format
        call_args = mock_s3.delete_objects.call_args
        objects = call_args[1]["Delete"]["Objects"]
        assert objects[0]["Key"] == "path/to/file1.txt"
        assert objects[0]["VersionId"] == "v1"
        assert objects[1]["Key"] == "path/to/file2.txt"
        assert objects[1]["VersionId"] == "v2"

    def test_delete_bucket_large_batch(self):
        """Test deleting bucket with large batch of objects"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 1500}

        # Create mock paginator with large batch (list_object_versions format)
        large_batch = {
            "Versions": [{"Key": f"file{i}.txt", "VersionId": f"v{i}"} for i in range(1500)]
        }
        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [large_batch]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Verify delete_objects was called with all objects
        call_args = mock_s3.delete_objects.call_args
        assert len(call_args[1]["Delete"]["Objects"]) == 1500

    def test_delete_bucket_updates_progress(self):
        """Test that delete progress is displayed"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 5}

        # Create multiple pages to trigger progress updates (list_object_versions format)
        mock_paginator = mock.Mock()
        pages = [
            {
                "Versions": [
                    {"Key": f"file{i}.txt", "VersionId": f"v{i}"}
                    for i in range(j * 1000, (j + 1) * 1000)
                ]
            }
            for j in range(5)
        ]
        mock_paginator.paginate.return_value = pages
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)

        # Should not raise an error
        deleter.delete_bucket("test-bucket")

        # Should have called delete_objects for each page
        assert mock_s3.delete_objects.call_count == 5


class TestEdgeCases:
    """Tests for edge cases and error path coverage"""

    def test_check_inventory_shows_many_missing_files(self):
        """Test inventory check shows summary when >10 missing files"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {f"file{i}.txt" for i in range(20)}
        local_keys = {"file0.txt", "file1.txt"}

        with pytest.raises(ValueError) as exc_info:
            checker.check_inventory(expected_keys, local_keys)

        assert "18 missing" in str(exc_info.value)

    def test_check_inventory_shows_many_extra_files(self):
        """Test inventory check shows summary when >10 extra files"""
        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, Path("/tmp"))

        expected_keys = {"file0.txt", "file1.txt"}
        local_keys = {f"file{i}.txt" for i in range(20)}

        with pytest.raises(ValueError) as exc_info:
            checker.check_inventory(expected_keys, local_keys)

        assert "18 extra" in str(exc_info.value)

    def test_verify_files_shows_many_verification_errors(self, tmp_path):
        """Test verify_files shows summary when >10 verification errors"""
        # Create files with size mismatches
        files = {}
        expected_map = {}
        for i in range(15):
            file_path = tmp_path / f"file{i}.txt"
            file_path.write_bytes(b"content")
            files[f"file{i}.txt"] = file_path
            expected_map[f"file{i}.txt"] = {"size": 999, "etag": "abc123"}

        verifier = FileChecksumVerifier()

        with pytest.raises(ValueError) as exc_info:
            verifier.verify_files(
                local_files=files,
                expected_file_map=expected_map,
                expected_files=15,
                expected_size=15 * 999,
            )

        assert "15 file(s) with issues" in str(exc_info.value)

    def test_scan_local_files_with_no_progress_needed(self, tmp_path):
        """Test scanning <10000 files doesn't show progress"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        # Create 5 files (less than 10000)
        for i in range(5):
            (bucket_path / f"file{i}.txt").write_text(f"content{i}")

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 5)

        assert len(local_files) == 5

    def test_update_progress_with_large_file_counts(self, capsys):
        """Test progress update with large file counts"""
        tracker = VerificationProgressTracker()
        start_time = time.time() - 10

        # Test with 1 million files
        tracker.update_progress(
            start_time=start_time,
            verified_count=500000,
            total_bytes_verified=1024 * 1024 * 1024,  # 1 GB
            expected_files=1000000,
            expected_size=2048 * 1024 * 1024,  # 2 GB
        )

        captured = capsys.readouterr()
        # Should display progress with large counts
        assert "Progress:" in captured.out

    def test_verify_files_count_mismatch_in_verify_bucket(self, tmp_path):
        """Test that BucketVerifier detects verified count mismatch"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content1")

        md5_1 = hashlib.md5(b"content1").hexdigest()

        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 2,  # Says 2 files but only has 1
            "total_size": 16,
        }

        mock_conn = mock.Mock()
        mock_rows = [
            {"key": "file1.txt", "size": 8, "etag": md5_1},
            {"key": "file2.txt", "size": 8, "etag": "def456"},  # Missing
        ]
        mock_conn.execute.return_value = mock_rows

        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)

        # Should fail at inventory check because file2.txt is missing
        with pytest.raises(ValueError):
            verifier.verify_bucket("test-bucket")

    def test_delete_bucket_with_zero_objects(self):
        """Test deleting bucket with no objects"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 0}

        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = []
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("empty-bucket")

        # Should still call delete_bucket to remove the empty bucket
        mock_s3.delete_bucket.assert_called_once_with(Bucket="empty-bucket")

    def test_verify_multipart_file_verifies_checksum(self, tmp_path):
        """Test multipart file verification updates stats correctly"""
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"multipart content here")

        stats = {
            "verified_count": 0,
            "size_verified": 1,
            "checksum_verified": 0,
            "total_bytes_verified": 0,
            "verification_errors": [],
        }

        verifier = FileChecksumVerifier()
        verifier._verify_multipart_file("file1.txt", file1, stats)

        assert stats["verified_count"] == 1
        assert stats["checksum_verified"] == 1

    def test_compute_etag_with_empty_file(self, tmp_path):
        """Test ETag computation for empty file"""
        file1 = tmp_path / "empty.txt"
        file1.write_bytes(b"")

        md5_hash = hashlib.md5(b"").hexdigest()

        verifier = FileChecksumVerifier()
        computed, is_match = verifier._compute_etag(file1, md5_hash)

        assert is_match is True
        assert computed == md5_hash

    def test_verify_files_with_mixed_single_and_multipart(self, tmp_path):
        """Test verification of files with mixed part types"""
        # Create single-part file
        file1 = tmp_path / "singlepart.txt"
        file1.write_bytes(b"single")

        # Create multipart file
        file2 = tmp_path / "multipart.txt"
        file2.write_bytes(b"multipart")

        md5_1 = hashlib.md5(b"single").hexdigest()

        local_files = {
            "singlepart.txt": file1,
            "multipart.txt": file2,
        }
        expected_file_map = {
            "singlepart.txt": {"size": 6, "etag": md5_1},
            "multipart.txt": {"size": 9, "etag": "def456-2"},  # Multipart (has hyphen)
        }

        verifier = FileChecksumVerifier()
        results = verifier.verify_files(
            local_files=local_files,
            expected_file_map=expected_file_map,
            expected_files=2,
            expected_size=15,
        )

        assert results["verified_count"] == 2
        assert results["checksum_verified"] == 2

    def test_scan_large_number_of_files_with_progress_output(self, tmp_path):
        """Test scanning with many files to trigger progress output"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()

        # Create 10100 files to trigger progress output (>10000)
        for i in range(10100):
            subdir = bucket_path / f"dir{i // 100}"
            subdir.mkdir(exist_ok=True)
            (subdir / f"file{i}.txt").write_text(f"content{i}")

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        local_files = checker.scan_local_files("test-bucket", 10100)

        assert len(local_files) == 10100

    def test_delete_bucket_with_pagination_triggers_progress(self):
        """Test delete progress update at 1000 object intervals"""
        mock_s3 = mock.Mock()
        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {"file_count": 2500}

        # Create 3 pages with 1000, 1000, 500 objects (list_object_versions format)
        mock_paginator = mock.Mock()
        mock_paginator.paginate.return_value = [
            {"Versions": [{"Key": f"file{i}.txt", "VersionId": f"v{i}"} for i in range(1000)]},
            {
                "Versions": [
                    {"Key": f"file{i}.txt", "VersionId": f"v{i}"} for i in range(1000, 2000)
                ]
            },
            {
                "Versions": [
                    {"Key": f"file{i}.txt", "VersionId": f"v{i}"} for i in range(2000, 2500)
                ]
            },
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        deleter = BucketDeleter(mock_s3, mock_state)
        deleter.delete_bucket("test-bucket")

        # Should be called 3 times (one per page)
        assert mock_s3.delete_objects.call_count == 3

    def test_scan_files_with_equal_expected_files(self, tmp_path):
        """Test scanning when actual files equal expected files"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()

        # Create exactly 100 files
        for i in range(100):
            (bucket_path / f"file{i}.txt").write_text(f"content{i}")

        mock_state = mock.Mock()
        checker = FileInventoryChecker(mock_state, tmp_path)

        # Tell it to expect exactly 100 files
        local_files = checker.scan_local_files("test-bucket", 100)

        assert len(local_files) == 100

    def test_verify_files_all_file_count_milestone_updates(self, capsys):
        """Test progress updates at every 100-file milestone"""
        tracker = VerificationProgressTracker()
        current_time = time.time()

        # Verify that exactly 100 files triggers an update
        tracker.update_progress(
            start_time=current_time,
            verified_count=100,
            total_bytes_verified=1024,
            expected_files=1000,
            expected_size=10240,
        )

        captured = capsys.readouterr()
        # Should have updated due to file count milestone
        assert "Progress:" in captured.out


class TestIntegration:
    """Integration tests combining multiple components"""

    def test_full_verification_workflow(self, tmp_path):
        """Test complete verification workflow from inventory to checksums"""
        # Setup
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content")
        (bucket_path / "file2.txt").write_bytes(b"data")

        md5_1 = hashlib.md5(b"content").hexdigest()
        md5_2 = hashlib.md5(b"data").hexdigest()

        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 2,
            "total_size": 11,
        }

        mock_conn = mock.Mock()
        mock_rows = [
            {"key": "file1.txt", "size": 7, "etag": md5_1},
            {"key": "file2.txt", "size": 4, "etag": md5_2},
        ]
        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)
        results = verifier.verify_bucket("test-bucket")

        assert results["verified_count"] == 2
        assert results["checksum_verified"] == 2
        assert results["local_file_count"] == 2

    def test_error_handling_across_components(self, tmp_path):
        """Test error handling flows through components"""
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content")

        mock_state = mock.Mock()
        mock_state.get_bucket_info.return_value = {
            "file_count": 1,
            "total_size": 100,
        }

        mock_conn = mock.Mock()
        mock_rows = [
            {"key": "file1.txt", "size": 100, "etag": "abc123"},  # Wrong size
        ]
        mock_conn.execute.return_value = mock_rows

        # Use MagicMock for context manager support
        mock_cm = mock.MagicMock()
        mock_cm.__enter__.return_value = mock_conn
        mock_cm.__exit__.return_value = False
        mock_state.db_conn.get_connection.return_value = mock_cm

        verifier = BucketVerifier(mock_state, tmp_path)

        with pytest.raises(ValueError):
            verifier.verify_bucket("test-bucket")
