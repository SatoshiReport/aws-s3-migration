"""Comprehensive tests for monitor_manual_exports.py - Part 1."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.monitor_manual_exports import (
    _print_file_summary,
    _print_task_summary,
    check_export_status,
    check_s3_files,
)


class TestCheckExportStatusBasic:
    """Test basic export status checking scenarios."""

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_export_status_all_tasks(self, mock_boto_client, mock_load_creds, capsys):
        """Test checking all export tasks."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_export_image_tasks.return_value = {
            "ExportImageTasks": [
                {
                    "ExportImageTaskId": "export-123",
                    "ImageId": "ami-111",
                    "Status": "active",
                    "Progress": "50",
                    "StatusMessage": "exporting",
                },
                {
                    "ExportImageTaskId": "export-456",
                    "ImageId": "ami-222",
                    "Status": "completed",
                    "Progress": "100",
                },
            ]
        }
        tasks = check_export_status("us-east-1")
        assert len(tasks) == 2
        assert tasks[0]["Status"] == "active"
        assert tasks[1]["Status"] == "completed"
        captured = capsys.readouterr()
        assert "Export tasks in us-east-1" in captured.out
        assert "export-123" in captured.out
        assert "export-456" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_export_status_specific_ami(self, mock_boto_client, _mock_load_creds):
        """Test checking specific AMI export status."""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_export_image_tasks.return_value = {
            "ExportImageTasks": [
                {
                    "ExportImageTaskId": "export-789",
                    "ImageId": "ami-specific",
                    "Status": "active",
                    "Progress": "80",
                },
                {
                    "ExportImageTaskId": "export-999",
                    "ImageId": "ami-other",
                    "Status": "active",
                    "Progress": "20",
                },
            ]
        }
        tasks = check_export_status("us-west-2", ami_id="ami-specific")
        assert len(tasks) == 1
        assert tasks[0]["ImageId"] == "ami-specific"


@patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
@patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
def test_check_export_status_various_statuses(mock_boto_client, mock_load_creds, capsys):
    """Test display of various export statuses."""
    mock_load_creds.return_value = ("access_key", "secret_key")
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2
    mock_ec2.describe_export_image_tasks.return_value = {
        "ExportImageTasks": [
            {
                "ExportImageTaskId": "export-active",
                "ImageId": "ami-1",
                "Status": "active",
                "Progress": "50",
            },
            {
                "ExportImageTaskId": "export-completed",
                "ImageId": "ami-2",
                "Status": "completed",
                "Progress": "100",
            },
            {
                "ExportImageTaskId": "export-failed",
                "ImageId": "ami-3",
                "Status": "failed",
                "Progress": "30",
            },
            {
                "ExportImageTaskId": "export-deleted",
                "ImageId": "ami-4",
                "Status": "deleted",
                "Progress": "0",
            },
        ]
    }
    tasks = check_export_status("us-east-1")
    assert len(tasks) == 4
    captured = capsys.readouterr()
    assert "🔄" in captured.out
    assert "✅" in captured.out
    assert "❌" in captured.out
    assert "🗑️" in captured.out


class TestCheckExportStatusEdgeCases:
    """Test edge cases and error scenarios for export status checking."""

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_export_status_no_tasks(self, mock_boto_client, mock_load_creds, capsys):
        """Test when no export tasks exist."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_export_image_tasks.return_value = {"ExportImageTasks": []}

        tasks = check_export_status("eu-west-1")

        assert len(tasks) == 0
        captured = capsys.readouterr()
        assert "No export tasks found" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_export_status_error(self, mock_boto_client, mock_load_creds, capsys):
        """Test handling errors when checking export status."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_export_image_tasks.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "describe_export_image_tasks"
        )

        tasks = check_export_status("us-east-1")

        assert len(tasks) == 0
        captured = capsys.readouterr()
        assert "Error checking exports" in captured.out


