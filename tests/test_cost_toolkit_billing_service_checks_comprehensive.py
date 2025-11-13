"""Comprehensive tests for cost_toolkit/scripts/billing/billing_report/service_checks.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks import (
    _check_cloudwatch_alarms_in_region,
    _check_cloudwatch_canaries_in_region,
    _check_lightsail_databases_in_region,
    _check_lightsail_instances_in_region,
    _format_cloudwatch_status,
    _format_lightsail_status,
    check_cloudwatch_status,
    check_global_accelerator_status,
    check_lightsail_status,
)


class TestGlobalAcceleratorStatus:
    def test_accelerator_status(self):
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


class TestLightsailInstancesRegion:
    def test_instance_states(self):
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


class TestLightsailDatabasesRegion:
    def test_database_states(self):
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
    def test_all_stopped(self):
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
        is_resolved, message = _format_lightsail_status(
            total_resources=10, stopped_resources=6, stopped_instances=4, stopped_databases=2
        )
        assert is_resolved is True
        assert "PARTIAL" in message
        assert "6/10" in message

    def test_all_active(self):
        is_resolved, message = _format_lightsail_status(
            total_resources=5, stopped_resources=0, stopped_instances=0, stopped_databases=0
        )
        assert is_resolved is False
        assert "ACTIVE" in message
        assert "5 Lightsail resources still running" in message

    def test_no_resources(self):
        is_resolved, message = _format_lightsail_status(
            total_resources=0, stopped_resources=0, stopped_instances=0, stopped_databases=0
        )
        assert is_resolved is True
        assert "No Lightsail resources found" in message


class TestCheckLightsailStatus:
    def test_lightsail_status(self):
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


class TestCloudWatchCanariesRegion:
    def test_canary_states(self):
        mock_client = MagicMock()
        mock_client.describe_canaries.return_value = {
            "Canaries": [
                {"Name": "canary1", "Status": {"State": "STOPPED"}},
                {"Name": "canary2", "Status": {"State": "STOPPED"}},
            ]
        }
        stopped, total = _check_cloudwatch_canaries_in_region(mock_client)
        assert stopped == 2
        assert total == 2
        mock_client.describe_canaries.return_value = {
            "Canaries": [
                {"Name": "canary1", "Status": {"State": "STOPPED"}},
                {"Name": "canary2", "Status": {"State": "RUNNING"}},
            ]
        }
        stopped, total = _check_cloudwatch_canaries_in_region(mock_client)
        assert stopped == 1
        assert total == 2
        error = botocore.exceptions.ClientError({"Error": {"Code": "Error"}}, "describe_canaries")
        mock_client.describe_canaries.side_effect = error
        stopped, total = _check_cloudwatch_canaries_in_region(mock_client)
        assert stopped == 0
        assert total == 0


class TestCloudWatchAlarmsRegion:
    def test_alarm_states(self):
        mock_client = MagicMock()
        mock_client.describe_alarms.return_value = {
            "MetricAlarms": [
                {"AlarmName": "alarm1", "ActionsEnabled": False},
                {"AlarmName": "alarm2", "ActionsEnabled": False},
            ]
        }
        disabled, total = _check_cloudwatch_alarms_in_region(mock_client)
        assert disabled == 2
        assert total == 2
        mock_client.describe_alarms.return_value = {
            "MetricAlarms": [
                {"AlarmName": "alarm1", "ActionsEnabled": False},
                {"AlarmName": "alarm2", "ActionsEnabled": True},
                {"AlarmName": "alarm3", "ActionsEnabled": False},
            ]
        }
        disabled, total = _check_cloudwatch_alarms_in_region(mock_client)
        assert disabled == 2
        assert total == 3
        error = botocore.exceptions.ClientError({"Error": {"Code": "Error"}}, "describe_alarms")
        mock_client.describe_alarms.side_effect = error
        disabled, total = _check_cloudwatch_alarms_in_region(mock_client)
        assert disabled == 0
        assert total == 0


class TestFormatCloudWatchStatus:
    def test_all_resolved(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=2,
            stopped_canaries=2,
            total_alarms=3,
            disabled_alarms=3,
        )
        assert is_resolved is True
        assert "RESOLVED" in message
        assert "2 canaries stopped" in message
        assert "3 alarms disabled" in message

    def test_only_canaries(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=2,
            stopped_canaries=2,
            total_alarms=0,
            disabled_alarms=0,
        )
        assert is_resolved is True
        assert "2 canaries stopped" in message

    def test_only_alarms(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=5,
            disabled_alarms=5,
        )
        assert is_resolved is True
        assert "5 alarms disabled" in message

    def test_no_resources(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=0,
            disabled_alarms=0,
        )
        assert is_resolved is True
        assert "no active resources" in message

    def test_canaries_active(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=3,
            stopped_canaries=1,
            total_alarms=0,
            disabled_alarms=0,
        )
        assert is_resolved is False
        assert "ACTIVE" in message
        assert "2 canaries running" in message

    def test_alarms_active(self):
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=4,
            disabled_alarms=2,
        )
        assert is_resolved is False
        assert "2 alarms enabled" in message


class TestCheckCloudWatchStatus:
    def test_cloudwatch_status(self):
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_synthetics = MagicMock()
            mock_synthetics.describe_canaries.return_value = {
                "Canaries": [
                    {"Name": "canary1", "Status": {"State": "STOPPED"}},
                ]
            }
            mock_cw.describe_alarms.return_value = {
                "MetricAlarms": [
                    {"AlarmName": "alarm1", "ActionsEnabled": False},
                ]
            }

            def client_side_effect(service, **kwargs):
                if service == "cloudwatch":
                    return mock_cw
                elif service == "synthetics":
                    return mock_synthetics
                return MagicMock()

            mock_client.side_effect = client_side_effect
            is_resolved, message = check_cloudwatch_status()
            assert is_resolved is True
            assert "RESOLVED" in message
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_synthetics = MagicMock()
            mock_synthetics.describe_canaries.return_value = {
                "Canaries": [
                    {"Name": "canary1", "Status": {"State": "RUNNING"}},
                ]
            }
            mock_cw.describe_alarms.return_value = {
                "MetricAlarms": [
                    {"AlarmName": "alarm1", "ActionsEnabled": True},
                ]
            }

            def client_side_effect(service, **kwargs):
                if service == "cloudwatch":
                    return mock_cw
                elif service == "synthetics":
                    return mock_synthetics
                return MagicMock()

            mock_client.side_effect = client_side_effect
            is_resolved, message = check_cloudwatch_status()
            assert is_resolved is False
            assert "ACTIVE" in message

    def test_cloudwatch_error_handling(self):
        with patch("boto3.client") as mock_client:
            error = botocore.exceptions.ClientError({"Error": {"Code": "Error"}}, "client")
            mock_client.side_effect = error
            is_resolved, message = check_cloudwatch_status()
            assert is_resolved is not None
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceError"}}, "client")
            mock_client.side_effect = error
            result = check_cloudwatch_status()
            assert result is not None
            assert len(result) == 2
