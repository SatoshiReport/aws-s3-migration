"""Unit tests for BucketScanner class from migration_scanner.py - ETag handling"""

from datetime import datetime
from unittest import mock

import pytest

from migration_scanner import BucketScanner
from migration_state_v2 import MigrationStateV2


class TestBucketScannerMissingETag:
    """Test BucketScanner with missing ETag"""

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

    def test_scan_bucket_handles_missing_etag(self, scanner, mock_s3, mock_state):
        """Test handling of objects without ETag field"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                        # ETag missing
                    }
                ]
            }
        ]

        scanner.scan_bucket("test-bucket")

        # Should still call add_file with empty string etag
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == ""


class TestBucketScannerETagQuotes:
    """Test BucketScanner ETag quote stripping"""

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

    def test_scan_bucket_strips_etag_quotes(self, scanner, mock_s3, mock_state):
        """Test that ETags are stripped of quotes"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner.scan_bucket("test-bucket")

        # ETag should be stripped of quotes
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == "abc123"
