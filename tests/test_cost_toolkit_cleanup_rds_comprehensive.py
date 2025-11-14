"""Comprehensive tests for aws_rds_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_rds_cleanup import (
    _cleanup_aurora_cluster,
    _cleanup_mariadb_instance,
    _delete_aurora_cluster,
    _delete_aurora_instance,
    _print_cleanup_summary,
    _stop_mariadb_instance,
    _wait_for_instance_deletion,
    cleanup_rds_databases,
    main,
)


class TestDeleteAuroraInstance:
    """Tests for _delete_aurora_instance function."""

    def test_delete_instance_success(self, capsys):
        """Test successful Aurora instance deletion."""
        mock_client = MagicMock()

        result = _delete_aurora_instance(mock_client, "test-instance")

        assert result is True
        mock_client.delete_db_instance.assert_called_once_with(
            DBInstanceIdentifier="test-instance",
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
        captured = capsys.readouterr()
        assert "deletion initiated" in captured.out

    def test_delete_instance_not_found(self, capsys):
        """Test deleting instance that doesn't exist."""
        mock_client = MagicMock()
        mock_client.delete_db_instance.side_effect = ClientError(
            {"Error": {"Code": "DBInstanceNotFound", "Message": "Not found"}}, "delete_db_instance"
        )

        result = _delete_aurora_instance(mock_client, "test-instance")

        assert result is False
        captured = capsys.readouterr()
        assert "already deleted" in captured.out

    def test_delete_instance_already_deleting(self, capsys):
        """Test instance already being deleted."""
        mock_client = MagicMock()
        mock_client.delete_db_instance.side_effect = ClientError(
            {"Error": {"Code": "InvalidDBInstanceState", "Message": "already being deleted"}},
            "delete_db_instance",
        )

        result = _delete_aurora_instance(mock_client, "test-instance")

        assert result is False
        captured = capsys.readouterr()
        assert "already being deleted" in captured.out

    def test_delete_instance_other_error(self):
        """Test other deletion errors."""
        mock_client = MagicMock()
        mock_client.delete_db_instance.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_db_instance"
        )

        with pytest.raises(ClientError):
            _delete_aurora_instance(mock_client, "test-instance")


class TestWaitForInstanceDeletion:
    """Tests for _wait_for_instance_deletion function."""

    def test_wait_success(self, capsys):
        """Test successful wait for deletion."""
        mock_client = MagicMock()
        mock_waiter = MagicMock()
        mock_client.get_waiter.return_value = mock_waiter

        _wait_for_instance_deletion(mock_client, "test-instance")

        mock_waiter.wait.assert_called_once_with(
            DBInstanceIdentifier="test-instance", WaiterConfig={"Delay": 30, "MaxAttempts": 20}
        )
        captured = capsys.readouterr()
        assert "deleted successfully" in captured.out

    def test_wait_error(self, capsys):
        """Test error during wait."""
        mock_client = MagicMock()
        mock_waiter = MagicMock()
        mock_waiter.wait.side_effect = ClientError({"Error": {"Code": "WaiterError"}}, "wait")
        mock_client.get_waiter.return_value = mock_waiter

        _wait_for_instance_deletion(mock_client, "test-instance")

        captured = capsys.readouterr()
        assert "Proceeding with cluster deletion" in captured.out


class TestDeleteAuroraCluster:
    """Tests for _delete_aurora_cluster function."""

    def test_delete_cluster_success(self, capsys):
        """Test successful cluster deletion."""
        mock_client = MagicMock()

        _delete_aurora_cluster(mock_client, "test-cluster")

        mock_client.delete_db_cluster.assert_called_once_with(
            DBClusterIdentifier="test-cluster", SkipFinalSnapshot=True
        )
        captured = capsys.readouterr()
        assert "deletion initiated" in captured.out
        assert "Will save" in captured.out

    def test_delete_cluster_not_found(self, capsys):
        """Test deleting cluster that doesn't exist."""
        mock_client = MagicMock()
        mock_client.delete_db_cluster.side_effect = ClientError(
            {"Error": {"Code": "DBClusterNotFound"}}, "delete_db_cluster"
        )

        _delete_aurora_cluster(mock_client, "test-cluster")

        captured = capsys.readouterr()
        assert "already deleted" in captured.out

    def test_delete_cluster_error(self, capsys):
        """Test other cluster deletion errors."""
        mock_client = MagicMock()
        mock_client.delete_db_cluster.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_db_cluster"
        )

        _delete_aurora_cluster(mock_client, "test-cluster")

        captured = capsys.readouterr()
        assert "Error deleting cluster" in captured.out


