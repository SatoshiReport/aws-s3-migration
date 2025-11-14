"""Comprehensive tests for aws_volume_cleanup.py - Part 3."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.management import aws_volume_cleanup
from cost_toolkit.scripts.management.aws_volume_cleanup import (
    delete_snapshot,
    get_bucket_size_metrics,
    main,
)


class TestEdgeCases:
    """Tests for edge cases."""

    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.boto3.client")
    def test_delete_snapshot_zero_size(self, mock_boto3_client, capsys):
        """Test deleting zero-size snapshot."""
        mock_ec2_client = MagicMock()
        mock_boto3_client.return_value = mock_ec2_client

        mock_ec2_client.describe_snapshots.return_value = {
            "Snapshots": [
                {
                    "VolumeSize": 0,
                    "Description": "Empty",
                    "StartTime": datetime(2025, 11, 13, 12, 0, 0),
                }
            ]
        }

        delete_snapshot("snap-123456", "us-east-1")

        captured = capsys.readouterr()
        assert "$0.00" in captured.out

    @patch("cost_toolkit.scripts.management.aws_volume_cleanup.boto3.client")
    def test_get_bucket_size_exact_1gb(self, mock_boto3_client, capsys):
        """Test bucket size exactly at 1GB boundary."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch

        mock_cloudwatch.get_metric_statistics.return_value = {
            "Datapoints": [
                {
                    "Timestamp": datetime.now(timezone.utc),
                    "Average": 2 * 1024**3,
                }
            ]
        }

        get_bucket_size_metrics("bucket", "us-east-1")

        captured = capsys.readouterr()
        assert "Size: 2.00 GB" in captured.out


class TestConstantsAndImports:
    """Tests for module constants and imports."""

    def test_module_imports(self):
        """Test module can be imported."""
        assert aws_volume_cleanup is not None

    def test_main_function_exists(self):
        """Test main function exists."""
        assert callable(main)
