"""Comprehensive tests for aws_export_recovery.py - Part 2 (Main Function Tests)."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.aws_export_recovery import main


class TestMain:
    """Test main function."""

    @patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.check_active_exports")
    def test_main_no_recoveries(self, mock_check, mock_load_creds, capsys):
        """Test main with no recovered exports."""
        mock_load_creds.return_value = ("key", "secret")
        mock_check.return_value = []
        main()
        assert mock_check.call_count == 4
        captured = capsys.readouterr()
        assert "AWS Export Recovery Script" in captured.out
        assert "RECOVERY SUMMARY" in captured.out
        assert "No completed exports found" in captured.out

    @patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.check_active_exports")
    def test_main_with_recoveries(self, mock_check, mock_load_creds, capsys):
        """Test main with recovered exports."""
        mock_load_creds.return_value = ("key", "secret")
        mock_check.side_effect = [
            [
                {
                    "export_task_id": "export-1",
                    "ami_id": "ami-1",
                    "bucket_name": "bucket-1",
                    "s3_key": "exports/export-1.vmdk",
                    "size_gb": 50.0,
                    "status": "recovered",
                }
            ],
            [],
            [
                {
                    "export_task_id": "export-2",
                    "ami_id": "ami-2",
                    "bucket_name": "bucket-2",
                    "s3_key": "exports/export-2.vmdk",
                    "size_gb": 100.0,
                    "status": "recovered",
                }
            ],
            [],
        ]
        main()
        captured = capsys.readouterr()
        assert "Found 2 likely completed export(s)" in captured.out
        assert "export-1" in captured.out
        assert "export-2" in captured.out
        assert "Total recovered data: 150.00 GB" in captured.out
        assert "Monthly savings" in captured.out
        assert "Annual savings" in captured.out
        assert "Next Steps" in captured.out


class TestMainSavingsCalculation:
    """Test main function savings calculation and error handling."""

    @patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.check_active_exports")
    def test_main_calculates_savings(self, mock_check, mock_load_creds, capsys):
        """Test that main calculates savings correctly."""
        mock_load_creds.return_value = ("key", "secret")
        mock_check.side_effect = [
            [
                {
                    "export_task_id": "export-savings",
                    "ami_id": "ami-savings",
                    "bucket_name": "bucket-savings",
                    "s3_key": "exports/export-savings.vmdk",
                    "size_gb": 100.0,
                    "status": "recovered",
                }
            ],
            [],
            [],
            [],
        ]
        main()
        captured = capsys.readouterr()
        ebs_cost = 100.0 * 0.05
        s3_cost = 100.0 * 0.023
        monthly_savings = ebs_cost - s3_cost
        annual_savings = monthly_savings * 12
        assert f"${monthly_savings:.2f}" in captured.out
        assert f"${annual_savings:.2f}" in captured.out

    @patch("cost_toolkit.common.credential_utils.setup_aws_credentials")
    @patch("cost_toolkit.scripts.optimization.aws_export_recovery.check_active_exports")
    def test_main_with_client_error(self, mock_check, mock_load_creds, capsys):
        """Test main handles client errors gracefully."""
        mock_load_creds.return_value = ("key", "secret")
        mock_check.side_effect = [
            ClientError({"Error": {"Code": "ServiceError"}}, "describe_export_image_tasks"),
            [],
            [],
            [],
        ]
        main()
        captured = capsys.readouterr()
        assert "Error checking" in captured.out
        assert "RECOVERY SUMMARY" in captured.out
