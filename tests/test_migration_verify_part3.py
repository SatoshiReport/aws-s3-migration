"""Unit tests for migration_verify.py - Part 3: BucketVerifier and BucketDeleter"""

import hashlib
from unittest import mock

import pytest

from migration_verify import BucketDeleter, BucketVerifier


class TestBucketVerifierSuccess:
    """Tests for BucketVerifier successful verification"""

    def test_verify_bucket_integration_succeeds(self, tmp_path):
        """Test complete bucket verification workflow"""
        # Setup
        bucket_path = tmp_path / "test-bucket"
        bucket_path.mkdir()
        (bucket_path / "file1.txt").write_bytes(b"content1")

        md5_1 = hashlib.md5(b"content1", usedforsecurity=False).hexdigest()

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


class TestBucketVerifierMissingPath:
    """Tests for BucketVerifier when local path is missing"""

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


class TestBucketVerifierMissingFiles:
    """Tests for BucketVerifier with missing files"""

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


class TestBucketVerifierChecksumMismatch:
    """Tests for BucketVerifier with checksum mismatches"""

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


class TestBucketDeleterSinglePage:
    """Tests for BucketDeleter with single page of objects"""

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
        assert len(call_args[1]["Delete"]["Objects"]) == 3  # noqa: PLR2004
        # Verify VersionId is included
        assert all("VersionId" in obj for obj in call_args[1]["Delete"]["Objects"])


class TestBucketDeleterMultiplePagesBasic:
    """Tests for BucketDeleter with multiple pages - basic functionality"""

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
        assert mock_s3.delete_objects.call_count == 3  # noqa: PLR2004


class TestBucketDeleterEmptyPages:
    """Tests for BucketDeleter handling empty pages"""

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
        assert mock_s3.delete_objects.call_count == 2  # noqa: PLR2004


class TestBucketDeleterBucketRemoval:
    """Tests for BucketDeleter bucket removal after objects deleted"""

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


class TestBucketDeleterObjectFormatting:
    """Tests for BucketDeleter object key formatting"""

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
