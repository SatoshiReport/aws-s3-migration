"""Tests for cost_toolkit/common/backup_utils.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cost_toolkit.common.backup_utils import (
    check_aws_backup_plans,
    check_dlm_lifecycle_policies,
    check_eventbridge_scheduled_rules,
)


def test_check_dlm_lifecycle_policies_success():
    """Test check_dlm_lifecycle_policies with successful response."""
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_dlm.get_lifecycle_policies.return_value = {
            "Policies": [{"PolicyId": "policy-1"}, {"PolicyId": "policy-2"}]
        }
        mock_client.return_value = mock_dlm

        result = check_dlm_lifecycle_policies("us-east-1")

        assert len(result) == 2
        assert result[0]["PolicyId"] == "policy-1"
        mock_dlm.get_lifecycle_policies.assert_called_once()


def test_check_dlm_lifecycle_policies_no_policies():
    """Test check_dlm_lifecycle_policies when no policies exist."""
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_dlm.get_lifecycle_policies.return_value = {"Policies": []}
        mock_client.return_value = mock_dlm

        result = check_dlm_lifecycle_policies("us-east-1")

        assert result == []


def test_check_dlm_lifecycle_policies_error():
    """Test check_dlm_lifecycle_policies raises on error (fail-fast)."""
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_dlm.get_lifecycle_policies.side_effect = Exception("DLM error")
        mock_client.return_value = mock_dlm

        with pytest.raises(Exception, match="DLM error"):
            check_dlm_lifecycle_policies("us-east-1")


def test_check_eventbridge_scheduled_rules_success():
    """Test check_eventbridge_scheduled_rules with successful response."""
    with patch("boto3.client") as mock_client:
        mock_events = MagicMock()
        mock_events.list_rules.return_value = {"Rules": [{"Name": "rule-1"}, {"Name": "rule-2"}]}
        mock_client.return_value = mock_events

        result = check_eventbridge_scheduled_rules("us-east-1")

        assert len(result) == 2
        assert result[0]["Name"] == "rule-1"


def test_check_eventbridge_scheduled_rules_error():
    """Test check_eventbridge_scheduled_rules raises on error (fail-fast)."""
    with patch("boto3.client") as mock_client:
        mock_events = MagicMock()
        mock_events.list_rules.side_effect = Exception("EventBridge error")
        mock_client.return_value = mock_events

        with pytest.raises(Exception, match="EventBridge error"):
            check_eventbridge_scheduled_rules("us-east-1")


def test_check_aws_backup_plans_success():
    """Test check_aws_backup_plans with successful response."""
    with patch("boto3.client") as mock_client:
        mock_backup = MagicMock()
        mock_backup.list_backup_plans.return_value = {
            "BackupPlansList": [{"BackupPlanId": "plan-1"}, {"BackupPlanId": "plan-2"}]
        }
        mock_client.return_value = mock_backup

        result = check_aws_backup_plans("us-east-1")

        assert len(result) == 2
        assert result[0]["BackupPlanId"] == "plan-1"


def test_check_aws_backup_plans_error():
    """Test check_aws_backup_plans raises on error (fail-fast)."""
    with patch("boto3.client") as mock_client:
        mock_backup = MagicMock()
        mock_backup.list_backup_plans.side_effect = Exception("Backup error")
        mock_client.return_value = mock_backup

        with pytest.raises(Exception, match="Backup error"):
            check_aws_backup_plans("us-east-1")
