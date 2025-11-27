"""Unit tests for BucketScanner class from migration_scanner.py - ETag handling"""

from datetime import datetime

import pytest


def test_scan_bucket_raises_on_missing_etag(scanner, state_mock):
    """Test that missing ETag field raises KeyError (fail-fast)"""
    scanner.s3.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "file.txt",
                    "Size": 100,
                    "StorageClass": "STANDARD",
                    "LastModified": datetime.now(),
                    # ETag missing - AWS always provides this, so missing indicates bad data
                }
            ]
        }
    ]

    with pytest.raises(KeyError, match="ETag"):
        scanner.scan_bucket("test-bucket")

    # Should not have called add_file since we raised before that
    state_mock.add_file.assert_not_called()


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
