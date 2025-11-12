"""Unit tests for BucketScanner class from migration_scanner.py - Storage class handling"""

from datetime import datetime
from unittest import mock

import pytest

from migration_scanner import BucketScanner
from migration_state_v2 import MigrationStateV2
from tests.assertions import assert_equal


class TestBucketScannerInterruption:
    """Test BucketScanner interruption handling"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def scanner(self, mock_s3, mock_state):
        """Create BucketScanner instance"""
        return BucketScanner(mock_s3, mock_state)

    def test_scan_all_buckets_respects_interrupt_signal(self, scanner, mock_s3, mock_state):
        """Test that scan_all_buckets stops on interrupt"""
        mock_s3.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1"},
                {"Name": "bucket2"},
            ]
        }
        mock_s3.get_paginator.return_value.paginate.return_value = []

        # Interrupt after first bucket
        def interrupt_on_second_call(*_args, **_kwargs):
            scanner.interrupted = True

        mock_state.save_bucket_status.side_effect = interrupt_on_second_call

        scanner.scan_all_buckets()

        # Should only process first bucket
        assert mock_state.save_bucket_status.call_count == 1


class TestBucketScannerMixedStorageClasses:
    """Test BucketScanner with mixed storage classes"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def scanner(self, mock_s3, mock_state):
        """Create BucketScanner instance"""
        return BucketScanner(mock_s3, mock_state)

    def test_scan_bucket_with_mixed_storage_classes(self, scanner, mock_state):
        """Test scanning bucket with multiple storage classes"""
        files = [
            {
                "Key": "standard.txt",
                "Size": 100,
                "StorageClass": "STANDARD",
                "LastModified": datetime.now(),
            },
            {
                "Key": "glacier.txt",
                "Size": 200,
                "StorageClass": "GLACIER",
                "LastModified": datetime.now(),
            },
            {
                "Key": "deep_archive.txt",
                "Size": 300,
                "StorageClass": "DEEP_ARCHIVE",
                "LastModified": datetime.now(),
            },
        ]
        scanner.s3.get_paginator.return_value.paginate.return_value = [{"Contents": files}]

        scanner.scan_bucket("test-bucket")

        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1
        assert storage_classes["GLACIER"] == 1
        assert storage_classes["DEEP_ARCHIVE"] == 1


class TestBucketScannerMissingStorageClass:
    """Test BucketScanner with missing storage class"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def scanner(self, mock_s3, mock_state):
        """Create BucketScanner instance"""
        return BucketScanner(mock_s3, mock_state)

    def test_scan_bucket_handles_missing_storage_class(self, scanner, mock_state):
        """Test handling of objects without StorageClass field"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "LastModified": datetime.now(),
                        # StorageClass missing
                    }
                ]
            }
        ]

        scanner.scan_bucket("test-bucket")

        # Should default to STANDARD
        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1


class TestBucketScannerSizeAccumulation:
    """Test BucketScanner size accumulation"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    @pytest.fixture
    def scanner(self, mock_s3, mock_state):
        """Create BucketScanner instance"""
        return BucketScanner(mock_s3, mock_state)

    def test_scan_bucket_accumulates_size(self, scanner, mock_state):
        """Test that file sizes are accumulated correctly"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 1000,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    },
                    {
                        "Key": "file2.txt",
                        "Size": 2000,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    },
                ]
            }
        ]

        scanner.scan_bucket("test-bucket")

        # Total size should be 3000
        call_args = mock_state.save_bucket_status.call_args
        assert_equal(call_args[0][2], 3000)
