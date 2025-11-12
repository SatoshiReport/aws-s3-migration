"""Shared test helper utilities to reduce code duplication across test files."""

import json
import os
from datetime import datetime
from unittest import mock


def create_mock_ec2_client(_region, _aws_access_key_id, _aws_secret_access_key):
    """
    Create a mock EC2 client with standard configuration.

    Args:
        _region: AWS region name (unused)
        _aws_access_key_id: AWS access key ID (unused)
        _aws_secret_access_key: AWS secret access key (unused)

    Returns:
        mock.Mock: Configured mock EC2 client
    """
    return mock.Mock()


def create_mock_s3_client(_region, _aws_access_key_id, _aws_secret_access_key):
    """
    Create a mock S3 client with standard configuration.

    Args:
        _region: AWS region name (unused)
        _aws_access_key_id: AWS access key ID (unused)
        _aws_secret_access_key: AWS secret access key (unused)

    Returns:
        mock.Mock: Configured mock S3 client
    """
    return mock.Mock()


def setup_mock_aws_credentials():
    """
    Set up mock AWS credentials in environment for testing.

    Returns:
        dict: Dictionary containing mock credentials
    """
    return {
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "AWS_DEFAULT_REGION": "us-east-1",
    }


def create_s3_list_response_with_missing_etag():
    """Create S3 list response with missing ETag for testing."""
    return [
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


def get_all_migration_phases():
    """Get list of all migration phases for testing."""
    from migration_state_v2 import Phase  # pylint: disable=import-outside-toplevel

    return [
        Phase.SCANNING,
        Phase.GLACIER_RESTORE,
        Phase.GLACIER_WAIT,
        Phase.SYNCING,
        Phase.VERIFYING,
        Phase.DELETING,
        Phase.COMPLETE,
    ]


def load_log_file_json(log_file):
    """Load JSON log file, creating empty dict if not exists."""
    if os.path.exists(log_file):
        with open(log_file, encoding="utf-8") as f:
            return json.load(f)
    return {}


def create_verification_stats():
    """Create verification statistics dict."""
    return {
        "verified_count": 0,
        "size_verified": 0,
        "checksum_verified": 0,
        "total_bytes_verified": 0,
        "verification_errors": [],
    }
