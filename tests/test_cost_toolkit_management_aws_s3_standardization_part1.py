"""Comprehensive tests for aws_s3_standardization.py - Part 1 (Core Functions)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.aws_s3_standardization import (
    ensure_bucket_private,
    get_bucket_region,
    remove_lifecycle_policy,
)


class TestGetBucketRegion:
    """Tests for get_bucket_region function."""

    @patch("cost_toolkit.scripts.aws_s3_operations.get_bucket_location")
    def test_get_bucket_region_success(self, mock_get_location):
        """Test successful bucket region retrieval."""
        mock_get_location.return_value = "us-west-2"
        region = get_bucket_region("test-bucket")
        assert region == "us-west-2"
        mock_get_location.assert_called_once_with("test-bucket")

    @patch("cost_toolkit.scripts.aws_s3_operations.get_bucket_location")
    def test_get_bucket_region_error_raises(self, mock_get_location):
        """Test bucket region error raises exception (fail-fast)."""
        mock_get_location.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "get_bucket_location"
        )

        with pytest.raises(ClientError):
            get_bucket_region("non-existent-bucket")


class TestEnsureBucketPrivate:
    """Tests for ensure_bucket_private function."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_ensure_bucket_private_success(self, mock_create_client, capsys):
        """Test successfully securing a bucket."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        result = ensure_bucket_private("test-bucket", "us-east-1")

        assert result is True
        mock_s3_client.put_public_access_block.assert_called_once()
        call_args = mock_s3_client.put_public_access_block.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        config = call_args[1]["PublicAccessBlockConfiguration"]
        assert config["BlockPublicAcls"] is True
        assert config["IgnorePublicAcls"] is True
        assert config["BlockPublicPolicy"] is True
        assert config["RestrictPublicBuckets"] is True

        mock_s3_client.delete_bucket_policy.assert_called_once_with(Bucket="test-bucket")
        captured = capsys.readouterr()
        assert "Secured bucket" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_ensure_bucket_private_no_policy(self, mock_create_client, capsys):
        """Test securing bucket with no existing policy."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.delete_bucket_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucketPolicy"}}, "delete_bucket_policy"
        )

        result = ensure_bucket_private("test-bucket", "us-east-1")

        assert result is True
        captured = capsys.readouterr()
        assert "Secured bucket" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_ensure_bucket_private_policy_delete_error(self, mock_create_client, capsys):
        """Test warning when policy deletion fails."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.delete_bucket_policy.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "delete_bucket_policy"
        )

        result = ensure_bucket_private("test-bucket", "us-east-1")

        assert result is True
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Could not remove bucket policy" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_ensure_bucket_private_error(self, mock_create_client, capsys):
        """Test error securing bucket."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.put_public_access_block.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "put_public_access_block"
        )

        result = ensure_bucket_private("non-existent", "us-east-1")

        assert result is False
        captured = capsys.readouterr()
        assert "Error securing bucket" in captured.out


class TestRemoveLifecyclePolicy:
    """Tests for remove_lifecycle_policy function."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_remove_lifecycle_policy_success(self, mock_create_client, capsys):
        """Test successfully removing lifecycle policy."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.get_bucket_lifecycle_configuration.return_value = {"Rules": []}

        result = remove_lifecycle_policy("test-bucket", "us-east-1")

        assert result is True
        mock_s3_client.delete_bucket_lifecycle.assert_called_once_with(Bucket="test-bucket")
        captured = capsys.readouterr()
        assert "Removed lifecycle policy" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_remove_lifecycle_policy_no_policy(self, mock_create_client, capsys):
        """Test removing lifecycle policy when none exists."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
            "get_bucket_lifecycle_configuration",
        )

        result = remove_lifecycle_policy("test-bucket", "us-east-1")

        assert result is True
        mock_s3_client.delete_bucket_lifecycle.assert_not_called()
        captured = capsys.readouterr()
        assert "No lifecycle policy to remove" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_remove_lifecycle_policy_get_error(self, mock_create_client, capsys):
        """Test error getting lifecycle policy."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "get_bucket_lifecycle_configuration"
        )

        result = remove_lifecycle_policy("test-bucket", "us-east-1")

        assert result is False
        captured = capsys.readouterr()
        assert "Error removing lifecycle policy" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    def test_remove_lifecycle_policy_unexpected_error(self, mock_create_client, capsys):
        """Test unexpected error during policy removal."""
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client
        mock_s3_client.get_bucket_lifecycle_configuration.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable"}}, "get_bucket_lifecycle_configuration"
        )

        result = remove_lifecycle_policy("test-bucket", "us-east-1")

        assert result is False
        captured = capsys.readouterr()
        assert "Error removing lifecycle policy" in captured.out
