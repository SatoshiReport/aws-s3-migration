"""
Integration tests for analyze_bucket_objects in
cost_toolkit/scripts/audit/s3_audit/bucket_analysis.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.s3_audit.bucket_analysis import analyze_bucket_objects
from tests.assertions import assert_equal


def test_analyze_bucket_objects_success():
    """Test analyze_bucket_objects successfully analyzes a bucket."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock metadata calls
        mock_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
            "GetBucketLifecycleConfiguration",
        )
        mock_client.get_bucket_encryption.side_effect = ClientError(
            {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
            "GetBucketEncryption",
        )
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }

        # Mock paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 1024,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime(2024, 10, 1, tzinfo=timezone.utc),
                    },
                    {
                        "Key": "file2.txt",
                        "Size": 2048,
                        "StorageClass": "GLACIER",
                        "LastModified": datetime(2024, 9, 1, tzinfo=timezone.utc),
                    },
                ]
            }
        ]

        result = analyze_bucket_objects("test-bucket", "us-east-1")

        assert result is not None
        assert_equal(result["bucket_name"], "test-bucket")
        assert_equal(result["region"], "us-east-1")
        assert_equal(result["total_objects"], 2)
        assert_equal(result["total_size_bytes"], 3072)
        assert_equal(result["versioning_enabled"], True)
        assert_equal(result["lifecycle_policy"], [])
        assert_equal(result["public_access"], False)


def test_analyze_bucket_objects_empty_bucket():
    """Test analyze_bucket_objects handles empty bucket."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock metadata calls
        mock_client.get_bucket_versioning.side_effect = ClientError(
            {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
        )
        mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
            "GetBucketLifecycleConfiguration",
        )
        mock_client.get_bucket_encryption.side_effect = ClientError(
            {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
            "GetBucketEncryption",
        )
        mock_client.get_public_access_block.side_effect = ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
        )

        # Mock paginator with no Contents
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No Contents key

        result = analyze_bucket_objects("empty-bucket", "us-west-2")

        assert result is not None
        assert_equal(result["total_objects"], 0)
        assert_equal(result["total_size_bytes"], 0)


def test_analyze_bucket_objects_no_such_bucket():
    """Test analyze_bucket_objects handles NoSuchBucket error."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock paginator to raise NoSuchBucket error
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "ListObjectsV2",
        )

        with patch("builtins.print") as mock_print:
            result = analyze_bucket_objects("nonexistent-bucket", "us-east-1")

            assert result is None
            mock_print.assert_called_once()
            print_call_args = str(mock_print.call_args)
            assert "nonexistent-bucket" in print_call_args
            assert "does not exist" in print_call_args


def test_analyze_bucket_objects_access_denied():
    """Test analyze_bucket_objects handles AccessDenied error."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock paginator to raise AccessDenied error
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "ListObjectsV2",
        )

        with patch("builtins.print") as mock_print:
            result = analyze_bucket_objects("restricted-bucket", "us-east-1")

            assert result is None
            mock_print.assert_called_once()
            print_call_args = str(mock_print.call_args)
            assert "restricted-bucket" in print_call_args
            assert "Access denied" in print_call_args


def test_analyze_bucket_objects_other_client_error():
    """Test analyze_bucket_objects handles generic ClientError."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock paginator to raise generic error
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Internal server error"}},
            "ListObjectsV2",
        )

        with patch("builtins.print") as mock_print:
            result = analyze_bucket_objects("error-bucket", "us-east-1")

            assert result is None
            mock_print.assert_called_once()
            print_call_args = str(mock_print.call_args)
            assert "error-bucket" in print_call_args
            assert "Error analyzing" in print_call_args


def test_analyze_bucket_objects_with_large_and_old_objects():
    """Test analyze_bucket_objects correctly identifies large and old objects."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock metadata calls
        mock_client.get_bucket_versioning.side_effect = ClientError(
            {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
        )
        mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
            "GetBucketLifecycleConfiguration",
        )
        mock_client.get_bucket_encryption.side_effect = ClientError(
            {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
            "GetBucketEncryption",
        )
        mock_client.get_public_access_block.side_effect = ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
        )

        large_size = 200 * 1024 * 1024  # 200MB
        old_date = datetime.now(timezone.utc) - timedelta(days=200)
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)  # Recent, not old

        # Mock paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "large-file.bin",
                        "Size": large_size,
                        "StorageClass": "STANDARD",
                        "LastModified": recent_date,  # Large but not old
                    },
                    {
                        "Key": "old-file.txt",
                        "Size": 5000,
                        "StorageClass": "GLACIER",
                        "LastModified": old_date,  # Old but not large
                    },
                ]
            }
        ]

        result = analyze_bucket_objects("test-bucket", "us-east-1")

        assert result is not None
        assert_equal(len(result["large_objects"]), 1)
        assert_equal(result["large_objects"][0]["key"], "large-file.bin")
        assert_equal(len(result["old_objects"]), 1)
        assert_equal(result["old_objects"][0]["key"], "old-file.txt")


def test_analyze_bucket_objects_multiple_pages():
    """Test analyze_bucket_objects handles pagination correctly."""
    with patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client

        # Mock metadata calls
        mock_client.get_bucket_versioning.side_effect = ClientError(
            {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
        )
        mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
            "GetBucketLifecycleConfiguration",
        )
        mock_client.get_bucket_encryption.side_effect = ClientError(
            {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
            "GetBucketEncryption",
        )
        mock_client.get_public_access_block.side_effect = ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
        )

        # Mock paginator with multiple pages
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {
                        "Key": "file1.txt",
                        "Size": 1000,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime(2024, 10, 1, tzinfo=timezone.utc),
                    }
                ]
            },
            {
                "Contents": [
                    {
                        "Key": "file2.txt",
                        "Size": 2000,
                        "StorageClass": "GLACIER",
                        "LastModified": datetime(2024, 9, 1, tzinfo=timezone.utc),
                    }
                ]
            },
            {
                "Contents": [
                    {
                        "Key": "file3.txt",
                        "Size": 3000,
                        "StorageClass": "STANDARD_IA",
                        "LastModified": datetime(2024, 8, 1, tzinfo=timezone.utc),
                    }
                ]
            },
        ]

        result = analyze_bucket_objects("test-bucket", "us-east-1")

        assert result is not None
        assert_equal(result["total_objects"], 3)
        assert_equal(result["total_size_bytes"], 6000)
        assert_equal(result["storage_classes"]["STANDARD"]["count"], 1)
        assert_equal(result["storage_classes"]["GLACIER"]["count"], 1)
        assert_equal(result["storage_classes"]["STANDARD_IA"]["count"], 1)
