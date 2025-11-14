"""Comprehensive tests for cost_toolkit/scripts/rds/fix_default_subnet_group.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.rds.fix_default_subnet_group import (
    _create_migration_snapshot,
    _restore_instance_to_public_subnet,
    fix_default_subnet_group,
    main,
)


class TestCreateMigrationSnapshot:
    """Tests for _create_migration_snapshot function."""

    def test_create_snapshot_success(self, capsys):
        """Test creating snapshot successfully."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter

        _create_migration_snapshot(mock_rds, "test-snapshot")

        mock_rds.create_db_snapshot.assert_called_once_with(
            DBSnapshotIdentifier="test-snapshot", DBInstanceIdentifier="simba-db-restored"
        )
        mock_waiter.wait.assert_called_once_with(
            DBSnapshotIdentifier="test-snapshot", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
        )

        captured = capsys.readouterr()
        assert "Snapshot creation initiated: test-snapshot" in captured.out
        assert "Waiting for snapshot to complete..." in captured.out
        assert "Snapshot completed!" in captured.out

    def test_create_snapshot_already_exists(self, capsys):
        """Test handling when snapshot already exists."""
        mock_rds = MagicMock()
        mock_rds.create_db_snapshot.side_effect = ClientError(
            {"Error": {"Code": "DBSnapshotAlreadyExists", "Message": "already exists"}},
            "CreateDBSnapshot",
        )

        _create_migration_snapshot(mock_rds, "existing-snapshot")

        captured = capsys.readouterr()
        assert "Snapshot existing-snapshot already exists, proceeding..." in captured.out

    def test_create_snapshot_other_error(self):
        """Test handling other errors during snapshot creation."""
        mock_rds = MagicMock()
        mock_rds.create_db_snapshot.side_effect = ClientError(
            {"Error": {"Code": "InvalidDBInstanceState", "Message": "instance not available"}},
            "CreateDBSnapshot",
        )

        try:
            _create_migration_snapshot(mock_rds, "test-snapshot")
            assert False, "Expected ClientError to be raised"
        except ClientError as e:
            assert e.response["Error"]["Code"] == "InvalidDBInstanceState"

    def test_create_snapshot_waiter_timeout(self):
        """Test handling waiter timeout."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = RuntimeError("Waiter exceeded max attempts")
        mock_rds.get_waiter.return_value = mock_waiter

        try:
            _create_migration_snapshot(mock_rds, "test-snapshot")
            assert False, "Expected exception to be raised"
        except RuntimeError as e:
            assert "Waiter exceeded max attempts" in str(e)

    def test_create_snapshot_waiter_config(self):
        """Test that waiter is configured correctly."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter

        _create_migration_snapshot(mock_rds, "test-snapshot")

        mock_rds.get_waiter.assert_called_once_with("db_snapshot_completed")
        waiter_call_args = mock_waiter.wait.call_args[1]
        assert waiter_call_args["WaiterConfig"]["Delay"] == 30
        assert waiter_call_args["WaiterConfig"]["MaxAttempts"] == 20


class TestRestoreInstanceToPublicSubnet:
    """Tests for _restore_instance_to_public_subnet function."""

    def test_restore_instance_success(self, capsys):
        """Test restoring instance successfully."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter

        _restore_instance_to_public_subnet(
            mock_rds, "test-snapshot", "test-instance", "test-subnet-group"
        )

        mock_rds.restore_db_instance_from_db_snapshot.assert_called_once_with(
            DBInstanceIdentifier="test-instance",
            DBSnapshotIdentifier="test-snapshot",
            DBInstanceClass="db.t4g.micro",
            DBSubnetGroupName="test-subnet-group",
            PubliclyAccessible=True,
            VpcSecurityGroupIds=["sg-265aa043"],
        )

        mock_waiter.wait.assert_called_once_with(
            DBInstanceIdentifier="test-instance", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
        )

        captured = capsys.readouterr()
        assert "Restoring to new instance in public subnets: test-instance" in captured.out
        assert "New instance restoration initiated!" in captured.out
        assert "Waiting for new instance to be available..." in captured.out
        assert "New instance is available in public subnets!" in captured.out
        assert "You can now connect to: test-instance" in captured.out
        assert "After confirming connectivity, you can delete the old instance" in captured.out

    def test_restore_instance_parameters(self):
        """Test that restore uses correct parameters."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter

        _restore_instance_to_public_subnet(mock_rds, "snap-1", "inst-1", "subnet-grp-1")

        call_args = mock_rds.restore_db_instance_from_db_snapshot.call_args[1]
        assert call_args["DBInstanceClass"] == "db.t4g.micro"
        assert call_args["PubliclyAccessible"] is True
        assert call_args["VpcSecurityGroupIds"] == ["sg-265aa043"]

    def test_restore_instance_waiter_called(self):
        """Test that waiter is called with correct parameters."""
        mock_rds = MagicMock()
        mock_waiter = MagicMock()
        mock_rds.get_waiter.return_value = mock_waiter

        _restore_instance_to_public_subnet(mock_rds, "snap", "inst", "subnet")

        mock_rds.get_waiter.assert_called_once_with("db_instance_available")


