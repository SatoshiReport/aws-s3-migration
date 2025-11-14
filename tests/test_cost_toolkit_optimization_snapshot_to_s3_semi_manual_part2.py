"""Comprehensive tests for aws_snapshot_to_s3_semi_manual.py - Part 2."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual import main


def test_main_success(capsys):
    """Test successful main execution."""
    mod = "cost_toolkit.scripts.optimization.aws_snapshot_to_s3_semi_manual"
    with (
        patch(f"{mod}.load_aws_credentials_from_env") as mock_load_creds,
        patch(f"{mod}._get_target_snapshots") as mock_get_snapshots,
        patch(f"{mod}._prepare_all_snapshots") as mock_prepare,
        patch(f"{mod}.generate_manual_commands") as mock_generate,
        patch(f"{mod}._save_commands_to_file") as mock_save,
    ):
        mock_load_creds.return_value = ("access_key", "secret_key")
        mock_get_snapshots.return_value = [
            {
                "snapshot_id": "snap-1",
                "region": "us-east-1",
                "size_gb": 8,
                "description": "Test",
            }
        ]
        mock_prepare.return_value = [
            {
                "snapshot_id": "snap-1",
                "ami_id": "ami-1",
                "bucket_name": "bucket-1",
                "region": "us-east-1",
                "size_gb": 8,
                "monthly_savings": 0.22,
                "description": "Test",
            }
        ]
        mock_generate.return_value = (["export"], ["monitor"], ["cleanup"])

        main()

        mock_load_creds.assert_called_once()
        mock_get_snapshots.assert_called_once()
        mock_prepare.assert_called_once()
        mock_generate.assert_called_once()
        mock_save.assert_called_once()
        captured = capsys.readouterr()
        assert "PREPARATION COMPLETE" in captured.out
