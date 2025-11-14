"""Comprehensive tests for aws_s3_standardization.py - Part 1 (Core Functions)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.aws_s3_standardization import (
    delete_bucket_completely,
    ensure_bucket_private,
    get_bucket_region,
    remove_lifecycle_policy,
)


class TestGetBucketRegion:
    """Tests for get_bucket_region function."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_location")
    def test_get_bucket_region_success(self, mock_get_location):
        """Test successful bucket region retrieval."""
        mock_get_location.return_value = "us-west-2"
        region = get_bucket_region("test-bucket")
        assert region == "us-west-2"
        mock_get_location.assert_called_once_with("test-bucket")

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_location")
    def test_get_bucket_region_error_returns_default(self, mock_get_location, capsys):
        """Test bucket region error returns default region."""
        mock_get_location.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "get_bucket_location"
        )
        region = get_bucket_region("non-existent-bucket")
        assert region == "us-east-1"
        captured = capsys.readouterr()
        assert "Error getting region" in captured.out


class TestDeleteBucketCompletelySuccess:
    """Tests for successful bucket deletion scenarios."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_versioned_bucket(self, mock_get_region, mock_create_client, capsys):
        """Test deleting a versioned bucket with objects."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.return_value = {
            "Versions": [
                {"Key": "file1.txt", "VersionId": "v1"},
                {"Key": "file2.txt", "VersionId": "v2"},
            ],
            "DeleteMarkers": [{"Key": "file3.txt", "VersionId": "m1"}],
        }

        result = delete_bucket_completely("versioned-bucket")

        assert result is True
        assert mock_s3_client.delete_object.call_count == 3
        mock_s3_client.delete_bucket.assert_called_once_with(Bucket="versioned-bucket")
        captured = capsys.readouterr()
        assert "Successfully deleted bucket" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_regular_bucket(self, mock_get_region, mock_create_client, capsys):
        """Test deleting a non-versioned bucket with objects."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "list_object_versions"
        )

        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]}
        ]

        result = delete_bucket_completely("regular-bucket")

        assert result is True
        assert mock_s3_client.delete_object.call_count == 2
        mock_s3_client.delete_bucket.assert_called_once_with(Bucket="regular-bucket")
        captured = capsys.readouterr()
        assert "Successfully deleted bucket" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_empty_versioned_bucket(self, mock_get_region, mock_create_client):
        """Test deleting an empty versioned bucket."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.return_value = {}

        result = delete_bucket_completely("empty-versioned")

        assert result is True
        mock_s3_client.delete_object.assert_not_called()
        mock_s3_client.delete_bucket.assert_called_once_with(Bucket="empty-versioned")


class TestDeleteBucketCompletelyErrors:
    """Tests for bucket deletion error scenarios."""

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_already_deleted_bucket(self, mock_get_region, mock_create_client, capsys):
        """Test deleting a bucket that doesn't exist."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "list_object_versions"
        )
        mock_s3_client.get_paginator.return_value.paginate.return_value = []
        mock_s3_client.delete_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "delete_bucket"
        )

        result = delete_bucket_completely("non-existent")

        assert result is True
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_bucket_not_empty_error(self, mock_get_region, mock_create_client, capsys):
        """Test error when bucket is not empty."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "list_object_versions"
        )
        mock_s3_client.get_paginator.return_value.paginate.return_value = []
        mock_s3_client.delete_bucket.side_effect = ClientError(
            {"Error": {"Code": "BucketNotEmpty"}}, "delete_bucket"
        )

        result = delete_bucket_completely("not-empty-bucket")

        assert result is False
        captured = capsys.readouterr()
        assert "is not empty" in captured.out

    @patch("cost_toolkit.scripts.management.aws_s3_standardization.create_s3_client")
    @patch("cost_toolkit.scripts.management.aws_s3_standardization.get_bucket_region")
    def test_delete_bucket_generic_error(self, mock_get_region, mock_create_client, capsys):
        """Test generic error during bucket deletion."""
        mock_get_region.return_value = "us-east-1"
        mock_s3_client = MagicMock()
        mock_create_client.return_value = mock_s3_client

        mock_s3_client.list_object_versions.return_value = {}
        mock_s3_client.delete_bucket.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "delete_bucket"
        )

        result = delete_bucket_completely("error-bucket")

        assert result is False
        captured = capsys.readouterr()
        assert "Error deleting bucket" in captured.out


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
