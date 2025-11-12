"""Unit tests for BucketScanner class from migration_scanner.py - Basic operations"""

from datetime import datetime
from unittest import mock

from migration_scanner import BucketScanner
from migration_state_v2 import Phase
from tests.assertions import assert_equal


def test_scanner_initialization(s3_mock, state_mock):
    """Test BucketScanner initialization"""
    scanner = BucketScanner(s3_mock, state_mock)
    assert scanner.s3 is s3_mock
    assert scanner.state is state_mock
    assert scanner.interrupted is False


def test_scan_all_buckets_with_no_buckets(scanner, s3_mock, state_mock, capsys):
    """Test scanning when no buckets exist"""
    s3_mock.list_buckets.return_value = {"Buckets": []}

    scanner.scan_all_buckets()

    assert capsys.readouterr().out.count("PHASE 1/4: SCANNING BUCKETS") == 1
    state_mock.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)


def test_scan_all_buckets_with_single_bucket(scanner, s3_mock, state_mock):
    """Test scanning with single bucket"""
    s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
    s3_mock.get_paginator.return_value.paginate.return_value = [
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

    state_mock.add_file.assert_called_once()
    state_mock.save_bucket_status.assert_called_once()
    state_mock.set_current_phase.assert_called_once_with(Phase.GLACIER_RESTORE)


def test_scan_all_buckets_handles_empty_bucket(scanner, s3_mock, state_mock):
    """Test scanning empty bucket"""
    s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "empty-bucket"}]}
    s3_mock.get_paginator.return_value.paginate.return_value = [{}]

    scanner.scan_all_buckets()

    state_mock.add_file.assert_not_called()
    state_mock.save_bucket_status.assert_called_once_with(
        "empty-bucket", 0, 0, {}, scan_complete=True
    )


def test_scan_all_buckets_filters_excluded_buckets(scanner, s3_mock, capsys):
    """Test that excluded buckets are filtered out"""
    with mock.patch("migration_scanner.config.EXCLUDED_BUCKETS", ["excluded-bucket"]):
        s3_mock.list_buckets.return_value = {
            "Buckets": [
                {"Name": "test-bucket"},
                {"Name": "excluded-bucket"},
            ]
        }
        s3_mock.get_paginator.return_value.paginate.return_value = []

        scanner.scan_all_buckets()

        output = capsys.readouterr().out
        assert "Found 1 bucket(s)" in output
        assert "Excluded 1 bucket(s)" in output


def test_scan_all_buckets_with_multiple_pages(scanner, s3_mock, state_mock):
    """Test scanning bucket with pagination"""
    s3_mock.list_buckets.return_value = {"Buckets": [{"Name": "test-bucket"}]}
    s3_mock.get_paginator.return_value.paginate.return_value = [
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

    assert_equal(state_mock.add_file.call_count, 2)
