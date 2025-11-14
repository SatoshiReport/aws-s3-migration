"""Comprehensive tests for cost_toolkit/scripts/rds/enable_rds_public_access.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.rds.enable_rds_public_access import enable_public_access, main


@patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
@patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
def test_enable_public_access_success(_mock_setup_creds, mock_create_client, capsys):
    """Test successfully enabling public access."""
    mock_rds = MagicMock()
    mock_waiter = MagicMock()
    mock_rds.get_waiter.return_value = mock_waiter
    mock_create_client.return_value = mock_rds

    enable_public_access()

    _mock_setup_creds.assert_called_once()
    mock_create_client.assert_called_once_with(region="us-east-1")

    mock_rds.modify_db_instance.assert_called_once_with(
        DBInstanceIdentifier="simba-db-restored", PubliclyAccessible=True, ApplyImmediately=True
    )

    mock_rds.get_waiter.assert_called_once_with("db_instance_available")
    mock_waiter.wait.assert_called_once_with(
        DBInstanceIdentifier="simba-db-restored", WaiterConfig={"Delay": 30, "MaxAttempts": 10}
    )

    captured = capsys.readouterr()
    assert "Enabling public access to restored RDS instance..." in captured.out
    assert "This is temporary - we'll disable it after data migration" in captured.out
    assert "Public access enabled!" in captured.out
    assert "Waiting for modification to complete..." in captured.out
    assert "This may take 2-3 minutes..." in captured.out
    assert "RDS instance is now publicly accessible!" in captured.out
    assert "You can now connect to explore your data" in captured.out


class TestEnablePublicAccessErrors:
    """Tests for enable_public_access function - error handling."""

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_modify_error(self, _mock_setup_creds, mock_create_client, capsys):
        """Test handling error when modifying instance."""
        mock_rds = MagicMock()
        mock_create_client.return_value = mock_rds
        mock_rds.modify_db_instance.side_effect = ClientError(
            {"Error": {"Code": "InvalidDBInstanceState", "Message": "instance not available"}},
            "ModifyDBInstance",
        )

        enable_public_access()

        captured = capsys.readouterr()
        assert "Error enabling public access:" in captured.out

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_waiter_timeout(self, _mock_setup_creds, mock_create_client):
        """Test that waiter timeout exception propagates (wrapped in ClientError)."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("Waiter exceeded max attempts")
        mock_rds.get_waiter.return_value = mock_waiter
        mock_create_client.return_value = mock_rds

        # The current code wraps in try/except ClientError, but waiters can raise other exceptions
        # This test verifies the exception is raised
        with pytest.raises(Exception, match="Waiter exceeded max attempts"):
            enable_public_access()

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_instance_not_found(
        self, _mock_setup_creds, mock_create_client, capsys
    ):
        """Test handling when instance is not found."""
        mock_rds = MagicMock()
        mock_create_client.return_value = mock_rds
        mock_rds.modify_db_instance.side_effect = ClientError(
            {"Error": {"Code": "DBInstanceNotFound", "Message": "instance does not exist"}},
            "ModifyDBInstance",
        )

        enable_public_access()

        captured = capsys.readouterr()
        assert "Error enabling public access:" in captured.out

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_insufficient_permissions(
        self, _mock_setup_creds, mock_create_client, capsys
    ):
        """Test handling when user lacks permissions."""
        mock_rds = MagicMock()
        mock_create_client.return_value = mock_rds
        mock_rds.modify_db_instance.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "insufficient permissions"}},
            "ModifyDBInstance",
        )

        enable_public_access()

        captured = capsys.readouterr()
        assert "Error enabling public access:" in captured.out


class TestEnablePublicAccessConfiguration:
    """Tests for enable_public_access function - configuration validation."""

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_apply_immediately(self, _mock_setup_creds, mock_create_client):
        """Test that modification is applied immediately."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_create_client.return_value = mock_rds

        enable_public_access()

        call_args = mock_rds.modify_db_instance.call_args[1]
        assert call_args["ApplyImmediately"] is True
        assert call_args["PubliclyAccessible"] is True

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_correct_instance_id(self, _mock_setup_creds, mock_create_client):
        """Test that correct instance ID is used."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_create_client.return_value = mock_rds

        enable_public_access()

        call_args = mock_rds.modify_db_instance.call_args[1]
        assert call_args["DBInstanceIdentifier"] == "simba-db-restored"

        waiter_args = mock_waiter.wait.call_args[1]
        assert waiter_args["DBInstanceIdentifier"] == "simba-db-restored"

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_waiter_config(self, _mock_setup_creds, mock_create_client):
        """Test that waiter is configured correctly."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_create_client.return_value = mock_rds

        enable_public_access()

        mock_rds.get_waiter.assert_called_once_with("db_instance_available")
        waiter_args = mock_waiter.wait.call_args[1]
        assert waiter_args["WaiterConfig"]["Delay"] == 30
        assert waiter_args["WaiterConfig"]["MaxAttempts"] == 10

    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.create_rds_client")
    @patch("cost_toolkit.scripts.rds.enable_rds_public_access.setup_aws_credentials")
    def test_enable_public_access_client_creation(self, _mock_setup_creds, mock_create_client):
        """Test that RDS client is created with correct region."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_create_client.return_value = mock_rds

        enable_public_access()

        mock_create_client.assert_called_once_with(region="us-east-1")


@patch("cost_toolkit.scripts.rds.enable_rds_public_access.enable_public_access")
def test_main_calls_enable_public_access(mock_enable):
    """Test that main calls enable_public_access."""
    main()

    mock_enable.assert_called_once()
