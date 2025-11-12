"""Unit tests for BucketScanner class from migration_scanner.py - ETag handling"""

from datetime import datetime


def test_scan_bucket_handles_missing_etag(scanner, state_mock):
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
    call_args = state_mock.add_file.call_args
    assert call_args[0][3] == ""


def test_scan_bucket_strips_etag_quotes(scanner, state_mock):
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
    call_args = state_mock.add_file.call_args
    assert call_args[0][3] == "abc123"