class TestCheckS3Files:
    """Test S3 file checking functionality."""

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_s3_files_with_vmdks(self, mock_boto_client, mock_load_creds, capsys):
        """Test checking S3 files with VMDK files present."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "ebs-snapshots/ami-111/export-111.vmdk",
                    "Size": 10 * 1024**3,
                    "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc),
                },
                {
                    "Key": "ebs-snapshots/ami-222/export-222.vmdk",
                    "Size": 20 * 1024**3,
                    "LastModified": datetime(2024, 1, 2, tzinfo=timezone.utc),
                },
                {"Key": "ebs-snapshots/readme.txt", "Size": 1024, "LastModified": datetime.now()},
            ]
        }

        files = check_s3_files("us-east-1", "test-bucket")

        assert len(files) == 2
        assert files[0]["size_gb"] == 10.0
        assert files[1]["size_gb"] == 20.0
        captured = capsys.readouterr()
        assert "Found 2 VMDK files" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_s3_files_no_contents(self, mock_boto_client, mock_load_creds, capsys):
        """Test when S3 bucket has no files."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.list_objects_v2.return_value = {}

        files = check_s3_files("us-west-2")

        assert len(files) == 0
        captured = capsys.readouterr()
        assert "No files found" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_s3_files_bucket_not_found(self, mock_boto_client, mock_load_creds, capsys):
        """Test when S3 bucket does not exist."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        class NoSuchBucket(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchBucket = NoSuchBucket
        mock_s3.list_objects_v2.side_effect = NoSuchBucket()

        files = check_s3_files("us-east-1", "nonexistent-bucket")

        assert len(files) == 0
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.load_aws_credentials_from_env")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    def test_check_s3_files_client_error(self, mock_boto_client, mock_load_creds, capsys):
        """Test handling S3 client errors."""
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        class NoSuchBucket(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchBucket = NoSuchBucket
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "list_objects_v2"
        )

        files = check_s3_files("us-east-1")

        assert len(files) == 0
        captured = capsys.readouterr()
        assert "Error checking S3" in captured.out


class TestPrintTaskSummary:
    """Test task summary printing."""

    def test_print_task_summary_with_tasks(self, capsys):
        """Test printing summary with various task statuses."""
        tasks = [
            {"Status": "active"},
            {"Status": "active"},
            {"Status": "completed"},
            {"Status": "completed"},
            {"Status": "completed"},
            {"Status": "failed"},
            {"Status": "deleted"},
        ]

        _print_task_summary(tasks)

        captured = capsys.readouterr()
        assert "Active exports: 2" in captured.out
        assert "Completed exports: 3" in captured.out
        assert "Failed exports: 1" in captured.out
        assert "Deleted exports: 1" in captured.out

    def test_print_task_summary_empty(self, capsys):
        """Test printing summary with no tasks."""
        _print_task_summary([])

        captured = capsys.readouterr()
        assert "No export tasks found" in captured.out


class TestPrintFileSummary:
    """Test file summary printing."""

    def test_print_file_summary_with_files(self, capsys):
        """Test printing summary with files."""
        files = [
            {"size_gb": 10.0, "key": "file1.vmdk"},
            {"size_gb": 20.0, "key": "file2.vmdk"},
            {"size_gb": 30.0, "key": "file3.vmdk"},
        ]

        _print_file_summary(files)

        captured = capsys.readouterr()
        assert "S3 VMDK files: 3" in captured.out
        assert "60.00 GB" in captured.out
        assert "monthly savings" in captured.out
        assert "annual savings" in captured.out

    def test_print_file_summary_calculates_savings(self, capsys):
        """Test that savings calculation is correct."""
        files = [{"size_gb": 100.0, "key": "large.vmdk"}]

        _print_file_summary(files)

        captured = capsys.readouterr()
        monthly_savings = 100 * (0.05 - 0.023)
        assert f"${monthly_savings:.2f}" in captured.out

    def test_print_file_summary_empty(self, capsys):
        """Test printing summary with no files."""
        _print_file_summary([])

        captured = capsys.readouterr()
        assert "No S3 VMDK files found" in captured.out
