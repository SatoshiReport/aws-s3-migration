"""Comprehensive tests for aws_cleanup_script.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_cleanup_script import (
    _process_region,
    _stop_database,
    main,
    stop_lightsail_instances,
)


class TestStopDatabase:
    """Tests for _stop_database function."""

    def test_stop_database_success(self, capsys):
        """Test successful database stop."""
        mock_client = MagicMock()
        database = {
            "name": "test-db",
            "state": "available",
            "relationalDatabaseBundleId": "micro_1_0",
        }
        stopped, cost = _stop_database(mock_client, database)
        assert stopped == 1
        assert cost == 15.0
        mock_client.stop_relational_database.assert_called_once_with(
            relationalDatabaseName="test-db"
        )
        captured = capsys.readouterr()
        assert "Stopped database" in captured.out

    def test_stop_database_already_stopped(self, capsys):
        """Test database already stopped."""
        mock_client = MagicMock()
        database = {
            "name": "test-db",
            "state": "stopped",
            "relationalDatabaseBundleId": "micro_1_0",
        }
        stopped, cost = _stop_database(mock_client, database)
        assert stopped == 0
        assert cost == 0.0
        mock_client.stop_relational_database.assert_not_called()
        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    def test_stop_database_error(self, capsys):
        """Test error stopping database."""
        mock_client = MagicMock()
        mock_client.stop_relational_database.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "stop_relational_database"
        )
        database = {
            "name": "test-db",
            "state": "available",
            "relationalDatabaseBundleId": "micro_1_0",
        }
        stopped, cost = _stop_database(mock_client, database)
        assert stopped == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Error stopping database" in captured.out

    def test_stop_database_no_bundle_id(self):
        """Test stopping database without bundle ID."""
        mock_client = MagicMock()
        database = {"name": "test-db", "state": "available"}
        stopped, cost = _stop_database(mock_client, database)
        assert stopped == 1
        assert cost == 0.0

    def test_stop_database_other_state(self, capsys):
        """Test database in other states."""
        mock_client = MagicMock()
        database = {
            "name": "test-db",
            "state": "backing-up",
            "relationalDatabaseBundleId": "micro_1_0",
        }
        stopped, cost = _stop_database(mock_client, database)
        assert stopped == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "already" in captured.out


class TestProcessRegionSuccess:
    """Tests for _process_region function - successful cases."""

    def test_process_region_with_instances_and_databases(self, capsys):
        """Test processing region with both instances and databases."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.return_value = {
                "instances": [
                    {"name": "inst1", "state": {"name": "running"}, "bundleId": "nano_2_0"}
                ]
            }
            mock_ls.get_relational_databases.return_value = {
                "relationalDatabases": [
                    {"name": "db1", "state": "available", "relationalDatabaseBundleId": "micro_1_0"}
                ]
            }
            mock_client.return_value = mock_ls
            instances, databases, savings = _process_region("us-east-1")
        assert instances == 1
        assert databases == 1
        assert savings == 18.5  # 3.5 + 15.0
        captured = capsys.readouterr()
        assert "Checking region: us-east-1" in captured.out

    def test_process_region_no_resources(self, capsys):
        """Test processing region with no resources."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.return_value = {"instances": []}
            mock_ls.get_relational_databases.return_value = {"relationalDatabases": []}
            mock_client.return_value = mock_ls
            instances, databases, savings = _process_region("us-east-1")
        assert instances == 0
        assert databases == 0
        assert savings == 0.0
        captured = capsys.readouterr()
        assert "No Lightsail resources found" in captured.out

    def test_process_region_only_instances(self):
        """Test processing region with only instances."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.return_value = {
                "instances": [
                    {"name": "inst1", "state": {"name": "running"}, "bundleId": "small_2_0"},
                    {"name": "inst2", "state": {"name": "running"}, "bundleId": "micro_2_0"},
                ]
            }
            mock_ls.get_relational_databases.return_value = {"relationalDatabases": []}
            mock_client.return_value = mock_ls
            instances, databases, savings = _process_region("us-west-2")
        assert instances == 2
        assert databases == 0
        assert savings == 15.0  # 10.0 + 5.0


