"""Tests for bucket metadata functions in cost_toolkit/scripts/audit/s3_audit/bucket_analysis.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.s3_utils import get_bucket_region
from cost_toolkit.scripts.audit.s3_audit.bucket_analysis import (
    _get_bucket_metadata,
)
from tests.assertions import assert_equal


def test_get_bucket_region_us_east_1():
    """Test get_bucket_region returns us-east-1 when LocationConstraint is None."""
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.bucket_analysis.get_bucket_location"
    ) as mock_get_location:
        mock_get_location.return_value = "us-east-1"

        region = get_bucket_region("test-bucket")
        assert_equal(region, "us-east-1")
        mock_get_location.assert_called_once_with("test-bucket")


def test_get_bucket_region_specific_region():
    """Test get_bucket_region returns the correct region."""
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.bucket_analysis.get_bucket_location"
    ) as mock_get_location:
        mock_get_location.return_value = "us-west-2"

        region = get_bucket_region("test-bucket")
        assert_equal(region, "us-west-2")


def test_get_bucket_region_client_error():
    """Test get_bucket_region raises ClientError on error."""
    with patch(
        "cost_toolkit.scripts.audit.s3_audit.bucket_analysis.get_bucket_location"
    ) as mock_get_location:
        mock_get_location.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}},
            "GetBucketLocation",
        )

        with pytest.raises(ClientError):
            get_bucket_region("nonexistent-bucket")


def test_get_bucket_metadata_versioning_enabled():
    """Test _get_bucket_metadata detects versioning enabled."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
        {"Error": {"Code": "NoSuchLifecycleConfiguration"}}, "GetBucketLifecycleConfiguration"
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

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["versioning_enabled"], True)
    assert_equal(bucket_analysis["lifecycle_policy"], [])
    assert_equal(bucket_analysis["public_access"], False)


def test_get_bucket_metadata_versioning_disabled():
    """Test _get_bucket_metadata detects versioning disabled."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.return_value = {"Status": "Suspended"}
    mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
        {"Error": {"Code": "NoSuchLifecycleConfiguration"}}, "GetBucketLifecycleConfiguration"
    )
    mock_client.get_bucket_encryption.side_effect = ClientError(
        {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
        "GetBucketEncryption",
    )
    mock_client.get_public_access_block.side_effect = ClientError(
        {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
    )

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["versioning_enabled"], False)
    assert_equal(bucket_analysis["public_access"], True)


def test_get_bucket_metadata_with_lifecycle_policy():
    """Test _get_bucket_metadata collects lifecycle policy."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.side_effect = ClientError(
        {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
    )
    lifecycle_rules = [
        {
            "Id": "rule1",
            "Status": "Enabled",
            "Transitions": [{"Days": 30, "StorageClass": "GLACIER"}],
        }
    ]
    mock_client.get_bucket_lifecycle_configuration.return_value = {"Rules": lifecycle_rules}
    mock_client.get_bucket_encryption.side_effect = ClientError(
        {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
        "GetBucketEncryption",
    )
    mock_client.get_public_access_block.side_effect = ClientError(
        {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
    )

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["lifecycle_policy"], lifecycle_rules)


def test_get_bucket_metadata_with_encryption():
    """Test _get_bucket_metadata collects encryption configuration."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.side_effect = ClientError(
        {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
    )
    mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
        {"Error": {"Code": "NoSuchLifecycleConfiguration"}}, "GetBucketLifecycleConfiguration"
    )
    encryption_config = {
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }
    mock_client.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": encryption_config
    }
    mock_client.get_public_access_block.side_effect = ClientError(
        {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
    )

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["encryption"], encryption_config)


def test_get_bucket_metadata_public_access_partial_block():
    """Test _get_bucket_metadata detects partial public access blocking."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.side_effect = ClientError(
        {"Error": {"Code": "NoSuchConfiguration"}}, "GetBucketVersioning"
    )
    mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
        {"Error": {"Code": "NoSuchLifecycleConfiguration"}}, "GetBucketLifecycleConfiguration"
    )
    mock_client.get_bucket_encryption.side_effect = ClientError(
        {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
        "GetBucketEncryption",
    )
    # Only some public access blocks enabled
    mock_client.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": False,  # This is False, so public access is possible
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["public_access"], True)
