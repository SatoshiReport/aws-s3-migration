"""Tests for aws_utils clients and bucket functionality."""

from unittest import mock

import pytest

import aws_utils
from tests.assertions import assert_equal

# ============================================================================
# Tests for get_boto3_clients
# ============================================================================


def test_get_boto3_clients_returns_three_clients():
    """Test that get_boto3_clients returns three clients."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_client.side_effect = [mock.Mock(), mock.Mock(), mock.Mock()]

        s3, sts, iam = aws_utils.get_boto3_clients()

        assert s3 is not None
        assert sts is not None
        assert iam is not None


def test_get_boto3_clients_creates_s3_sts_iam():
    """Test that get_boto3_clients creates clients in correct order."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_s3, mock_sts, mock_iam = mock.Mock(), mock.Mock(), mock.Mock()
        mock_client.side_effect = [mock_s3, mock_sts, mock_iam]

        _s3, _sts, _iam = aws_utils.get_boto3_clients()

        assert_equal(mock_client.call_count, 3)
        calls = mock_client.call_args_list
        assert calls[0] == mock.call("s3")
        assert calls[1] == mock.call("sts")
        assert calls[2] == mock.call("iam")


def test_get_boto3_clients_returns_tuple():
    """Test that get_boto3_clients returns a tuple."""
    with mock.patch("aws_utils.boto3.client") as mock_client:
        mock_client.side_effect = [mock.Mock(), mock.Mock(), mock.Mock()]

        result = aws_utils.get_boto3_clients()

        assert isinstance(result, tuple)
        assert_equal(len(result), 3)


# ============================================================================
# Tests for list_s3_buckets
# ============================================================================


def test_list_s3_buckets_returns_bucket_names():
    """Test that list_s3_buckets returns bucket names as list."""
    with mock.patch("aws_utils._list_buckets_raw", return_value=[{"Name": "a"}, {"Name": "b"}]):
        buckets = aws_utils.list_s3_buckets()

    assert buckets == ["a", "b"]


def test_list_s3_buckets_returns_empty_list_when_no_buckets():
    """Test that list_s3_buckets returns empty list when no buckets exist."""
    with mock.patch("aws_utils._list_buckets_raw", return_value=[]):
        buckets = aws_utils.list_s3_buckets()

    assert buckets == []


def test_list_s3_buckets_returns_list_type():
    """Test that list_s3_buckets always returns a list."""
    with mock.patch("aws_utils._list_buckets_raw", return_value=[{"Name": "bucket1"}]):
        buckets = aws_utils.list_s3_buckets()

    assert isinstance(buckets, list)


def test_list_s3_buckets_with_many_buckets():
    """Test list_s3_buckets with large number of buckets."""
    bucket_list = [{"Name": f"bucket-{i}"} for i in range(100)]

    with mock.patch("aws_utils._list_buckets_raw", return_value=bucket_list):
        buckets = aws_utils.list_s3_buckets()

    assert_equal(len(buckets), 100)
    assert buckets[0] == "bucket-0"
    assert buckets[99] == "bucket-99"


def test_list_s3_buckets_with_special_names():
    """Test list_s3_buckets with bucket names containing special characters."""
    bucket_list = [
        {"Name": "bucket-with-dash"},
        {"Name": "bucket.with.dot"},
        {"Name": "bucket123"},
    ]

    with mock.patch("aws_utils._list_buckets_raw", return_value=bucket_list):
        buckets = aws_utils.list_s3_buckets()

    assert "bucket-with-dash" in buckets
    assert "bucket.with.dot" in buckets
    assert "bucket123" in buckets


def test_list_s3_buckets_error_handling():
    """Test that list_s3_buckets propagates boto3 exceptions."""
    with mock.patch("aws_utils._list_buckets_raw", side_effect=Exception("AWS Error")):
        with pytest.raises(Exception, match="AWS Error"):
            aws_utils.list_s3_buckets()
