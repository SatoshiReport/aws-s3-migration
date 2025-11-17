"""Comprehensive tests for aws_export_recovery.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.aws_export_recovery import (
    EXPORT_STABILITY_MINUTES,
    _check_s3_file_exists,
    _is_file_stable,
    _process_stuck_export,
    check_active_exports,
)


class TestCheckS3FileExists:
    """Test S3 file existence checking."""

    def test_file_exists_success(self):
        """Test when S3 file exists."""
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentLength": 1024 * 1024 * 1024 * 10,
            "LastModified": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        }

        result = _check_s3_file_exists(mock_s3, "test-bucket", "test-key.vmdk")

        assert result["exists"] is True
        assert result["size_bytes"] == 1024 * 1024 * 1024 * 10
        assert result["size_gb"] == 10.0
        assert isinstance(result["last_modified"], datetime)
        mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="test-key.vmdk")

    def test_file_not_exists(self):
        """Test when S3 file does not exist."""
        mock_s3 = MagicMock()

        class NoSuchKey(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchKey = NoSuchKey
        mock_s3.head_object.side_effect = NoSuchKey()

        result = _check_s3_file_exists(mock_s3, "test-bucket", "nonexistent.vmdk")

        assert result["exists"] is False
        assert "error" not in result

    def test_file_check_client_error(self):
        """Test handling client errors when checking file."""
        mock_s3 = MagicMock()

        class NoSuchKey(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchKey = NoSuchKey
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "head_object"
        )

        result = _check_s3_file_exists(mock_s3, "test-bucket", "denied.vmdk")

        assert result["exists"] is False
        assert "error" in result


class TestIsFileStable:
    """Test file stability checking."""

    def test_file_is_stable(self):
        """Test when file has been stable long enough."""
        now = datetime.now(timezone.utc)
        last_modified = now - timedelta(minutes=EXPORT_STABILITY_MINUTES + 5)

        is_stable, minutes = _is_file_stable(last_modified)

        assert is_stable is True
        assert minutes > EXPORT_STABILITY_MINUTES

    def test_file_is_not_stable(self):
        """Test when file was modified too recently."""
        now = datetime.now(timezone.utc)
        last_modified = now - timedelta(minutes=EXPORT_STABILITY_MINUTES - 5)

        is_stable, minutes = _is_file_stable(last_modified)

        assert is_stable is False
        assert minutes < EXPORT_STABILITY_MINUTES

    def test_file_stability_boundary(self):
        """Test file stability at exact boundary."""
        now = datetime.now(timezone.utc)
        last_modified = now - timedelta(minutes=EXPORT_STABILITY_MINUTES + 1)

        is_stable, _minutes = _is_file_stable(last_modified)

        assert is_stable is True


def _create_stuck_export_task():
    """Helper to create a stuck export task."""
    return {
        "ExportImageTaskId": "export-stuck",
        "ImageId": "ami-stuck",
        "S3ExportLocation": {
            "S3Bucket": "recovery-bucket",
            "S3Prefix": "exports/",
        },
    }


def _assert_recovered_export_result(result):
    """Helper to assert recovered export result."""
    assert result is not None
    assert result["export_task_id"] == "export-stuck"
    assert result["ami_id"] == "ami-stuck"
    assert result["bucket_name"] == "recovery-bucket"
    assert result["s3_key"] == "exports/export-stuck.vmdk"
    assert result["status"] == "recovered"
    assert result["size_gb"] == 5.0


def _assert_recovered_export_output(capsys):
    """Helper to assert recovered export output."""
    captured = capsys.readouterr()
    assert "S3 file exists!" in captured.out
    assert "EXPORT LIKELY COMPLETED SUCCESSFULLY" in captured.out


def test_process_stuck_export_recovered(capsys):
    """Test processing a stuck export that has completed."""
    now = datetime.now(timezone.utc)
    stable_time = now - timedelta(minutes=EXPORT_STABILITY_MINUTES + 10)

    task = _create_stuck_export_task()

    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = {
        "ContentLength": 5 * 1024**3,
        "LastModified": stable_time,
    }

    result = _process_stuck_export(task, mock_s3)

    _assert_recovered_export_result(result)
    _assert_recovered_export_output(capsys)


class TestProcessStuckExportEdgeCases:
    """Test edge cases and incomplete export scenarios."""

    def test_process_stuck_export_still_writing(self, capsys):
        """Test processing an export that is still being written."""
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(minutes=EXPORT_STABILITY_MINUTES - 5)

        task = {
            "ExportImageTaskId": "export-writing",
            "ImageId": "ami-writing",
            "S3ExportLocation": {
                "S3Bucket": "writing-bucket",
                "S3Prefix": "exports/",
            },
        }

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentLength": 3 * 1024**3,
            "LastModified": recent_time,
        }

        result = _process_stuck_export(task, mock_s3)

        assert result is None
        captured = capsys.readouterr()
        assert "File still being written" in captured.out

    def test_process_stuck_export_no_bucket_info(self, capsys):
        """Test processing when task has no bucket information."""
        task = {
            "ExportImageTaskId": "export-nobucket",
            "ImageId": "ami-nobucket",
            "S3ExportLocation": {},
        }

        mock_s3 = MagicMock()

        result = _process_stuck_export(task, mock_s3)

        assert result is None
        captured = capsys.readouterr()
        assert "No S3 bucket information found" in captured.out


class TestProcessStuckExportErrors:
    """Test error scenarios during stuck export processing."""

    def test_process_stuck_export_no_file(self, capsys):
        """Test processing when S3 file doesn't exist."""
        task = {
            "ExportImageTaskId": "export-nofile",
            "ImageId": "ami-nofile",
            "S3ExportLocation": {
                "S3Bucket": "test-bucket",
                "S3Prefix": "exports/",
            },
        }

        mock_s3 = MagicMock()

        class NoSuchKey(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchKey = NoSuchKey
        mock_s3.head_object.side_effect = NoSuchKey()

        result = _process_stuck_export(task, mock_s3)

        assert result is None
        captured = capsys.readouterr()
        assert "S3 file not found" in captured.out

    def test_process_stuck_export_s3_error(self, capsys):
        """Test processing when S3 check errors."""
        task = {
            "ExportImageTaskId": "export-error",
            "ImageId": "ami-error",
            "S3ExportLocation": {
                "S3Bucket": "error-bucket",
                "S3Prefix": "exports/",
            },
        }

        mock_s3 = MagicMock()

        class NoSuchKey(Exception):  # pylint: disable=missing-class-docstring
            pass

        mock_s3.exceptions.NoSuchKey = NoSuchKey
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "head_object"
        )

        result = _process_stuck_export(task, mock_s3)

        assert result is None
        captured = capsys.readouterr()
        assert "Error checking S3" in captured.out


