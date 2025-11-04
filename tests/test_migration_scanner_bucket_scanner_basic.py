"""Unit tests for BucketScanner class from migration_scanner.py - Basic operations"""

from datetime import datetime
from unittest import mock

import pytest

from migration_scanner import BucketScanner
from migration_state_v2 import MigrationStateV2, Phase


class TestBucketScannerInitialization:
    """Test BucketScanner initialization"""

    @pytest.fixture
    def mock_s3(self):
        """Create mock S3 client"""
        return mock.Mock()

    @pytest.fixture
    def mock_state(self):
        """Create mock MigrationStateV2"""
        return mock.Mock(spec=MigrationStateV2)

    def test_scanner_initialization(self, mock_s3, mock_state):
        """Test BucketScanner initialization"""
        scanner = BucketScanner(mock_s3, mock_state)
        assert scanner.s3 is mock_s3
        assert scanner.state is mock_state
        assert scanner.interrupted is False


class TestBucketScannerNoBuckets:
    """Test BucketScanner with no buckets"""

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

    def test_scan_all_buckets_with_no_buckets(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning when no buckets exist"""
        mock_s3.list_buckets.return_value = {"Buckets": []}

        scanner.scan_all_buckets()

        assert capsys.readouterr().out.count("PHASE 1/4: SCANNING BUCKETS") == 1
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)


class TestBucketScannerSingleBucket:
    """Test BucketScanner with single bucket"""

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

    def test_scan_all_buckets_with_single_bucket(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning with single bucket"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner.scan_all_buckets()

        mock_state.add_file.assert_called_once()
        mock_state.save_bucket_status.assert_called_once()
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)


class TestBucketScannerEmptyBucket:
    """Test BucketScanner with empty bucket"""

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

    def test_scan_all_buckets_handles_empty_bucket(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning empty bucket"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "empty-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [{}]

        scanner.scan_all_buckets()

        mock_state.add_file.assert_not_called()
        mock_state.save_bucket_status.assert_called_once_with(
            "empty-bucket", 0, 0, {}, scan_complete=True
        )


class TestBucketScannerFiltering:
    """Test BucketScanner bucket filtering"""

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

    def test_scan_all_buckets_filters_excluded_buckets(self, scanner, mock_s3, mock_state, capsys):
        """Test that excluded buckets are filtered out"""
        with mock.patch("migration_scanner.config.EXCLUDED_BUCKETS", ["excluded-bucket"]):
            mock_s3.list_buckets.return_value = {
                "Buckets": [
                    {"Name": "test-bucket"},
                    {"Name": "excluded-bucket"},
                ]
            }
            mock_s3.get_paginator.return_value.paginate.return_value = []

            scanner.scan_all_buckets()

            output = capsys.readouterr().out
            assert "Found 1 bucket(s)" in output
            assert "Excluded 1 bucket(s)" in output


class TestBucketScannerPagination:
    """Test BucketScanner pagination handling"""

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

    def test_scan_all_buckets_with_multiple_pages(self, scanner, mock_s3, mock_state):
        """Test scanning bucket with pagination"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            },
            {
                "Contents": [
                    {
                        "Key": "file2.txt",
                        "Size": 200,
                        "StorageClass": "GLACIER",
                        "LastModified": datetime.now(),
                    }
                ]
            },
        ]

        scanner.scan_all_buckets()

        assert mock_state.add_file.call_count == 2  # noqa: PLR2004
