"""Tests for bucket metadata functions in cost_toolkit/scripts/audit/s3_audit/bucket_analysis.py"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.s3_utils import get_bucket_region
from cost_toolkit.scripts.audit.s3_audit.bucket_analysis import (
    _get_bucket_metadata,
    _normalize_mock_methods,
    _process_object,
    _require_public_access_config,
    analyze_bucket_objects,
)
from tests.assertions import assert_equal
from tests.s3_audit_test_utils import build_bucket_metadata_client


def test_get_bucket_region_us_east_1():
    """Test get_bucket_region returns us-east-1 when LocationConstraint is None."""
    with patch("cost_toolkit.common.s3_utils.get_bucket_location") as mock_get_location:
        mock_get_location.return_value = "us-east-1"

        region = get_bucket_region("test-bucket")
        assert_equal(region, "us-east-1")
        mock_get_location.assert_called_once_with("test-bucket")


def test_get_bucket_region_specific_region():
    """Test get_bucket_region returns the correct region."""
    with patch("cost_toolkit.common.s3_utils.get_bucket_location") as mock_get_location:
        mock_get_location.return_value = "us-west-2"

        region = get_bucket_region("test-bucket")
        assert_equal(region, "us-west-2")


def test_get_bucket_region_client_error():
    """Test get_bucket_region raises ClientError on error."""
    with patch("cost_toolkit.common.s3_utils.get_bucket_location") as mock_get_location:
        mock_get_location.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}},
            "GetBucketLocation",
        )

        with pytest.raises(ClientError):
            get_bucket_region("nonexistent-bucket")


def test_get_bucket_metadata_versioning_enabled():
    """Test _get_bucket_metadata detects versioning enabled."""
    mock_client = build_bucket_metadata_client()

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["versioning_enabled"], True)
    assert_equal(bucket_analysis["lifecycle_policy"], [])
    assert_equal(bucket_analysis["public_access"], False)


def test_get_bucket_metadata_versioning_disabled():
    """Test _get_bucket_metadata detects versioning disabled."""
    mock_client = build_bucket_metadata_client(public_access=False)

    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["versioning_enabled"], False)
    assert_equal(bucket_analysis["public_access"], True)


def test_get_bucket_metadata_with_lifecycle_policy():
    """Test _get_bucket_metadata collects lifecycle policy."""
    mock_client = build_bucket_metadata_client(public_access=False)
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
    bucket_analysis = {}
    _get_bucket_metadata(mock_client, "test-bucket", bucket_analysis)

    assert_equal(bucket_analysis["lifecycle_policy"], lifecycle_rules)


def test_get_bucket_metadata_with_encryption():
    """Test _get_bucket_metadata collects encryption configuration."""
    mock_client = build_bucket_metadata_client(public_access=False)
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


@patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.logging.warning")
def test_require_public_access_config_missing_config(mock_warning):
    """Return default blocking config when payload missing."""
    result = _require_public_access_config({})

    assert result == {
        "BlockPublicAcls": False,
        "IgnorePublicAcls": False,
        "BlockPublicPolicy": False,
        "RestrictPublicBuckets": False,
    }
    mock_warning.assert_called_once()


@patch("cost_toolkit.scripts.audit.s3_audit.bucket_analysis.logging.warning")
def test_require_public_access_config_fills_missing_fields(mock_warning):
    """Fill in any missing public access fields."""
    result = _require_public_access_config(
        {"PublicAccessBlockConfiguration": {"BlockPublicAcls": True}}
    )

    assert result["BlockPublicAcls"] is True
    assert result["IgnorePublicAcls"] is False
    assert mock_warning.called


def test_normalize_mock_methods_clears_side_effects():
    """normalize_mock_methods should clear side_effect when return_value is set."""
    mock_client = MagicMock()
    mock_client.get_bucket_lifecycle_configuration.return_value = {}
    mock_client.get_bucket_lifecycle_configuration.side_effect = Exception("boom")
    mock_client.get_bucket_encryption.return_value = {}
    mock_client.get_bucket_encryption.side_effect = Exception("kaboom")

    _normalize_mock_methods(mock_client)

    assert mock_client.get_bucket_lifecycle_configuration.side_effect is None
    assert mock_client.get_bucket_encryption.side_effect is None


def test_process_object_tracks_sizes_and_dates():
    """process_object updates counters and tracking lists."""
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
    bucket_analysis = {
        "total_objects": 0,
        "total_size_bytes": 0,
        "storage_classes": {"STANDARD": {"count": 0, "size_bytes": 0}},
        "last_modified_oldest": None,
        "last_modified_newest": None,
        "large_objects": [],
        "old_objects": [],
    }
    obj = {
        "Key": "test",
        "Size": 200,
        "StorageClass": "STANDARD",
        "LastModified": datetime.now(timezone.utc) - timedelta(days=120),
    }

    _process_object(obj, bucket_analysis, ninety_days_ago, large_object_threshold=100)

    assert bucket_analysis["total_objects"] == 1
    assert bucket_analysis["total_size_bytes"] == 200
    assert bucket_analysis["storage_classes"]["STANDARD"]["count"] == 1
    assert bucket_analysis["large_objects"]
    assert bucket_analysis["old_objects"]


def test_analyze_bucket_objects_happy_path(monkeypatch):
    """analyze_bucket_objects should process pages and return analysis."""

    class FakePaginator:
        """Simple paginator stub that returns predefined pages."""

        def __init__(self, pages):
            self.pages = pages

        def paginate(self, **kwargs):
            """Return the configured page sequence for the requested bucket."""
            assert kwargs["Bucket"] == "bucket"
            return self.pages

    class FakeClient:
        """S3 client stub that returns deterministic metadata."""

        def __init__(self):
            self.called = []

        def get_bucket_versioning(self, **kwargs):
            """Simulate versioning enabled."""
            _ = kwargs["Bucket"]
            return {"Status": "Enabled"}

        def get_bucket_lifecycle_configuration(self, **kwargs):
            """Return an empty lifecycle configuration."""
            _ = kwargs["Bucket"]
            return {"Rules": []}

        def get_bucket_encryption(self, **kwargs):
            """Return an empty encryption configuration."""
            _ = kwargs["Bucket"]
            return {"ServerSideEncryptionConfiguration": {"Rules": []}}

        def get_public_access_block(self, **kwargs):
            """Return a fully restricted public access block."""
            _ = kwargs["Bucket"]
            return {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                }
            }

        def get_paginator(self, name):
            """Return a paginator configured with one page of object metadata."""
            assert name == "list_objects_v2"
            return FakePaginator(
                [
                    {
                        "Contents": [
                            {
                                "Key": "k1",
                                "Size": 150,
                                "StorageClass": "STANDARD",
                                "LastModified": datetime.now(timezone.utc),
                            }
                        ]
                    }
                ]
            )

    monkeypatch.setattr(
        "cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3.client",
        lambda service_name, region_name=None: FakeClient(),
    )

    result = analyze_bucket_objects("bucket", "us-east-1")

    assert result is not None
    assert result["bucket_name"] == "bucket"
    assert result["total_objects"] == 1
    assert result["storage_classes"]["STANDARD"]["count"] == 1


def test_analyze_bucket_objects_handles_errors(monkeypatch):
    """Return None on client errors."""
    error = ClientError({"Error": {"Code": "NoSuchBucket"}}, "ListObjects")

    def raise_client(*_, **__):
        raise error

    monkeypatch.setattr(
        "cost_toolkit.scripts.audit.s3_audit.bucket_analysis.boto3.client",
        lambda *args, **kwargs: raise_client(),
    )

    result = analyze_bucket_objects("missing", "us-east-1")
    assert result is None
