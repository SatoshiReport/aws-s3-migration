"""Comprehensive tests for aws_s3_to_snapshot_restore.py - Part 3."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore import main


class TestMain:
    """Test main function."""

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.restore_snapshots_from_s3")
    def test_main_success(self, mock_restore):
        """Test successful main execution."""
        main()
        mock_restore.assert_called_once()

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.restore_snapshots_from_s3")
    def test_main_client_error(self, mock_restore):
        """Test main with ClientError."""
        mock_restore.side_effect = ClientError({"Error": {"Code": "Error"}}, "operation")

        try:
            main()
        except SystemExit as e:
            assert e.code == 1

    @patch("cost_toolkit.scripts.optimization.aws_s3_to_snapshot_restore.restore_snapshots_from_s3")
    def test_main_keyboard_interrupt(self, mock_restore):
        """Test main with KeyboardInterrupt."""
        mock_restore.side_effect = KeyboardInterrupt()

        try:
            main()
        except SystemExit as e:
            assert e.code == 1
