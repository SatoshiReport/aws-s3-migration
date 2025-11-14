"""Tests for CloudWatch service checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import botocore.exceptions
from botocore.exceptions import ClientError

from cost_toolkit.scripts.billing.billing_report.service_checks import (
    _check_cloudwatch_alarms_in_region,
    _check_cloudwatch_canaries_in_region,
    _format_cloudwatch_status,
    check_cloudwatch_status,
)


def test_cloud_watch_canaries_region_canary_states():
    """Test checking CloudWatch canary states."""
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


def test_cloud_watch_alarms_region_alarm_states():
    """Test checking CloudWatch alarm states."""
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
    """Test CloudWatch status formatting."""

    def test_all_resolved(self):
        """Test formatting when all resources resolved."""
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
        """Test formatting with only canaries."""
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=2,
            stopped_canaries=2,
            total_alarms=0,
            disabled_alarms=0,
        )
        assert is_resolved is True
        assert "2 canaries stopped" in message

    def test_only_alarms(self):
        """Test formatting with only alarms."""
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=5,
            disabled_alarms=5,
        )
        assert is_resolved is True
        assert "5 alarms disabled" in message

    def test_no_resources(self):
        """Test formatting with no resources."""
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=0,
            disabled_alarms=0,
        )
        assert is_resolved is True
        assert "no active resources" in message

    def test_canaries_active(self):
        """Test formatting with active canaries."""
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
        """Test formatting with active alarms."""
        is_resolved, message = _format_cloudwatch_status(
            total_canaries=0,
            stopped_canaries=0,
            total_alarms=4,
            disabled_alarms=2,
        )
        assert is_resolved is False
        assert "2 alarms enabled" in message


class TestCheckCloudWatchStatus:
    """Test overall CloudWatch status checking."""

    def test_cloudwatch_status(self):
        """Test checking CloudWatch status across resources."""
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

            def client_side_effect(service, **_):
                if service == "cloudwatch":
                    return mock_cw
                if service == "synthetics":
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

            def client_side_effect_active(service, **_):
                if service == "cloudwatch":
                    return mock_cw
                if service == "synthetics":
                    return mock_synthetics
                return MagicMock()

            mock_client.side_effect = client_side_effect_active
            is_resolved, message = check_cloudwatch_status()
            assert is_resolved is False
            assert "ACTIVE" in message

    def test_cloudwatch_error_handling(self):
        """Test error handling in CloudWatch status checks."""
        with patch("boto3.client") as mock_client:
            error = botocore.exceptions.ClientError({"Error": {"Code": "Error"}}, "client")
            mock_client.side_effect = error
            is_resolved, _ = check_cloudwatch_status()
            assert is_resolved is not None
        with patch("boto3.client") as mock_client:
            error = ClientError({"Error": {"Code": "ServiceError"}}, "client")
            mock_client.side_effect = error
            result = check_cloudwatch_status()
            assert result is not None
            assert len(result) == 2
