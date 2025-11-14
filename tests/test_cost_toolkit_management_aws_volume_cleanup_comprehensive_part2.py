"""Comprehensive tests for aws_volume_cleanup.py - Part 2."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.management.aws_volume_cleanup import (
    list_s3_buckets,
    main,
    process_bucket_info,
)


@patch("cost_toolkit.scripts.management.aws_volume_cleanup.get_bucket_region")
@patch("cost_toolkit.scripts.management.aws_volume_cleanup.get_bucket_size_metrics")
def test_process_bucket_info_success(mock_get_size, mock_get_region, capsys):
    """Test processing bucket info successfully."""
    mock_s3_client = MagicMock()
    bucket = {"Name": "test-bucket", "CreationDate": datetime(2025, 11, 13, 12, 0, 0)}

    mock_get_region.return_value = "us-east-1"

    result = process_bucket_info(mock_s3_client, bucket)

    assert result["name"] == "test-bucket"
    assert result["creation_date"] == datetime(2025, 11, 13, 12, 0, 0)
    assert result["region"] == "us-east-1"

    mock_get_region.assert_called_once_with(mock_s3_client, "test-bucket")
    mock_get_size.assert_called_once_with("test-bucket", "us-east-1")

    captured = capsys.readouterr()
    assert "Bucket: test-bucket" in captured.out


class TestListS3Buckets:
    """Tests for list_s3_buckets function."""

    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.boto3.client")
    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.process_bucket_info")
    def test_list_s3_buckets_success(self, mock_process_bucket, mock_boto3_client, capsys):
        """Test successfully listing S3 buckets."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        mock_s3_client.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket1", "CreationDate": datetime(2025, 11, 13, 12, 0, 0)},
                {"Name": "bucket2", "CreationDate": datetime(2025, 11, 12, 12, 0, 0)},
            ]
        }

        mock_process_bucket.side_effect = [
            {
                "name": "bucket1",
                "creation_date": datetime(2025, 11, 13, 12, 0, 0),
                "region": "us-east-1",
            },
            {
                "name": "bucket2",
                "creation_date": datetime(2025, 11, 12, 12, 0, 0),
                "region": "us-west-2",
            },
        ]

        result = list_s3_buckets()

        assert len(result) == 2
        assert result[0]["name"] == "bucket1"
        assert result[1]["name"] == "bucket2"

        captured = capsys.readouterr()
        assert "Found 2 S3 bucket(s)" in captured.out

    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.boto3.client")
    def test_list_s3_buckets_empty(self, mock_boto3_client, capsys):
        """Test listing S3 buckets when none exist."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        mock_s3_client.list_buckets.return_value = {"Buckets": []}

        result = list_s3_buckets()

        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Found 0 S3 bucket(s)" in captured.out

    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.boto3.client")
    def test_list_s3_buckets_error(self, mock_boto3_client, capsys):
        """Test error listing S3 buckets."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client

        mock_s3_client.list_buckets.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "list_buckets"
        )

        result = list_s3_buckets()

        assert result == []
        captured = capsys.readouterr()
        assert "Error listing S3 buckets" in captured.out


class TestMainSuccess:
    """Tests for main function successful operations."""

    def test_main_all_operations_success(self, capsys):
        """Test main function with all operations successful."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.return_value = True
            mock_list_buckets.return_value = [{"name": "bucket1"}]

            main()

            mock_tag_volume.assert_called_once_with("vol-062d0da3492e8cef", "mufasa", "us-east-2")
            assert mock_delete_snapshot.call_count == 2
            mock_list_buckets.assert_called_once()

            captured = capsys.readouterr()
            assert "SUMMARY" in captured.out
            assert "vol-062d0da3492e8ceff successfully tagged" in captured.out
            assert "Both automated snapshots successfully deleted" in captured.out

    def test_main_displays_verification_commands(self, capsys):
        """Test main function displays verification commands."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.return_value = True
            mock_list_buckets.return_value = []

            main()

            captured = capsys.readouterr()
            assert "You can verify changes using" in captured.out
            assert "aws_ebs_volume_manager.py" in captured.out

    def test_main_multiple_buckets(self, capsys):
        """Test main function with multiple buckets."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.return_value = True
            mock_list_buckets.return_value = [
                {"name": "bucket1"},
                {"name": "bucket2"},
                {"name": "bucket3"},
            ]

            main()

            captured = capsys.readouterr()
            assert "Found 3 S3 bucket(s)" in captured.out


class TestMainErrors:
    """Tests for main function error handling."""

    def test_main_volume_tag_failure(self, capsys):
        """Test main function with volume tagging failure."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = False
            mock_delete_snapshot.return_value = True
            mock_list_buckets.return_value = []

            main()

            captured = capsys.readouterr()
            assert "Failed to tag volume" in captured.out

    def test_main_snapshot_deletion_failure(self, capsys):
        """Test main function with snapshot deletion failure."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.return_value = False
            mock_list_buckets.return_value = []

            main()

            captured = capsys.readouterr()
            assert "Failed to delete automated snapshots" in captured.out

    def test_main_partial_snapshot_deletion(self, capsys):
        """Test main function with partial snapshot deletion."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.side_effect = [True, False]
            mock_list_buckets.return_value = []

            main()

            captured = capsys.readouterr()
            assert "One automated snapshot deleted, one failed" in captured.out

    def test_main_no_buckets_found(self, capsys):
        """Test main function with no S3 buckets found."""
        mod = "cost_toolkit.scripts.management.aws_volume_cleanup"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.tag_volume_with_name") as mock_tag_volume,
            patch(f"{mod}.delete_snapshot") as mock_delete_snapshot,
            patch(f"{mod}.list_s3_buckets") as mock_list_buckets,
        ):
            mock_tag_volume.return_value = True
            mock_delete_snapshot.return_value = True
            mock_list_buckets.return_value = []

            main()

            captured = capsys.readouterr()
            assert "No S3 buckets found or unable to list" in captured.out
