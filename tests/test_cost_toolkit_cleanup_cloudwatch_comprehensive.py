"""Comprehensive tests for aws_cloudwatch_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup import (
    _collect_alarm_names_to_disable,
    _delete_single_canary,
    _disable_alarms_in_region,
    _process_canaries_in_region,
    _reduce_retention_in_region,
    _stop_canary_if_running,
    _update_log_group_retention,
    delete_cloudwatch_canaries,
    delete_custom_metrics,
    disable_cloudwatch_alarms,
    reduce_log_retention,
    setup_aws_credentials,
)


class TestSetupAwsCredentials:
    """Tests for setup_aws_credentials function."""

    def test_calls_shared_setup(self):
        """Test that setup calls the shared utility."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup.aws_utils.setup_aws_credentials"
        ) as mock_setup:
            setup_aws_credentials()
            mock_setup.assert_called_once()


class TestStopCanaryIfRunning:
    """Tests for _stop_canary_if_running function."""

    def test_stop_running_canary(self, capsys):
        """Test stopping a running canary."""
        mock_client = MagicMock()
        _stop_canary_if_running(mock_client, "test-canary", "RUNNING")
        mock_client.stop_canary.assert_called_once_with(Name="test-canary")
        captured = capsys.readouterr()
        assert "Stopping canary" in captured.out
        assert "Successfully stopped" in captured.out

    def test_skip_non_running_canary(self):
        """Test skipping non-running canary."""
        mock_client = MagicMock()
        _stop_canary_if_running(mock_client, "test-canary", "STOPPED")
        mock_client.stop_canary.assert_not_called()

    def test_stop_canary_error(self, capsys):
        """Test error when stopping canary."""
        mock_client = MagicMock()
        mock_client.stop_canary.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "stop_canary"
        )
        _stop_canary_if_running(mock_client, "test-canary", "RUNNING")
        captured = capsys.readouterr()
        assert "Error stopping canary" in captured.out


class TestDeleteSingleCanary:
    """Tests for _delete_single_canary function."""

    def test_delete_running_canary(self, capsys):
        """Test deleting a running canary."""
        mock_client = MagicMock()
        canary = {"Name": "test-canary", "Status": {"State": "RUNNING"}}
        with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._stop_canary_if_running"):
            _delete_single_canary(mock_client, canary)
        mock_client.delete_canary.assert_called_once_with(Name="test-canary", DeleteLambda=True)
        captured = capsys.readouterr()
        assert "Successfully deleted canary" in captured.out

    def test_delete_stopped_canary(self, capsys):
        """Test deleting a stopped canary."""
        mock_client = MagicMock()
        canary = {"Name": "test-canary", "Status": {"State": "STOPPED"}}
        _delete_single_canary(mock_client, canary)
        mock_client.delete_canary.assert_called_once()

    def test_delete_canary_error(self, capsys):
        """Test error when deleting canary."""
        mock_client = MagicMock()
        mock_client.delete_canary.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_canary"
        )
        canary = {"Name": "test-canary", "Status": {"State": "STOPPED"}}
        _delete_single_canary(mock_client, canary)
        captured = capsys.readouterr()
        assert "Error deleting canary" in captured.out


class TestProcessCanariesInRegion:
    """Tests for _process_canaries_in_region function."""

    def test_process_region_with_canaries(self, capsys):
        """Test processing region with canaries."""
        with patch("boto3.client") as mock_client:
            mock_synthetics = MagicMock()
            mock_synthetics.describe_canaries.return_value = {
                "Canaries": [
                    {"Name": "canary-1", "Status": {"State": "RUNNING"}},
                    {"Name": "canary-2", "Status": {"State": "STOPPED"}},
                ]
            }
            mock_client.return_value = mock_synthetics
            with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._delete_single_canary"):
                _process_canaries_in_region("us-east-1")
        captured = capsys.readouterr()
        assert "Checking region: us-east-1" in captured.out

    def test_process_region_no_canaries(self, capsys):
        """Test processing region with no canaries."""
        with patch("boto3.client") as mock_client:
            mock_synthetics = MagicMock()
            mock_synthetics.describe_canaries.return_value = {"Canaries": []}
            mock_client.return_value = mock_synthetics
            _process_canaries_in_region("us-east-1")
        captured = capsys.readouterr()
        assert "No canaries found" in captured.out