class TestFixDefaultSubnetGroup:
    """Tests for fix_default_subnet_group function."""

    def test_fix_subnet_group_success(self, capsys):
        """Test fixing subnet group successfully."""
        mod = "cost_toolkit.scripts.rds.fix_default_subnet_group"
        with (
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}.setup_aws_credentials") as mock_setup_creds,
            patch(f"{mod}.create_public_subnet_group") as mock_create_subnet_group,
            patch(f"{mod}._create_migration_snapshot") as mock_create_snapshot,
            patch(f"{mod}._restore_instance_to_public_subnet") as mock_restore,
        ):
            mock_rds = MagicMock()
            mock_boto_client.return_value = mock_rds

            fix_default_subnet_group()

            mock_setup_creds.assert_called_once()
            mock_boto_client.assert_called_once_with("rds", region_name="us-east-1")
            mock_create_subnet_group.assert_called_once_with(mock_rds, "public-rds-subnets")
            mock_create_snapshot.assert_called_once_with(
                mock_rds, "simba-db-public-migration-snapshot"
            )
            mock_restore.assert_called_once_with(
                mock_rds,
                "simba-db-public-migration-snapshot",
                "simba-db-public",
                "public-rds-subnets",
            )

            captured = capsys.readouterr()
            assert "Fixing default subnet group" in captured.out
            assert "Creating snapshot for subnet group migration..." in captured.out

    def test_fix_subnet_group_error_handling(self, capsys):
        """Test error handling in fix_default_subnet_group."""
        mod = "cost_toolkit.scripts.rds.fix_default_subnet_group"
        with (
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.create_public_subnet_group"),
            patch(f"{mod}._create_migration_snapshot") as mock_create_snapshot,
        ):
            mock_rds = MagicMock()
            mock_boto_client.return_value = mock_rds
            mock_create_snapshot.side_effect = ClientError(
                {"Error": {"Code": "ServiceError", "Message": "Service unavailable"}},
                "CreateDBSnapshot",
            )

            fix_default_subnet_group()

            captured = capsys.readouterr()
            assert "Error:" in captured.out

    @patch("cost_toolkit.scripts.rds.fix_default_subnet_group.boto3.client")
    @patch("cost_toolkit.scripts.rds.fix_default_subnet_group.setup_aws_credentials")
    @patch("cost_toolkit.scripts.rds.fix_default_subnet_group.create_public_subnet_group")
    def test_fix_subnet_group_subnet_creation_error(
        self, mock_create_subnet_group, _mock_setup_creds, mock_boto_client, capsys
    ):
        """Test handling subnet group creation error."""
        mock_rds = MagicMock()
        mock_boto_client.return_value = mock_rds
        mock_create_subnet_group.side_effect = ClientError(
            {"Error": {"Code": "InvalidSubnet", "Message": "Invalid subnet"}},
            "CreateDBSubnetGroup",
        )

        fix_default_subnet_group()

        captured = capsys.readouterr()
        assert "Error:" in captured.out


@patch("cost_toolkit.scripts.rds.fix_default_subnet_group.fix_default_subnet_group")
def test_main_calls_fix_default_subnet_group(mock_fix):
    """Test that main calls fix_default_subnet_group."""
    main()

    mock_fix.assert_called_once()
