"""Tests for Global Accelerator and Lightsail service checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks import (
    _check_lightsail_databases_in_region,
    _check_lightsail_instances_in_region,
    _format_lightsail_status,
    check_global_accelerator_status,
    check_lightsail_status,
)


class TestGlobalAcceleratorStatus:
    """Test global accelerator status checking."""

    def test_accelerator_status(self):
        """Test checking status of global accelerators."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {
                "Accelerators": [
                    {"Name": "acc1", "Enabled": False},
                    {"Name": "acc2", "Enabled": False},
                ]
            }
            mock_client.return_value = mock_ga
            is_resolved, message = check_global_accelerator_status()
            assert is_resolved is True
            assert "All 2 accelerators disabled" in message
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {
                "Accelerators": [
                    {"Name": "acc1", "Enabled": False},
                    {"Name": "acc2", "Enabled": True},
                    {"Name": "acc3", "Enabled": False},
                ]
            }
            mock_client.return_value = mock_ga
            is_resolved, message = check_global_accelerator_status()
            assert is_resolved is True
            assert "PARTIAL" in message
            assert "2/3" in message
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            mock_ga.list_accelerators.return_value = {
                "Accelerators": [
                    {"Name": "acc1", "Enabled": True},
                    {"Name": "acc2", "Enabled": True},
                ]
            }
            mock_client.return_value = mock_ga
            is_resolved, message = check_global_accelerator_status()
            assert is_resolved is False
            assert "ACTIVE" in message

    def test_accelerator_errors(self):
        """Test handling of errors when checking accelerators."""
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            error = ClientError({"Error": {"Code": "AccessDenied"}}, "list_accelerators")
            mock_ga.list_accelerators.side_effect = error
            mock_client.return_value = mock_ga
            is_resolved, message = check_global_accelerator_status()
            assert is_resolved is None
            assert "No permission" in message
        with patch("boto3.client") as mock_client:
            mock_ga = MagicMock()
            error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "list_accelerators")
            mock_ga.list_accelerators.side_effect = error
            mock_client.return_value = mock_ga
            is_resolved, message = check_global_accelerator_status()
            assert is_resolved is None
            assert "ERROR" in message


def test_lightsail_instances_region_instance_states():
    """Test checking Lightsail instance states."""
    mock_client = MagicMock()
    mock_client.get_instances.return_value = {
        "instances": [
            {"name": "inst1", "state": {"name": "stopped"}},
            {"name": "inst2", "state": {"name": "stopped"}},
        ]
    }
    stopped, total = _check_lightsail_instances_in_region(mock_client)
    assert stopped == 2
    assert total == 2
    mock_client.get_instances.return_value = {
        "instances": [
            {"name": "inst1", "state": {"name": "stopped"}},
            {"name": "inst2", "state": {"name": "running"}},
            {"name": "inst3", "state": {"name": "stopped"}},
        ]
    }
    stopped, total = _check_lightsail_instances_in_region(mock_client)
    assert stopped == 2
    assert total == 3
    mock_client.get_instances.return_value = {"instances": []}
    stopped, total = _check_lightsail_instances_in_region(mock_client)
    assert stopped == 0
    assert total == 0


def test_lightsail_databases_region_database_states():
    """Test checking Lightsail database states."""
    mock_client = MagicMock()
    mock_client.get_relational_databases.return_value = {
        "relationalDatabases": [
            {
                "relationalDatabaseBlueprintId": "mysql",
                "masterDatabaseName": "db1",
                "state": "stopped",
            },
            {
                "relationalDatabaseBlueprintId": "postgres",
                "masterDatabaseName": "db2",
                "state": "STOPPED",
            },
        ]
    }
    stopped, total = _check_lightsail_databases_in_region(mock_client)
    assert stopped == 2
    assert total == 2
    mock_client.get_relational_databases.return_value = {
        "relationalDatabases": [
            {
                "relationalDatabaseBlueprintId": "mysql",
                "masterDatabaseName": "db1",
                "state": "stopped",
            },
            {
                "relationalDatabaseBlueprintId": "postgres",
                "masterDatabaseName": "db2",
                "state": "available",
            },
        ]
    }
    stopped, total = _check_lightsail_databases_in_region(mock_client)
    assert stopped == 1
    assert total == 2
    mock_client.get_relational_databases.return_value = {"relationalDatabases": []}
    stopped, total = _check_lightsail_databases_in_region(mock_client)
    assert stopped == 0
    assert total == 0


class TestFormatLightsailStatus:
    """Test Lightsail status formatting."""

    def test_all_stopped(self):
        """Test formatting when all resources stopped."""
        is_resolved, message = _format_lightsail_status(
            total_resources=5,
            stopped_resources=5,
            stopped_instances=3,
            stopped_databases=2,
        )
        assert is_resolved is True
        assert "All Lightsail resources stopped" in message
        assert "3 instances" in message
        assert "2 databases" in message

    def test_partial_stopped(self):
        """Test formatting when some resources stopped."""
        is_resolved, message = _format_lightsail_status(
            total_resources=10, stopped_resources=6, stopped_instances=4, stopped_databases=2
        )
        assert is_resolved is True
        assert "PARTIAL" in message
        assert "6/10" in message

    def test_all_active(self):
        """Test formatting when all resources active."""
        is_resolved, message = _format_lightsail_status(
            total_resources=5, stopped_resources=0, stopped_instances=0, stopped_databases=0
        )
        assert is_resolved is False
        assert "ACTIVE" in message
        assert "5 Lightsail resources still running" in message

    def test_no_resources(self):
        """Test formatting when no resources exist."""
        is_resolved, message = _format_lightsail_status(
            total_resources=0, stopped_resources=0, stopped_instances=0, stopped_databases=0
        )
        assert is_resolved is True
        assert "No Lightsail resources found" in message


def test_check_lightsail_status_lightsail_status():
    """Test checking Lightsail status across regions."""
    with patch("boto3.client") as mock_client:
        mock_ls = MagicMock()
        mock_ls.get_instances.return_value = {
            "instances": [{"name": "inst1", "state": {"name": "stopped"}}]
        }
        mock_ls.get_relational_databases.return_value = {
            "relationalDatabases": [
                {
                    "relationalDatabaseBlueprintId": "mysql",
                    "masterDatabaseName": "db1",
                    "state": "stopped",
                }
            ]
        }
        mock_client.return_value = mock_ls
        is_resolved, message = check_lightsail_status()
        assert is_resolved is True
        assert "All Lightsail resources stopped" in message
    with patch("boto3.client") as mock_client:
        mock_ls = MagicMock()
        mock_ls.get_instances.return_value = {"instances": []}
        mock_ls.get_relational_databases.return_value = {"relationalDatabases": []}
        mock_client.return_value = mock_ls
        is_resolved, message = check_lightsail_status()
        assert is_resolved is True
        assert "No Lightsail resources found" in message
    with patch("boto3.client") as mock_client:
        error = ClientError({"Error": {"Code": "ServiceError"}}, "client")
        mock_client.side_effect = error
        result = check_lightsail_status()
        assert result is not None
        assert len(result) == 2