class TestDeleteCloudwatchCanaries:
    """Tests for delete_cloudwatch_canaries function."""

    def test_delete_canaries_multiple_regions(self, capsys):
        """Test deleting canaries across regions."""
        with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._process_canaries_in_region"
            ):
                delete_cloudwatch_canaries()
        captured = capsys.readouterr()
        assert "Checking CloudWatch Synthetics canaries" in captured.out

    def test_delete_canaries_service_not_available(self, capsys):
        """Test when Synthetics not available in region."""
        with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._process_canaries_in_region"
            ) as mock_process:
                mock_process.side_effect = ClientError(
                    {"Error": {"Code": "InvalidAction", "Message": "not available"}},
                    "describe_canaries",
                )
                delete_cloudwatch_canaries()
        captured = capsys.readouterr()
        assert "not available" in captured.out


class TestCollectAlarmNamesToDisable:
    """Tests for _collect_alarm_names_to_disable function."""

    def test_collect_enabled_alarms(self, capsys):
        """Test collecting enabled alarms."""
        alarms = [
            {
                "AlarmName": "alarm-1",
                "StateValue": "OK",
                "ActionsEnabled": True,
            },
            {
                "AlarmName": "alarm-2",
                "StateValue": "ALARM",
                "ActionsEnabled": True,
            },
        ]
        alarm_names = _collect_alarm_names_to_disable(alarms)
        assert len(alarm_names) == 2
        assert "alarm-1" in alarm_names
        assert "alarm-2" in alarm_names

    def test_collect_skip_disabled_alarms(self, capsys):
        """Test skipping already disabled alarms."""
        alarms = [
            {
                "AlarmName": "alarm-1",
                "StateValue": "OK",
                "ActionsEnabled": True,
            },
            {
                "AlarmName": "alarm-2",
                "StateValue": "ALARM",
                "ActionsEnabled": False,
            },
        ]
        alarm_names = _collect_alarm_names_to_disable(alarms)
        assert len(alarm_names) == 1
        assert "alarm-1" in alarm_names
        captured = capsys.readouterr()
        assert "Actions already disabled" in captured.out


class TestDisableAlarmsInRegion:
    """Tests for _disable_alarms_in_region function."""

    def test_disable_alarms_success(self, capsys):
        """Test successful alarm disabling."""
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = {
                "MetricAlarms": [
                    {
                        "AlarmName": "alarm-1",
                        "StateValue": "OK",
                        "ActionsEnabled": True,
                    }
                ]
            }
            mock_client.return_value = mock_cw
            _disable_alarms_in_region("us-east-1")
        mock_cw.disable_alarm_actions.assert_called_once()
        captured = capsys.readouterr()
        assert "Successfully disabled" in captured.out

    def test_disable_alarms_no_alarms(self, capsys):
        """Test when no alarms exist."""
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = {"MetricAlarms": []}
            mock_client.return_value = mock_cw
            _disable_alarms_in_region("us-east-1")
        captured = capsys.readouterr()
        assert "No alarms found" in captured.out

    def test_disable_alarms_error(self, capsys):
        """Test error when disabling alarms."""
        with patch("boto3.client") as mock_client:
            mock_cw = MagicMock()
            mock_cw.describe_alarms.return_value = {
                "MetricAlarms": [
                    {
                        "AlarmName": "alarm-1",
                        "StateValue": "OK",
                        "ActionsEnabled": True,
                    }
                ]
            }
            mock_cw.disable_alarm_actions.side_effect = ClientError(
                {"Error": {"Code": "ServiceError"}}, "disable_alarm_actions"
            )
            mock_client.return_value = mock_cw
            _disable_alarms_in_region("us-east-1")
        captured = capsys.readouterr()
        assert "Error disabling alarm actions" in captured.out


class TestDisableCloudwatchAlarms:
    """Tests for disable_cloudwatch_alarms function."""

    def test_disable_alarms_multiple_regions(self, capsys):
        """Test disabling alarms across regions."""
        with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._disable_alarms_in_region"
            ):
                disable_cloudwatch_alarms()
        captured = capsys.readouterr()
        assert "Checking CloudWatch alarms" in captured.out


