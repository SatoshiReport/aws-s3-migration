"""Comprehensive tests for cost_toolkit/scripts/rds/fix_rds_subnet_routing.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.rds.fix_rds_subnet_routing import fix_rds_subnet_routing, main


@patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
@patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
@patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
def test_fix_subnet_routing_success(
    mock_create_subnet_group, mock_setup_creds, mock_boto_client, capsys
):
    """Test successfully fixing subnet routing."""
    mock_rds = MagicMock()
    mock_waiter = MagicMock()
    mock_rds.get_waiter.return_value = mock_waiter
    mock_boto_client.return_value = mock_rds

    fix_rds_subnet_routing()

    mock_setup_creds.assert_called_once()
    mock_boto_client.assert_called_once_with("rds", region_name="us-east-1")
    mock_create_subnet_group.assert_called_once_with(
        mock_rds, "public-subnet-group", "Public subnets only for internet access"
    )

    mock_rds.modify_db_instance.assert_called_once_with(
        DBInstanceIdentifier="simba-db-restored",
        DBSubnetGroupName="public-subnet-group",
        ApplyImmediately=True,
    )

    mock_rds.get_waiter.assert_called_once_with("db_instance_available")
    mock_waiter.wait.assert_called_once_with(
        DBInstanceIdentifier="simba-db-restored", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
    )

    captured = capsys.readouterr()
    assert "Fixing RDS subnet routing for internet access..." in captured.out
    assert "Moving RDS instance to public subnet group..." in captured.out
    assert "RDS instance modification initiated!" in captured.out
    assert "Waiting for modification to complete..." in captured.out
    assert "This may take 5-10 minutes..." in captured.out
    assert "RDS instance is now in public subnets!" in captured.out
    assert "You should now be able to connect from the internet" in captured.out


class TestFixRdsSubnetRoutingErrors:
    """Tests for fix_rds_subnet_routing function - error handling."""

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_modify_instance_error(
        self, _mock_create_subnet_group, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling error when modifying instance."""
        mock_rds = MagicMock()
        mock_boto_client.return_value = mock_rds
        mock_rds.modify_db_instance.side_effect = ClientError(
            {"Error": {"Code": "InvalidDBInstanceState", "Message": "instance not available"}},
            "ModifyDBInstance",
        )

        fix_rds_subnet_routing()

        captured = capsys.readouterr()
        assert "Error fixing subnet routing:" in captured.out

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_subnet_group_creation_error(
        self, mock_create_subnet_group, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling error when creating subnet group."""
        mock_rds = MagicMock()
        mock_boto_client.return_value = mock_rds
        mock_create_subnet_group.side_effect = ClientError(
            {"Error": {"Code": "InvalidSubnet", "Message": "Invalid subnet"}},
            "CreateDBSubnetGroup",
        )

        fix_rds_subnet_routing()

        captured = capsys.readouterr()
        assert "Error fixing subnet routing:" in captured.out

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_waiter_timeout(
        self, _mock_create_subnet_group, _mock_setup_creds, mock_boto_client
    ):
        """Test that waiter timeout exception propagates (wrapped in ClientError)."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = Exception("Waiter exceeded max attempts")
        mock_rds.get_waiter.return_value = mock_waiter
        mock_boto_client.return_value = mock_rds

        # The current code wraps in try/except ClientError, but waiters can raise other exceptions
        # This test verifies the exception is raised
        with pytest.raises(Exception, match="Waiter exceeded max attempts"):
            fix_rds_subnet_routing()


class TestFixRdsSubnetRoutingConfiguration:
    """Tests for fix_rds_subnet_routing function - configuration validation."""

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_apply_immediately(
        self, _mock_create_subnet_group, _mock_setup_creds, mock_boto_client
    ):
        """Test that modification is applied immediately."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_boto_client.return_value = mock_rds

        fix_rds_subnet_routing()

        call_args = mock_rds.modify_db_instance.call_args[1]
        assert call_args["ApplyImmediately"] is True

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_correct_instance_id(
        self, _mock_create_subnet_group, _mock_setup_creds, mock_boto_client
    ):
        """Test that correct instance ID is used."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_boto_client.return_value = mock_rds

        fix_rds_subnet_routing()

        call_args = mock_rds.modify_db_instance.call_args[1]
        assert call_args["DBInstanceIdentifier"] == "simba-db-restored"

        waiter_args = mock_waiter.wait.call_args[1]
        assert waiter_args["DBInstanceIdentifier"] == "simba-db-restored"

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_waiter_config(
        self, _mock_create_subnet_group, _mock_setup_creds, mock_boto_client
    ):
        """Test that waiter is configured correctly."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_boto_client.return_value = mock_rds

        fix_rds_subnet_routing()

        waiter_args = mock_waiter.wait.call_args[1]
        assert waiter_args["WaiterConfig"]["Delay"] == 30
        assert waiter_args["WaiterConfig"]["MaxAttempts"] == 20

    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.create_public_subnet_group")
    def test_fix_subnet_routing_correct_subnet_group_name(
        self, mock_create_subnet_group, _mock_setup_creds, mock_boto_client
    ):
        """Test that correct subnet group name is used."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter
        mock_boto_client.return_value = mock_rds

        fix_rds_subnet_routing()

        mock_create_subnet_group.assert_called_once_with(
            mock_rds, "public-subnet-group", "Public subnets only for internet access"
        )

        call_args = mock_rds.modify_db_instance.call_args[1]
        assert call_args["DBSubnetGroupName"] == "public-subnet-group"


@patch("cost_toolkit.scripts.rds.fix_rds_subnet_routing.fix_rds_subnet_routing")
def test_main_calls_fix_rds_subnet_routing(mock_fix):
    """Test that main calls fix_rds_subnet_routing."""
    main()

    mock_fix.assert_called_once()
