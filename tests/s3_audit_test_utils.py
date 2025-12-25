"""Shared helpers for S3 audit bucket analysis tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from botocore.exceptions import ClientError


def build_bucket_metadata_client(public_access=True):
    """Create a mock s3 client with common metadata responses."""
    mock_client = MagicMock()
    mock_client.get_bucket_versioning.return_value = {"Status": "Enabled" if public_access else "Suspended"}
    mock_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
        {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
        "GetBucketLifecycleConfiguration",
    )
    mock_client.get_bucket_encryption.side_effect = ClientError(
        {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
        "GetBucketEncryption",
    )
    if public_access:
        mock_client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }
    else:
        mock_client.get_public_access_block.side_effect = ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration"}}, "GetPublicAccessBlock"
        )
    return mock_client
