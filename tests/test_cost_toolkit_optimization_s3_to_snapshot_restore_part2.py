"""Comprehensive tests for aws_s3_to_snapshot_restore.py - Part 2."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore import (
    _confirm_restore_operation,
    _get_and_validate_exports,
    _get_user_inputs,
    _perform_restores,
    _print_restore_summary,
    _process_export_restore,
    _select_exports,
)


class TestSelectExports:
    """Test export selection functionality."""

    def test_select_single_export(self, monkeypatch):
        """Test selecting a single export."""
        exports = [
            {"key": "snap1.vmdk", "size": 1024 * 1024, "last_modified": datetime.now()},
            {"key": "snap2.vmdk", "size": 2048 * 1024, "last_modified": datetime.now()},
        ]
        monkeypatch.setattr("builtins.input", lambda _: "1")

        selected = _select_exports(exports)

        assert len(selected) == 1
        assert selected[0]["key"] == "snap1.vmdk"

    def test_select_all_exports(self, monkeypatch):
        """Test selecting all exports."""
        exports = [
            {"key": "snap1.vmdk", "size": 1024, "last_modified": datetime.now()},
            {"key": "snap2.vmdk", "size": 2048, "last_modified": datetime.now()},
        ]
        monkeypatch.setattr("builtins.input", lambda _: "all")

        selected = _select_exports(exports)

        assert len(selected) == 2

    def test_select_invalid_input(self, monkeypatch):
        """Test invalid selection."""
        exports = [{"key": "snap1.vmdk", "size": 1024, "last_modified": datetime.now()}]
        monkeypatch.setattr("builtins.input", lambda _: "invalid")

        selected = _select_exports(exports)

        assert selected is None


class TestProcessExportRestore:
    """Test export restore processing."""

    def test_process_restore_success(self):
        """Test successful restore processing."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-123"}
        mock_ec2.describe_import_image_tasks.return_value = {
            "ImportImageTasks": [
                {"ImportTaskId": "import-123", "Status": "completed", "ImageId": "ami-111"}
            ]
        }
        mock_ec2.describe_images.return_value = {
            "Images": [
                {
                    "RootDeviceName": "/dev/sda1",
                    "BlockDeviceMappings": [
                        {"DeviceName": "/dev/sda1", "Ebs": {"SnapshotId": "snap-222"}}
                    ],
                }
            ]
        }

        export = {"key": "exports/test.vmdk", "size": 1024}
        result = _process_export_restore(mock_ec2, "test-bucket", export)

        assert result is not None
        assert result["ami_id"] == "ami-111"
        assert result["snapshot_id"] == "snap-222"
        assert result["s3_key"] == "exports/test.vmdk"

    def test_process_restore_import_failure(self, capsys):
        """Test restore when import fails."""
        mock_ec2 = MagicMock()
        mock_ec2.import_image.return_value = {"ImportTaskId": "import-fail"}
        mock_ec2.describe_import_image_tasks.return_value = {
            "ImportImageTasks": [{"ImportTaskId": "import-fail", "Status": "failed"}]
        }

        export = {"key": "exports/bad.vmdk", "size": 1024}
        result = _process_export_restore(mock_ec2, "test-bucket", export)

        assert result is None
        captured = capsys.readouterr()
        assert "Failed to import AMI from S3" in captured.out


class TestPrintRestoreSummary:
    """Test restore summary printing."""

    def test_print_summary_with_results(self, capsys):
        """Test printing summary with successful restores."""
        results = [
            {"s3_key": "snap1.vmdk", "ami_id": "ami-111", "snapshot_id": "snap-111"},
            {"s3_key": "snap2.vmdk", "ami_id": "ami-222", "snapshot_id": "snap-222"},
        ]
        selected = [{"key": "snap1.vmdk"}, {"key": "snap2.vmdk"}, {"key": "snap3.vmdk"}]

        _print_restore_summary(results, selected, "us-east-1")

        captured = capsys.readouterr()
        assert "Successfully restored: 2 snapshots" in captured.out
        assert "Failed to restore: 1 exports" in captured.out
        assert "snap-111" in captured.out
        assert "snap-222" in captured.out

    def test_print_summary_no_results(self, capsys):
        """Test printing summary with no successful restores."""
        _print_restore_summary([], [{"key": "snap1.vmdk"}], "us-west-2")

        captured = capsys.readouterr()
        assert "Successfully restored: 0 snapshots" in captured.out
        assert "Failed to restore: 1 exports" in captured.out