class TestDeleteCustomMetrics:
    """Tests for delete_custom_metrics function."""

    def test_print_custom_metrics_info(self, capsys):
        """Test printing custom metrics information."""
        delete_custom_metrics()
        captured = capsys.readouterr()
        assert "Custom Metrics Information" in captured.out
        assert "cannot be directly deleted" in captured.out
        assert "15 months" in captured.out


class TestUpdateLogGroupRetention:
    """Tests for _update_log_group_retention function."""

    def test_update_retention_never_expire(self, capsys):
        """Test updating log group with never expire retention."""
        mock_client = MagicMock()
        log_group = {
            "logGroupName": "/aws/lambda/test",
            "retentionInDays": "Never expire",
            "storedBytes": 1048576,
        }
        _update_log_group_retention(mock_client, log_group)
        mock_client.put_retention_policy.assert_called_once_with(
            logGroupName="/aws/lambda/test", retentionInDays=1
        )
        captured = capsys.readouterr()
        assert "Setting retention to 1 day" in captured.out

    def test_update_retention_long_period(self, capsys):
        """Test updating log group with long retention period."""
        mock_client = MagicMock()
        log_group = {
            "logGroupName": "/aws/lambda/test",
            "retentionInDays": 30,
            "storedBytes": 2097152,
        }
        _update_log_group_retention(mock_client, log_group)
        mock_client.put_retention_policy.assert_called_once()

    def test_update_retention_already_optimized(self, capsys):
        """Test log group with already optimized retention."""
        mock_client = MagicMock()
        log_group = {
            "logGroupName": "/aws/lambda/test",
            "retentionInDays": 1,
            "storedBytes": 512000,
        }
        _update_log_group_retention(mock_client, log_group)
        mock_client.put_retention_policy.assert_not_called()
        captured = capsys.readouterr()
        assert "already optimized" in captured.out

    def test_update_retention_error(self, capsys):
        """Test error when updating retention."""
        mock_client = MagicMock()
        mock_client.put_retention_policy.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "put_retention_policy"
        )
        log_group = {
            "logGroupName": "/aws/lambda/test",
            "retentionInDays": "Never expire",
            "storedBytes": 1024,
        }
        _update_log_group_retention(mock_client, log_group)
        captured = capsys.readouterr()
        assert "Error setting retention" in captured.out


class TestReduceRetentionInRegion:
    """Tests for _reduce_retention_in_region function."""

    def test_reduce_retention_multiple_log_groups(self, capsys):
        """Test reducing retention for multiple log groups."""
        with patch("boto3.client") as mock_client:
            mock_logs = MagicMock()
            mock_logs.describe_log_groups.return_value = {
                "logGroups": [
                    {
                        "logGroupName": "/aws/lambda/test1",
                        "retentionInDays": 30,
                        "storedBytes": 1024,
                    },
                    {
                        "logGroupName": "/aws/lambda/test2",
                        "retentionInDays": 7,
                        "storedBytes": 2048,
                    },
                ]
            }
            mock_client.return_value = mock_logs
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._update_log_group_retention"
            ):
                _reduce_retention_in_region("us-east-1")

    def test_reduce_retention_no_log_groups(self, capsys):
        """Test when no log groups exist."""
        with patch("boto3.client") as mock_client:
            mock_logs = MagicMock()
            mock_logs.describe_log_groups.return_value = {"logGroups": []}
            mock_client.return_value = mock_logs
            _reduce_retention_in_region("us-east-1")
        captured = capsys.readouterr()
        assert "No log groups found" in captured.out


class TestReduceLogRetention:
    """Tests for reduce_log_retention function."""

    def test_reduce_retention_multiple_regions(self, capsys):
        """Test reducing retention across regions."""
        with patch("cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup.setup_aws_credentials"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_cloudwatch_cleanup._reduce_retention_in_region"
            ):
                reduce_log_retention()
        captured = capsys.readouterr()
        assert "Checking CloudWatch log groups" in captured.out
