"""Unit tests for BucketScanner class from migration_scanner.py - Basic operations"""

from datetime import datetime
from unittest import mock

import pytest

from migration_scanner import BucketScanner
from migration_state_v2 import MigrationStateV2, Phase


class TestBucketScanner:
    """Test BucketScanner class"""

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

    def test_scanner_initialization(self, mock_s3, mock_state):
        """Test BucketScanner initialization"""
        scanner = BucketScanner(mock_s3, mock_state)
        assert scanner.s3 is mock_s3
        assert scanner.state is mock_state
        assert scanner.interrupted is False

    def test_scan_all_buckets_with_no_buckets(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning when no buckets exist"""
        mock_s3.list_buckets.return_value = {"Buckets": []}

        scanner.scan_all_buckets()

        assert capsys.readouterr().out.count("PHASE 1/4: SCANNING BUCKETS") == 1
        mock_state.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)

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

    def test_scan_all_buckets_handles_empty_bucket(self, scanner, mock_s3, mock_state, capsys):
        """Test scanning empty bucket"""
        mock_s3.list_buckets.return_value = {"Buckets": [{"Name": "empty-bucket"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [{}]

        scanner.scan_all_buckets()

        mock_state.add_file.assert_not_called()
        mock_state.save_bucket_status.assert_called_once_with(
            "empty-bucket", 0, 0, {}, scan_complete=True
        )

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
        def interrupt_on_second_call(*args, **kwargs):
            scanner.interrupted = True

        mock_state.save_bucket_status.side_effect = interrupt_on_second_call

        scanner.scan_all_buckets()

        # Should only process first bucket
        assert mock_state.save_bucket_status.call_count == 1

    def test_scan_bucket_with_mixed_storage_classes(self, scanner, mock_s3, mock_state):
        """Test scanning bucket with multiple storage classes"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
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
            }
        ]

        scanner._scan_bucket("test-bucket")

        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1
        assert storage_classes["GLACIER"] == 1
        assert storage_classes["DEEP_ARCHIVE"] == 1

    def test_scan_bucket_accumulates_size(self, scanner, mock_s3, mock_state):
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

        scanner._scan_bucket("test-bucket")

        # Total size should be 3000
        call_args = mock_state.save_bucket_status.call_args
        assert call_args[0][2] == 3000  # noqa: PLR2004

    def test_scan_bucket_handles_missing_storage_class(self, scanner, mock_s3, mock_state):
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

        scanner._scan_bucket("test-bucket")

        # Should default to STANDARD
        storage_classes = mock_state.save_bucket_status.call_args[0][3]
        assert storage_classes["STANDARD"] == 1

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

        scanner._scan_bucket("test-bucket")

        # Should still call add_file with empty string etag
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == ""

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

        scanner._scan_bucket("test-bucket")

        # ETag should be stripped of quotes
        call_args = mock_state.add_file.call_args
        assert call_args[0][3] == "abc123"

    def test_scan_bucket_respects_interrupt(self, scanner, mock_s3, mock_state):
        """Test that _scan_bucket stops on interrupt"""
        scanner.s3.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 100,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(),
                    }
                ]
            }
        ]

        scanner.interrupted = True
        scanner._scan_bucket("test-bucket")

        mock_state.add_file.assert_not_called()
        mock_state.save_bucket_status.assert_not_called()

    def test_scan_bucket_respects_pagination_interrupt(self, scanner, mock_s3, mock_state):
        """Test interrupt during pagination"""
        page_count = 0

        def paginate_with_interrupt(*args, **kwargs):
            nonlocal page_count
            page_count += 1
            scanner.interrupted = True
            return [
                {
                    "Contents": [
                        {
                            "Key": f"file{page_count}.txt",
                            "Size": 100,
                            "StorageClass": "STANDARD",
                            "LastModified": datetime.now(),
                        }
                    ]
                }
            ]

        scanner.s3.get_paginator.return_value.paginate = paginate_with_interrupt

        scanner._scan_bucket("test-bucket")

        # Should only process first page before interrupt
        mock_state.save_bucket_status.assert_not_called()

    def test_scan_bucket_progress_output(self, scanner, mock_s3, mock_state, capsys):
        """Test progress output for large number of files"""
        files = []
        for i in range(20001):
            files.append(
                {
                    "Key": f"file{i}.txt",
                    "Size": 100,
                    "StorageClass": "STANDARD",
                    "LastModified": datetime.now(),
                }
            )

        scanner.s3.get_paginator.return_value.paginate.return_value = [{"Contents": files}]

        scanner._scan_bucket("test-bucket")

        output = capsys.readouterr().out
        # Should show progress at 10000 mark
        assert "20001" in output or "20,001" in output