class TestCheckActiveExports:
    """Test checking active exports in a region."""

    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.create_ec2_and_s3_clients")
    def test_check_active_exports_no_exports(self, mock_clients, capsys):
        """Test checking region with no active exports."""
        mock_ec2 = MagicMock()
        mock_s3 = MagicMock()
        mock_clients.return_value = (mock_ec2, mock_s3)
        mock_ec2.describe_export_image_tasks.return_value = {"ExportImageTasks": []}

        recovered = check_active_exports("us-east-1", "key", "secret")

        assert len(recovered) == 0
        captured = capsys.readouterr()
        assert "No active exports found" in captured.out

    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.create_ec2_and_s3_clients")
    def test_check_active_exports_with_stuck_export(self, mock_clients, capsys):
        """Test checking region with stuck export."""
        now = datetime.now(timezone.utc)
        stable_time = now - timedelta(minutes=EXPORT_STABILITY_MINUTES + 10)

        mock_ec2 = MagicMock()
        mock_s3 = MagicMock()
        mock_clients.return_value = (mock_ec2, mock_s3)
        mock_ec2.describe_export_image_tasks.return_value = {
            "ExportImageTasks": [
                {
                    "ExportImageTaskId": "export-stuck-80",
                    "ImageId": "ami-stuck-80",
                    "Status": "active",
                    "Progress": "80",
                    "StatusMessage": "converting",
                    "S3ExportLocation": {
                        "S3Bucket": "stuck-bucket",
                        "S3Prefix": "exports/",
                    },
                }
            ]
        }
        mock_s3.head_object.return_value = {
            "ContentLength": 10 * 1024**3,
            "LastModified": stable_time,
        }

        recovered = check_active_exports("us-west-2", "key", "secret")

        assert len(recovered) == 1
        assert recovered[0]["export_task_id"] == "export-stuck-80"
        captured = capsys.readouterr()
        assert "Classic 80% stuck scenario detected" in captured.out

    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.create_ec2_and_s3_clients")
    def test_check_active_exports_not_stuck_scenario(self, mock_clients, capsys):
        """Test export that is not the stuck scenario."""
        mock_ec2 = MagicMock()
        mock_s3 = MagicMock()
        mock_clients.return_value = (mock_ec2, mock_s3)
        mock_ec2.describe_export_image_tasks.return_value = {
            "ExportImageTasks": [
                {
                    "ExportImageTaskId": "export-normal",
                    "ImageId": "ami-normal",
                    "Status": "active",
                    "Progress": "50",
                    "StatusMessage": "exporting",
                }
            ]
        }

        recovered = check_active_exports("eu-west-1", "key", "secret")

        assert len(recovered) == 0
        captured = capsys.readouterr()
        assert "Not the classic stuck scenario" in captured.out
