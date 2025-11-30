"""Tests for cost_toolkit/scripts/aws_s3_operations.py - Bucket operations"""

# pylint: disable=unused-argument

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_s3_operations import (
    create_bucket,
    get_bucket_location,
    get_bucket_tagging,
    get_bucket_versioning,
    list_buckets,
)
from tests.assertions import assert_equal


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_location_us_east_1(mock_create_client):
    """Test get_bucket_location returns us-east-1 when LocationConstraint is None."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_location.return_value = {"LocationConstraint": None}

    result = get_bucket_location("test-bucket")

    mock_create_client.assert_called_once_with(
        region="us-east-1", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.get_bucket_location.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, "us-east-1")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_location_other_region(mock_create_client):
    """Test get_bucket_location returns correct region for non-us-east-1."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}

    result = get_bucket_location("test-bucket-west")

    mock_s3.get_bucket_location.assert_called_once_with(Bucket="test-bucket-west")
    assert_equal(result, "us-west-2")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_location_with_credentials(mock_create_client):
    """Test get_bucket_location passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}

    result = get_bucket_location(
        "test-bucket", aws_access_key_id="test_key", aws_secret_access_key="test_secret"
    )

    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
    assert_equal(result, "eu-west-1")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_location_client_error(mock_create_client):
    """Test get_bucket_location raises ClientError when bucket not found."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_location.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"}},
        "GetBucketLocation",
    )

    try:
        get_bucket_location("nonexistent-bucket")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "NoSuchBucket")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_create_bucket_us_east_1_success(mock_print, mock_create_client):
    """Test create_bucket in us-east-1 without LocationConstraint."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = create_bucket("test-bucket", "us-east-1")

    mock_create_client.assert_called_once_with(
        region="us-east-1", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.create_bucket.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, True)
    mock_print.assert_called_once_with("✅ Created S3 bucket: test-bucket in us-east-1")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_create_bucket_other_region_success(mock_print, mock_create_client):
    """Test create_bucket in non-us-east-1 region with LocationConstraint."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = create_bucket("test-bucket-west", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.create_bucket.assert_called_once_with(
        Bucket="test-bucket-west",
        CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
    )
    assert_equal(result, True)
    mock_print.assert_called_once_with("✅ Created S3 bucket: test-bucket-west in us-west-2")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_create_bucket_with_credentials(mock_print, mock_create_client):
    """Test create_bucket passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = create_bucket(
        "test-bucket",
        "eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(
        region="eu-west-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
    assert_equal(result, True)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_create_bucket_failure(mock_print, mock_create_client):
    """Test create_bucket returns False on ClientError."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.create_bucket.side_effect = ClientError(
        {"Error": {"Code": "BucketAlreadyExists", "Message": "Bucket already exists"}},
        "CreateBucket",
    )

    result = create_bucket("existing-bucket", "us-east-1")

    assert_equal(result, False)
    assert mock_print.call_count == 1
    assert "❌ Failed to create bucket existing-bucket" in mock_print.call_args[0][0]


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_buckets_success(mock_create_client):
    """Test list_buckets returns bucket list."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    buckets = [
        {"Name": "bucket1", "CreationDate": "2025-01-01T00:00:00Z"},
        {"Name": "bucket2", "CreationDate": "2025-01-02T00:00:00Z"},
    ]
    mock_s3.list_buckets.return_value = {"Buckets": buckets}

    result = list_buckets()

    mock_create_client.assert_called_once_with(
        region="us-east-1", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.list_buckets.assert_called_once()
    assert_equal(result, buckets)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_buckets_empty(mock_create_client):
    """Test list_buckets raises KeyError when Buckets key is missing."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.list_buckets.return_value = {}

    with pytest.raises(KeyError, match="Buckets"):
        list_buckets()


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_buckets_with_credentials(mock_create_client):
    """Test list_buckets passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.list_buckets.return_value = {"Buckets": []}

    list_buckets(aws_access_key_id="test_key", aws_secret_access_key="test_secret")

    mock_create_client.assert_called_once_with(
        region="us-east-1",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_versioning_enabled(mock_create_client):
    """Test get_bucket_versioning returns versioning configuration."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    versioning = {"Status": "Enabled", "MFADelete": "Disabled"}
    mock_s3.get_bucket_versioning.return_value = versioning

    result = get_bucket_versioning("test-bucket", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.get_bucket_versioning.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, versioning)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_versioning_disabled(mock_create_client):
    """Test get_bucket_versioning returns empty dict when not enabled."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_versioning.return_value = {}

    result = get_bucket_versioning("test-bucket", "us-west-2")

    assert_equal(result, {})


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_versioning_with_credentials(mock_create_client):
    """Test get_bucket_versioning passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_versioning.return_value = {"Status": "Enabled"}

    get_bucket_versioning(
        "test-bucket",
        "us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(
        region="us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_tagging_success(mock_create_client):
    """Test get_bucket_tagging returns tag list."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    tags = [
        {"Key": "Environment", "Value": "Production"},
        {"Key": "Owner", "Value": "DevOps"},
    ]
    mock_s3.get_bucket_tagging.return_value = {"TagSet": tags}

    result = get_bucket_tagging("test-bucket", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.get_bucket_tagging.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, tags)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_tagging_no_such_tag_set(mock_create_client):
    """Test get_bucket_tagging returns empty list for NoSuchTagSet error."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_tagging.side_effect = ClientError(
        {"Error": {"Code": "NoSuchTagSet", "Message": "No tags found"}},
        "GetBucketTagging",
    )

    result = get_bucket_tagging("test-bucket", "us-west-2")

    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_tagging_empty_tag_set(mock_create_client):
    """Test get_bucket_tagging raises KeyError when TagSet not present."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_tagging.return_value = {}

    with pytest.raises(KeyError, match="TagSet"):
        get_bucket_tagging("test-bucket", "us-west-2")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_tagging_with_credentials(mock_create_client):
    """Test get_bucket_tagging passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_tagging.return_value = {"TagSet": []}

    get_bucket_tagging(
        "test-bucket",
        "us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(
        region="us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_get_bucket_tagging_other_client_error(mock_create_client):
    """Test get_bucket_tagging raises ClientError for non-NoSuchTagSet errors."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.get_bucket_tagging.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "GetBucketTagging",
    )

    try:
        get_bucket_tagging("test-bucket", "us-west-2")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "AccessDenied")
