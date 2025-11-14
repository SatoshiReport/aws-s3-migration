"""Tests for cost_toolkit/common/backup_utils.py module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.common.backup_utils import (
    check_aws_backup_plans,
    check_dlm_lifecycle_policies,
    check_eventbridge_scheduled_rules,
    get_backup_plan_details,
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
    """Test check_dlm_lifecycle_policies handles errors gracefully."""
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_dlm.get_lifecycle_policies.side_effect = Exception("DLM error")
        mock_client.return_value = mock_dlm

        result = check_dlm_lifecycle_policies("us-east-1")

        assert result == []


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
    """Test check_eventbridge_scheduled_rules handles errors gracefully."""
    with patch("boto3.client") as mock_client:
        mock_events = MagicMock()
        mock_events.list_rules.side_effect = Exception("EventBridge error")
        mock_client.return_value = mock_events

        result = check_eventbridge_scheduled_rules("us-east-1")

        assert result == []


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
    """Test check_aws_backup_plans handles errors gracefully."""
    with patch("boto3.client") as mock_client:
        mock_backup = MagicMock()
        mock_backup.list_backup_plans.side_effect = Exception("Backup error")
        mock_client.return_value = mock_backup

        result = check_aws_backup_plans("us-east-1")

        assert result == []


def test_get_backup_plan_details_success(capsys):
    """Test get_backup_plan_details with successful response."""
    mock_backup_client = MagicMock()
    mock_backup_client.get_backup_plan.return_value = {
        "BackupPlan": {"BackupPlanName": "TestPlan", "Rules": [{"RuleName": "DailyBackup"}]}
    }

    _ = get_backup_plan_details(mock_backup_client, "plan-123", "TestPlan", "2024-01-01")

    captured = capsys.readouterr()
    assert "TestPlan" in captured.out
    assert "plan-123" in captured.out
    assert "2024-01-01" in captured.out


def test_get_backup_plan_details_error(capsys):
    """Test get_backup_plan_details handles errors gracefully."""
    mock_backup_client = MagicMock()
    mock_backup_client.get_backup_plan.side_effect = Exception("API error")

    _ = get_backup_plan_details(mock_backup_client, "plan-123", "TestPlan", "2024-01-01")

    captured = capsys.readouterr()
    assert "Error getting details" in captured.out
