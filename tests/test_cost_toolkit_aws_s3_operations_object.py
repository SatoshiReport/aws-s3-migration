"""Tests for cost_toolkit/scripts/aws_s3_operations.py - Object operations"""

# pylint: disable=unused-argument

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_s3_operations import (
    delete_bucket,
    delete_object,
    head_object,
    list_objects,
)
from tests.assertions import assert_equal


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_objects_without_prefix(mock_create_client):
    """Test list_objects returns all objects when no prefix specified."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    objects = [
        {"Key": "file1.txt", "Size": 100},
        {"Key": "file2.txt", "Size": 200},
    ]
    mock_s3.list_objects_v2.return_value = {"Contents": objects}

    result = list_objects("test-bucket", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.list_objects_v2.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, objects)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_objects_with_prefix(mock_create_client):
    """Test list_objects filters by prefix when specified."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    objects = [{"Key": "logs/file1.txt", "Size": 100}]
    mock_s3.list_objects_v2.return_value = {"Contents": objects}

    result = list_objects("test-bucket", "us-west-2", prefix="logs/")

    mock_s3.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="logs/")
    assert_equal(result, objects)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_objects_empty(mock_create_client):
    """Test list_objects returns empty list when no objects match."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.list_objects_v2.return_value = {}

    result = list_objects("empty-bucket", "us-east-1")

    assert_equal(result, [])


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_list_objects_with_credentials(mock_create_client):
    """Test list_objects passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.list_objects_v2.return_value = {"Contents": []}

    list_objects(
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
def test_head_object_success(mock_create_client):
    """Test head_object returns object metadata."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    metadata = {
        "ContentLength": 1024,
        "LastModified": "2025-01-01T00:00:00Z",
        "ETag": "abc123",
    }
    mock_s3.head_object.return_value = metadata

    result = head_object("test-bucket", "file.txt", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="file.txt")
    assert_equal(result, metadata)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
def test_head_object_with_credentials(mock_create_client):
    """Test head_object passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.head_object.return_value = {"ContentLength": 100}

    head_object(
        "test-bucket",
        "file.txt",
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
def test_head_object_not_found(mock_create_client):
    """Test head_object raises ClientError when object not found."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )

    try:
        head_object("test-bucket", "nonexistent.txt", "us-west-2")
        assert False, "Expected ClientError to be raised"
    except ClientError as e:
        assert_equal(e.response["Error"]["Code"], "404")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_object_success(mock_print, mock_create_client):
    """Test delete_object successfully deletes object."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = delete_object("test-bucket", "file.txt", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="file.txt")
    assert_equal(result, True)
    mock_print.assert_called_once_with("✅ Deleted object: s3://test-bucket/file.txt")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_object_with_credentials(mock_print, mock_create_client):
    """Test delete_object passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = delete_object(
        "test-bucket",
        "file.txt",
        "us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )

    mock_create_client.assert_called_once_with(
        region="us-west-2",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
    )
    assert_equal(result, True)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_object_failure(mock_print, mock_create_client):
    """Test delete_object returns False on ClientError."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.delete_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "DeleteObject"
    )

    result = delete_object("test-bucket", "file.txt", "us-west-2")

    assert_equal(result, False)
    assert mock_print.call_count == 1
    assert "❌ Failed to delete object file.txt" in mock_print.call_args[0][0]


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_bucket_success(mock_print, mock_create_client):
    """Test delete_bucket successfully deletes bucket."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = delete_bucket("test-bucket", "us-west-2")

    mock_create_client.assert_called_once_with(
        region="us-west-2", aws_access_key_id=None, aws_secret_access_key=None
    )
    mock_s3.delete_bucket.assert_called_once_with(Bucket="test-bucket")
    assert_equal(result, True)
    mock_print.assert_called_once_with("✅ Deleted bucket: test-bucket")


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_bucket_with_credentials(mock_print, mock_create_client):
    """Test delete_bucket passes credentials to create_s3_client."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3

    result = delete_bucket(
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
    assert_equal(result, True)


@patch("cost_toolkit.scripts.aws_s3_operations.create_s3_client")
@patch("builtins.print")
def test_delete_bucket_failure(mock_print, mock_create_client):
    """Test delete_bucket returns False on ClientError."""
    mock_s3 = MagicMock()
    mock_create_client.return_value = mock_s3
    mock_s3.delete_bucket.side_effect = ClientError(
        {"Error": {"Code": "BucketNotEmpty", "Message": "Bucket not empty"}},
        "DeleteBucket",
    )

    result = delete_bucket("test-bucket", "us-west-2")

    assert_equal(result, False)
    assert mock_print.call_count == 1
    assert "❌ Failed to delete bucket test-bucket" in mock_print.call_args[0][0]