class TestGetUserInputs:
    """Test user input gathering."""

    def test_get_user_inputs_valid(self, monkeypatch):
        """Test getting valid inputs."""
        inputs = iter(["us-east-1", "my-bucket"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        region, bucket = _get_user_inputs()

        assert region == "us-east-1"
        assert bucket == "my-bucket"

    def test_get_user_inputs_empty_region(self, monkeypatch):
        """Test with empty region."""
        monkeypatch.setattr("builtins.input", lambda _: "")

        region, bucket = _get_user_inputs()

        assert region is None
        assert bucket is None

    def test_get_user_inputs_empty_bucket(self, monkeypatch):
        """Test with empty bucket name."""
        inputs = iter(["us-west-2", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        region, bucket = _get_user_inputs()

        assert region == "us-west-2"
        assert bucket is None


class TestConfirmRestoreOperation:
    """Test restore operation confirmation."""

    def test_confirm_with_correct_input(self, monkeypatch, capsys):
        """Test confirmation with correct input."""
        monkeypatch.setattr("builtins.input", lambda _: "RESTORE FROM S3")

        result = _confirm_restore_operation([{"key": "test.vmdk"}])

        assert result is True
        captured = capsys.readouterr()
        assert "Proceeding with S3 restore" in captured.out

    def test_confirm_with_incorrect_input(self, monkeypatch, capsys):
        """Test confirmation with incorrect input."""
        monkeypatch.setattr("builtins.input", lambda _: "wrong")

        result = _confirm_restore_operation([{"key": "test.vmdk"}])

        assert result is False
        captured = capsys.readouterr()
        assert "Operation cancelled" in captured.out


class TestPerformRestores:
    """Test performing multiple restores."""

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore._process_export_restore")
    def test_perform_restores_all_success(self, mock_process):
        """Test performing multiple successful restores."""
        mock_ec2 = MagicMock()
        mock_process.side_effect = [
            {"s3_key": "snap1.vmdk", "ami_id": "ami-1", "snapshot_id": "snap-1"},
            {"s3_key": "snap2.vmdk", "ami_id": "ami-2", "snapshot_id": "snap-2"},
        ]

        exports = [{"key": "snap1.vmdk"}, {"key": "snap2.vmdk"}]
        results = _perform_restores(mock_ec2, "test-bucket", exports)

        assert len(results) == 2
        assert mock_process.call_count == 2

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore._process_export_restore")
    def test_perform_restores_with_failures(self, mock_process):
        """Test performing restores with some failures."""
        mock_ec2 = MagicMock()
        mock_process.side_effect = [
            {"s3_key": "snap1.vmdk", "ami_id": "ami-1", "snapshot_id": "snap-1"},
            None,
            {"s3_key": "snap3.vmdk", "ami_id": "ami-3", "snapshot_id": "snap-3"},
        ]

        exports = [{"key": "snap1.vmdk"}, {"key": "snap2.vmdk"}, {"key": "snap3.vmdk"}]
        results = _perform_restores(mock_ec2, "test-bucket", exports)

        assert len(results) == 2


class TestGetAndValidateExports:
    """Test getting and validating exports."""

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.list_s3_exports")
    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore._select_exports")
    def test_get_and_validate_exports_success(self, mock_select, mock_list):
        """Test successful export validation."""
        mock_list.return_value = [
            {"key": "snap1.vmdk", "size": 1024, "last_modified": datetime.now()}
        ]
        mock_select.return_value = [{"key": "snap1.vmdk"}]

        mock_s3 = MagicMock()
        result = _get_and_validate_exports(mock_s3, "test-bucket")

        assert result is not None
        assert len(result) == 1

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.list_s3_exports")
    def test_get_and_validate_exports_no_exports(self, mock_list, capsys):
        """Test when no exports found."""
        mock_list.return_value = []

        mock_s3 = MagicMock()
        result = _get_and_validate_exports(mock_s3, "test-bucket")

        assert result is None
        captured = capsys.readouterr()
        assert "No snapshot exports found" in captured.out

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.list_s3_exports")
    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore._select_exports")
    def test_get_and_validate_exports_invalid_selection(self, mock_select, mock_list, capsys):
        """Test with invalid selection."""
        mock_list.return_value = [
            {"key": "snap1.vmdk", "size": 1024, "last_modified": datetime.now()}
        ]
        mock_select.return_value = None

        mock_s3 = MagicMock()
        result = _get_and_validate_exports(mock_s3, "test-bucket")

        assert result is None
        captured = capsys.readouterr()
        assert "Invalid selection" in captured.out