class TestProcessRegionEdgeCases:
    """Tests for _process_region function - edge cases."""

    def test_process_region_only_databases(self):
        """Test processing region with only databases."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.return_value = {"instances": []}
            mock_ls.get_relational_databases.return_value = {
                "relationalDatabases": [
                    {
                        "name": "db1",
                        "state": "available",
                        "relationalDatabaseBundleId": "small_1_0",
                    },
                ]
            }
            mock_client.return_value = mock_ls
            instances, databases, savings = _process_region("eu-central-1")
        assert instances == 0
        assert databases == 1
        assert savings == 30.0

    def test_process_region_mixed_states(self):
        """Test processing region with mixed instance/database states."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.return_value = {
                "instances": [
                    {"name": "inst1", "state": {"name": "running"}, "bundleId": "nano_2_0"},
                    {"name": "inst2", "state": {"name": "stopped"}, "bundleId": "nano_2_0"},
                ]
            }
            mock_ls.get_relational_databases.return_value = {
                "relationalDatabases": [
                    {
                        "name": "db1",
                        "state": "available",
                        "relationalDatabaseBundleId": "micro_1_0",
                    },
                    {"name": "db2", "state": "stopped", "relationalDatabaseBundleId": "micro_1_0"},
                ]
            }
            mock_client.return_value = mock_ls
            instances, databases, savings = _process_region("us-east-1")
        assert instances == 1  # Only running instance
        assert databases == 1  # Only available database
        assert savings == 18.5


class TestStopLightsailInstances:
    """Tests for stop_lightsail_instances function."""

    def test_stop_lightsail_instances_success(self, capsys):
        """Test successful Lightsail instance stop."""
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials"
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cleanup_script._process_region",
                return_value=(2, 1, 25.0),
            ):
                instances, databases, savings = stop_lightsail_instances()
        # 4 regions checked, each returns (2, 1, 25.0)
        assert instances == 8  # 2 * 4
        assert databases == 4  # 1 * 4
        assert savings == 100.0  # 25.0 * 4
        captured = capsys.readouterr()
        assert "Checking Lightsail instances" in captured.out

    def test_stop_lightsail_instances_region_not_available(self, capsys):
        """Test when Lightsail not available in region."""
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials"
        ):
            with patch("boto3.client") as mock_client:
                mock_ls = MagicMock()
                mock_ls.get_instances.side_effect = ClientError(
                    {"Error": {"Code": "InvalidAction", "Message": "not available"}},
                    "get_instances",
                )
                mock_client.return_value = mock_ls
                instances, databases, savings = stop_lightsail_instances()
        assert instances == 0
        assert databases == 0
        assert savings == 0.0
        captured = capsys.readouterr()
        assert "Lightsail not available" in captured.out

    def test_stop_lightsail_instances_other_error(self, capsys):
        """Test with other client errors."""
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials"
        ):
            with patch("boto3.client") as mock_client:
                mock_ls = MagicMock()
                mock_ls.get_instances.side_effect = ClientError(
                    {"Error": {"Code": "UnauthorizedOperation"}}, "get_instances"
                )
                mock_client.return_value = mock_ls
                instances, databases, savings = stop_lightsail_instances()
        assert instances == 0
        assert databases == 0
        assert savings == 0.0
        captured = capsys.readouterr()
        assert "Error accessing Lightsail" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success(self, capsys):
        """Test main function with successful execution."""
        with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.disable_global_accelerators"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cleanup_script.stop_lightsail_instances",
                return_value=(5, 3, 125.50),
            ):
                main()
        captured = capsys.readouterr()
        assert "AWS Cost Optimization Cleanup" in captured.out
        assert "Cleanup completed" in captured.out
        assert "Lightsail instances stopped: 5" in captured.out
        assert "Lightsail databases stopped: 3" in captured.out
        assert "$125.50" in captured.out

    def test_main_no_resources(self, capsys):
        """Test main when no resources found."""
        with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.disable_global_accelerators"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cleanup_script.stop_lightsail_instances",
                return_value=(0, 0, 0.0),
            ):
                main()
        captured = capsys.readouterr()
        assert "Cleanup completed" in captured.out
        assert "Lightsail instances stopped: 0" in captured.out

    def test_main_output_format(self, capsys):
        """Test main output formatting."""
        with patch("cost_toolkit.scripts.cleanup.aws_cleanup_script.disable_global_accelerators"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cleanup_script.stop_lightsail_instances",
                return_value=(10, 5, 250.0),
            ):
                main()
        captured = capsys.readouterr()
        assert "This script will:" in captured.out
        assert "Disable Global Accelerators" in captured.out
        assert "Stop Lightsail instances and databases" in captured.out
        assert "Changes may take a few minutes" in captured.out
