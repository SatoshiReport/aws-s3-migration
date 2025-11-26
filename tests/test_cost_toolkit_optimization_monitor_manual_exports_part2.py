"""Comprehensive tests for monitor_manual_exports.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.monitor_manual_exports import (
    check_specific_ami,
    main,
    monitor_all_regions,
)


@patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_export_status")
@patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_s3_files")
def test_monitor_all_regions(mock_check_files, mock_check_status, capsys):
    """Test monitoring all regions."""
    mock_check_status.side_effect = [
        [{"Status": "active", "ImageId": "ami-1"}],
        [{"Status": "completed", "ImageId": "ami-2"}],
    ]
    mock_check_files.side_effect = [
        [{"size_gb": 10.0, "key": "file1.vmdk"}],
        [{"size_gb": 20.0, "key": "file2.vmdk"}],
    ]

    monitor_all_regions()

    assert mock_check_status.call_count == 2
    assert mock_check_files.call_count == 2
    captured = capsys.readouterr()
    assert "AWS Export Monitor" in captured.out
    assert "SUMMARY" in captured.out


class TestCheckSpecificAmi:
    """Test checking specific AMI exports."""

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_export_status")
    def test_check_specific_ami_with_files(self, mock_check_status, mock_boto_client, capsys):
        """Test checking specific AMI with S3 files."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_check_status.return_value = []
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "ebs-snapshots/ami-specific/export.vmdk",
                    "Size": 5 * 1024**3,
                }
            ]
        }

        check_specific_ami("us-east-1", "ami-specific")

        captured = capsys.readouterr()
        assert "Checking AMI ami-specific" in captured.out
        assert "S3 files for AMI ami-specific" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_export_status")
    def test_check_specific_ami_no_files(self, mock_check_status, mock_boto_client, capsys):
        """Test checking specific AMI with no S3 files."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_check_status.return_value = []
        mock_s3.list_objects_v2.return_value = {}

        check_specific_ami("us-west-2", "ami-nofiles")

        captured = capsys.readouterr()
        assert "No S3 files found for AMI ami-nofiles" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.boto3.client")
    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_export_status")
    def test_check_specific_ami_s3_error(self, mock_check_status, mock_boto_client, capsys):
        """Test checking specific AMI with S3 error."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_check_status.return_value = []
        mock_s3.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "list_objects_v2"
        )

        check_specific_ami("us-east-1", "ami-error")

        captured = capsys.readouterr()
        assert "Error checking S3 for AMI ami-error" in captured.out


class TestMain:
    """Test main function."""

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.monitor_all_regions")
    def test_main_default(self, mock_monitor):
        """Test main with default arguments."""
        with patch("sys.argv", ["monitor_manual_exports.py"]):
            main()
        mock_monitor.assert_called_once()

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.check_specific_ami")
    def test_main_specific_ami(self, mock_check_ami):
        """Test main with specific AMI."""
        with patch(
            "sys.argv", ["monitor_manual_exports.py", "--region", "us-east-1", "--ami", "ami-test"]
        ):
            main()
        mock_check_ami.assert_called_once_with("us-east-1", "ami-test")

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.monitor_all_regions")
    def test_main_keyboard_interrupt(self, mock_monitor, capsys):
        """Test main with keyboard interrupt."""
        mock_monitor.side_effect = KeyboardInterrupt()
        with patch("sys.argv", ["monitor_manual_exports.py"]):
            main()
        captured = capsys.readouterr()
        assert "Monitoring stopped" in captured.out

    @patch("cost_toolkit.scripts.optimization.monitor_manual_exports.monitor_all_regions")
    def test_main_client_error(self, mock_monitor, capsys):
        """Test main with client error."""
        mock_monitor.side_effect = ClientError({"Error": {"Code": "Error"}}, "operation")
        with patch("sys.argv", ["monitor_manual_exports.py"]):
            main()
        captured = capsys.readouterr()
        assert "Error" in captured.out
