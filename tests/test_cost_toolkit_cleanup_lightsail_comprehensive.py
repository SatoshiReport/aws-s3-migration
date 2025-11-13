"""Comprehensive tests for aws_lightsail_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_lightsail_cleanup import (
    _delete_database,
    _delete_instance,
    _print_summary,
    _process_region,
    delete_lightsail_instances,
)


class TestDeleteInstance:
    """Tests for _delete_instance function."""

    def test_delete_instance_success(self, capsys):
        """Test successful instance deletion."""
        mock_client = MagicMock()
        instance = {
            "name": "test-instance",
            "state": {"name": "running"},
            "bundleId": "nano_2_0",
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.estimate_instance_cost",
            return_value=5.0,
        ):
            deleted, cost = _delete_instance(mock_client, instance)

        assert deleted == 1
        assert cost == 5.0
        mock_client.delete_instance.assert_called_once_with(
            instanceName="test-instance", forceDeleteAddOns=True
        )

    def test_delete_instance_error(self, capsys):
        """Test instance deletion with error."""
        mock_client = MagicMock()
        mock_client.delete_instance.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_instance"
        )
        instance = {
            "name": "test-instance",
            "state": {"name": "running"},
            "bundleId": "nano_2_0",
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.estimate_instance_cost",
            return_value=5.0,
        ):
            deleted, cost = _delete_instance(mock_client, instance)

        assert deleted == 0
        assert cost == 0.0

    def test_delete_instance_no_bundle(self, capsys):
        """Test instance deletion when bundle ID is missing."""
        mock_client = MagicMock()
        instance = {
            "name": "test-instance",
            "state": {"name": "stopped"},
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.estimate_instance_cost",
            return_value=0.0,
        ):
            deleted, cost = _delete_instance(mock_client, instance)

        assert deleted == 1


class TestDeleteDatabase:
    """Tests for _delete_database function."""

    def test_delete_database_success(self, capsys):
        """Test successful database deletion."""
        mock_client = MagicMock()
        database = {
            "name": "test-db",
            "state": "available",
            "relationalDatabaseBundleId": "micro_1_0",
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.estimate_database_cost",
            return_value=15.0,
        ):
            deleted, cost = _delete_database(mock_client, database)

        assert deleted == 1
        assert cost == 15.0
        mock_client.delete_relational_database.assert_called_once_with(
            relationalDatabaseName="test-db", skipFinalSnapshot=True
        )

    def test_delete_database_error(self, capsys):
        """Test database deletion with error."""
        mock_client = MagicMock()
        mock_client.delete_relational_database.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_relational_database"
        )
        database = {
            "name": "test-db",
            "state": "available",
            "relationalDatabaseBundleId": "micro_1_0",
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.estimate_database_cost",
            return_value=15.0,
        ):
            deleted, cost = _delete_database(mock_client, database)

        assert deleted == 0
        assert cost == 0.0


class TestProcessRegion:
    """Tests for _process_region function."""

    def test_process_region_with_resources(self, capsys):
        """Test processing region with instances and databases."""
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

            with patch(
                "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup._delete_instance",
                return_value=(1, 5.0),
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup._delete_database",
                    return_value=(1, 15.0),
                ):
                    instances, databases, savings = _process_region("us-east-1")

        assert instances == 1
        assert databases == 1
        assert savings == 20.0

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

    def test_process_region_not_available(self, capsys):
        """Test processing region where Lightsail is not available."""
        with patch("boto3.client") as mock_client:
            mock_ls = MagicMock()
            mock_ls.get_instances.side_effect = ClientError(
                {"Error": {"Code": "InvalidAction"}}, "get_instances"
            )
            mock_client.return_value = mock_ls

            instances, databases, savings = _process_region("us-east-1")

        assert instances == 0
        assert databases == 0
        assert savings == 0.0


class TestPrintSummary:
    """Tests for _print_summary function."""

    def test_print_summary_with_deletions(self, capsys):
        """Test summary printing with deletions."""
        _print_summary(5, 3, 100.50)

        captured = capsys.readouterr()
        assert "LIGHTSAIL CLEANUP COMPLETED" in captured.out
        assert "Instances deleted: 5" in captured.out
        assert "Databases deleted: 3" in captured.out
        assert "$100.50" in captured.out
        assert "IMPORTANT NOTES" in captured.out

    def test_print_summary_no_deletions(self, capsys):
        """Test summary printing with no deletions."""
        _print_summary(0, 0, 0.0)

        captured = capsys.readouterr()
        assert "LIGHTSAIL CLEANUP COMPLETED" in captured.out
        assert "Instances deleted: 0" in captured.out
        assert "IMPORTANT NOTES" not in captured.out


class TestDeleteLightsailInstances:
    """Tests for delete_lightsail_instances function."""

    def test_delete_lightsail_instances_success(self, capsys):
        """Test full Lightsail deletion workflow."""
        with patch("cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.get_default_regions",
                return_value=["us-east-1"],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup._process_region",
                    return_value=(2, 1, 30.0),
                ):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_lightsail_cleanup.record_cleanup_action"
                    ):
                        delete_lightsail_instances()

        captured = capsys.readouterr()
        assert "LIGHTSAIL INSTANCE CLEANUP" in captured.out
        assert "WARNING" in captured.out
