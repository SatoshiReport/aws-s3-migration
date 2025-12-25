"""Comprehensive tests for aws_migration_monitor.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_migration_monitor import (
    _check_bucket_contents,
    _check_migration_log,
    _print_cost_summary,
    main,
    monitor_migration,
)


@patch("cost_toolkit.scripts.migration.aws_migration_monitor._print_cost_summary")
@patch("cost_toolkit.scripts.migration.aws_migration_monitor._check_migration_log")
@patch("cost_toolkit.scripts.migration.aws_migration_monitor._check_bucket_contents")
@patch("cost_toolkit.scripts.migration.aws_migration_monitor.aws_utils.setup_aws_credentials")
@patch("cost_toolkit.scripts.migration.aws_migration_monitor.boto3.client")
def test_setup_credentials_calls_utils(
    mock_boto_client,
    mock_setup_creds,
    _mock_check_bucket,
    _mock_check_log,
    _mock_cost_summary,
):
    """monitor_migration should initialize shared credentials."""
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    monitor_migration()

    mock_setup_creds.assert_called_once()
    mock_boto_client.assert_called_once_with("s3", region_name="eu-west-2")


class TestCheckBucketContents:
    """Tests for _check_bucket_contents function."""

    def test_check_bucket_with_files(self, capsys):
        """Test checking bucket with files."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "home/user/file.txt", "Size": 1048576},
                {"Key": "opt/app/config.json", "Size": 2097152},
                {"Key": "var/log/app.log", "Size": 512000},
            ]
        }

        _check_bucket_contents(mock_s3, "test-bucket")

        mock_s3.list_objects_v2.assert_called_once_with(Bucket="test-bucket")
        captured = capsys.readouterr()
        assert "CHECKING S3 BUCKET CONTENTS" in captured.out
        assert "SUMMARY" in captured.out
        assert "Files: 3" in captured.out

    def test_check_bucket_calculates_size(self, capsys):
        """Test bucket size calculation."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "file1.txt", "Size": 1073741824},
                {"Key": "file2.txt", "Size": 1073741824},
            ]
        }

        _check_bucket_contents(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "Total size:" in captured.out
        assert "GB" in captured.out
        assert "Estimated monthly cost:" in captured.out

    def test_check_bucket_empty(self, capsys):
        """Test checking empty bucket."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {}

        _check_bucket_contents(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "No files found yet" in captured.out
        assert "migration may still be starting" in captured.out

    def test_check_bucket_filters_relevant_files(self, capsys):
        """Test bucket content filtering for relevant paths."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "home/user/data.txt", "Size": 1024},
                {"Key": "random/file.tmp", "Size": 2048},
                {"Key": "opt/config.json", "Size": 4096},
            ]
        }

        _check_bucket_contents(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "home/" in captured.out
        assert "opt/" in captured.out

    def test_check_bucket_handles_error(self, capsys):
        """Test error handling when listing bucket fails."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "list_objects_v2")

        _check_bucket_contents(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "Could not list bucket contents" in captured.out


class TestCheckMigrationLog:
    """Tests for _check_migration_log function."""

    def test_check_log_exists(self, capsys):
        """Test checking existing migration log."""
        mock_s3 = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"Migration started\nSyncing files\nCompleted\n"
        mock_s3.get_object.return_value = {"Body": mock_response}

        _check_migration_log(mock_s3, "test-bucket")

        mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="migration-log.txt")
        captured = capsys.readouterr()
        assert "CHECKING MIGRATION LOG" in captured.out
        assert "Latest migration log" in captured.out

    def test_check_log_truncates_output(self, capsys):
        """Test log output is truncated to last 20 lines."""
        mock_s3 = MagicMock()
        mock_response = MagicMock()
        log_lines = "\n".join([f"Line {i}" for i in range(50)])
        mock_response.read.return_value = log_lines.encode("utf-8")
        mock_s3.get_object.return_value = {"Body": mock_response}

        _check_migration_log(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        output_lines = [line for line in captured.out.split("\n") if line.strip().startswith("Line")]
        assert len(output_lines) <= 20

    def test_check_log_not_found(self, capsys):
        """Test when migration log doesn't exist."""
        mock_s3 = MagicMock()
        mock_s3.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
        mock_s3.get_object.side_effect = mock_s3.exceptions.NoSuchKey()

        _check_migration_log(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "Migration log not yet available" in captured.out

    def test_check_log_handles_client_error(self, capsys):
        """Test error handling for log retrieval."""
        mock_s3 = MagicMock()
        mock_s3.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
        mock_s3.get_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "get_object")

        _check_migration_log(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "Could not read migration log" in captured.out

    def test_check_log_skips_empty_lines(self, capsys):
        """Test empty lines are filtered from output."""
        mock_s3 = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"Line 1\n\n\nLine 2\n\n"
        mock_s3.get_object.return_value = {"Body": mock_response}

        _check_migration_log(mock_s3, "test-bucket")

        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out


class TestPrintCostSummary:
    """Tests for _print_cost_summary function."""

    def test_print_summary_output(self, capsys):
        """Test cost summary is printed correctly."""
        _print_cost_summary()

        captured = capsys.readouterr()
        assert "COST OPTIMIZATION SUMMARY" in captured.out
        assert "EBS Volume Cleanup" in captured.out
        assert "$81.92/month" in captured.out
        assert "EBS to S3 Migration" in captured.out
        assert "$25.54/month" in captured.out
        assert "TOTAL EXPECTED OPTIMIZATION" in captured.out
        assert "$191.94/month" in captured.out

    def test_print_summary_includes_all_volumes(self, capsys):
        """Test summary includes all removed volumes."""
        _print_cost_summary()

        captured = capsys.readouterr()
        assert "Tars" in captured.out
        assert "1024 GB" in captured.out
        assert "32 GB" in captured.out


class TestMonitorMigration:
    """Tests for monitor_migration function."""

    def test_monitor_migration_success(self, capsys):
        """Test successful migration monitoring."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "home/file.txt", "Size": 1024}]}
            mock_response = MagicMock()
            mock_response.read.return_value = b"Migration log"
            mock_s3.get_object.return_value = {"Body": mock_response}
            mock_client.return_value = mock_s3

            monitor_migration()

        captured = capsys.readouterr()
        assert "AWS Migration Monitor" in captured.out
        assert "Started monitoring at:" in captured.out

    def test_monitor_migration_handles_error(self, capsys):
        """Test error handling during migration monitoring."""
        with patch("boto3.client") as mock_client:
            with patch("cost_toolkit.scripts.migration.aws_migration_monitor._check_bucket_contents") as mock_check:
                mock_check.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "list_objects_v2")
                mock_s3 = MagicMock()
                mock_client.return_value = mock_s3

                monitor_migration()

        captured = capsys.readouterr()
        assert "Error monitoring migration" in captured.out

    def test_monitor_uses_correct_region(self):
        """Test monitor uses correct AWS region."""
        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.list_objects_v2.return_value = {}
            mock_client.return_value = mock_s3

            monitor_migration()

        mock_client.assert_called_once_with("s3", region_name="eu-west-2")

    def test_monitor_calls_all_checks(self):
        """Test monitor calls all check functions."""
        with patch("boto3.client") as mock_client:
            with patch("cost_toolkit.scripts.migration.aws_migration_monitor._check_bucket_contents") as mock_bucket:
                with patch("cost_toolkit.scripts.migration.aws_migration_monitor._check_migration_log") as mock_log:
                    with patch("cost_toolkit.scripts.migration.aws_migration_monitor." "_print_cost_summary") as mock_summary:
                        mock_s3 = MagicMock()
                        mock_client.return_value = mock_s3

                        monitor_migration()

        mock_bucket.assert_called_once()
        mock_log.assert_called_once()
        mock_summary.assert_called_once()


def test_main_calls_monitor_migration():
    """Test main function calls monitor_migration."""
    with patch("cost_toolkit.scripts.migration.aws_migration_monitor.monitor_migration") as mock_mon:
        main()
    mock_mon.assert_called_once()