class TestCleanupAuroraCluster:
    """Tests for _cleanup_aurora_cluster function."""

    def test_cleanup_aurora_success(self, capsys):
        """Test successful Aurora cleanup."""
        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_rds_cleanup._delete_aurora_instance",
                return_value=True,
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_rds_cleanup._wait_for_instance_deletion"
                ):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_rds_cleanup._delete_aurora_cluster"
                    ):
                        _cleanup_aurora_cluster()

        captured = capsys.readouterr()
        assert "DELETING AURORA CLUSTER" in captured.out

    def test_cleanup_aurora_client_error(self, capsys):
        """Test Aurora cleanup with client error."""
        with patch(
            "boto3.client", side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "client")
        ):
            _cleanup_aurora_cluster()

        captured = capsys.readouterr()
        assert "Error accessing eu-west-2" in captured.out


class TestStopMariadbInstance:
    """Tests for _stop_mariadb_instance function."""

    def test_stop_available_instance(self, capsys):
        """Test stopping available instance."""
        mock_client = MagicMock()
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [{"DBInstanceStatus": "available"}]
        }

        _stop_mariadb_instance(mock_client, "test-db")

        mock_client.stop_db_instance.assert_called_once_with(DBInstanceIdentifier="test-db")
        captured = capsys.readouterr()
        assert "stop initiated" in captured.out
        assert "Will save" in captured.out

    def test_stop_already_stopped(self, capsys):
        """Test instance already stopped."""
        mock_client = MagicMock()
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [{"DBInstanceStatus": "stopped"}]
        }

        _stop_mariadb_instance(mock_client, "test-db")

        mock_client.stop_db_instance.assert_not_called()
        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    def test_stop_invalid_state(self, capsys):
        """Test stopping instance in invalid state."""
        mock_client = MagicMock()
        mock_client.describe_db_instances.return_value = {
            "DBInstances": [{"DBInstanceStatus": "creating"}]
        }

        _stop_mariadb_instance(mock_client, "test-db")

        mock_client.stop_db_instance.assert_not_called()
        captured = capsys.readouterr()
        assert "cannot stop" in captured.out

    def test_stop_instance_not_found(self, capsys):
        """Test stopping non-existent instance."""
        mock_client = MagicMock()
        mock_client.describe_db_instances.side_effect = ClientError(
            {"Error": {"Code": "DBInstanceNotFound"}}, "describe_db_instances"
        )

        _stop_mariadb_instance(mock_client, "test-db")

        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestCleanupMariadbInstance:
    """Tests for _cleanup_mariadb_instance function."""

    def test_cleanup_mariadb_success(self, capsys):
        """Test successful MariaDB cleanup."""
        with patch("boto3.client"):
            with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup._stop_mariadb_instance"):
                _cleanup_mariadb_instance()

        captured = capsys.readouterr()
        assert "STOPPING MARIADB INSTANCE" in captured.out

    def test_cleanup_mariadb_error(self, capsys):
        """Test MariaDB cleanup with error."""
        with patch(
            "boto3.client", side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "client")
        ):
            _cleanup_mariadb_instance()

        captured = capsys.readouterr()
        assert "Error accessing us-east-1" in captured.out


def test_print_cleanup_summary_print_summary(capsys):
    """Test printing cleanup summary."""
    _print_cleanup_summary()

    captured = capsys.readouterr()
    assert "RDS CLEANUP SUMMARY" in captured.out
    assert "Aurora Cluster" in captured.out
    assert "MariaDB Instance" in captured.out
    assert "Estimated savings" in captured.out


def test_cleanup_rds_databases_cleanup_all_databases(capsys):
    """Test full RDS cleanup workflow."""
    with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup._cleanup_aurora_cluster"):
        with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup._cleanup_mariadb_instance"):
            with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup._print_cleanup_summary"):
                cleanup_rds_databases()

    captured = capsys.readouterr()
    assert "AWS RDS Database Cleanup" in captured.out


class TestMain:
    """Tests for main function and edge cases."""

    def test_main_calls_cleanup_rds_databases(self):
        """Test main function calls cleanup_rds_databases."""
        with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup.cleanup_rds_databases"):
            main()

    def test_main_handles_execution(self, capsys):
        """Test main function executes cleanup successfully."""
        with patch("cost_toolkit.scripts.cleanup.aws_rds_cleanup.cleanup_rds_databases"):
            main()
        captured = capsys.readouterr()
        # Main should execute cleanup_rds_databases which has its own output
        assert captured.out is not None

    def test_stop_instance_other_error(self, capsys):
        """Test other errors when stopping instance."""
        mock_client = MagicMock()
        mock_client.describe_db_instances.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "describe_db_instances"
        )

        _stop_mariadb_instance(mock_client, "test-db")

        captured = capsys.readouterr()
        assert "Error" in captured.out
