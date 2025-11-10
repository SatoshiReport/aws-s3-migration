"""Unit tests for migration_verify.py - Part 5: Edge Cases (Part 2) and Integration Tests"""

import hashlib
import time
from unittest import mock

import pytest

from migration_verify import (
    BucketDeleter,
    BucketVerifier,
    FileInventoryChecker,
    VerificationProgressTracker,
)
from tests.assertions import assert_equal


def test_update_progress_with_large_file_counts(capsys):
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


def test_verify_files_all_file_count_milestone_updates(capsys):
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


class TestBucketDeleterEmptyBuckets:
    """Tests for BucketDeleter with empty buckets"""

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


def test_scan_large_number_of_files_with_progress_output(tmp_path):
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

    assert_equal(len(local_files), 10100)


class TestBucketDeleterProgressUpdates:
    """Tests for BucketDeleter progress update functionality"""

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
        assert_equal(mock_s3.delete_objects.call_count, 3)


def test_full_verification_workflow(tmp_path):
    """Test complete verification workflow from inventory to checksums"""
    # Setup
    bucket_path = tmp_path / "test-bucket"
    bucket_path.mkdir()
    (bucket_path / "file1.txt").write_bytes(b"content")
    (bucket_path / "file2.txt").write_bytes(b"data")

    md5_1 = hashlib.md5(b"content", usedforsecurity=False).hexdigest()
    md5_2 = hashlib.md5(b"data", usedforsecurity=False).hexdigest()

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

    assert_equal(results["verified_count"], 2)
    assert_equal(results["checksum_verified"], 2)
    assert_equal(results["local_file_count"], 2)


def test_error_handling_across_components(tmp_path):
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
