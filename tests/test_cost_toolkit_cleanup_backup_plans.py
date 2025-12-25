"""Tests for AWS Backup plan disable operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_backup_disable import (
    _delete_backup_selection,
    _delete_plan_selections,
    _delete_single_backup_plan,
    disable_aws_backup_plans,
    disable_dlm_policies,
)


class TestDeleteBackupSelection:
    """Test backup selection deletion functionality."""

    def test_delete_selection_success(self, capsys):
        """Test successful deletion of a backup selection."""
        mock_client = MagicMock()
        selection = {
            "SelectionId": "sel-123",
            "SelectionName": "test-selection",
        }
        _delete_backup_selection(mock_client, "plan-123", selection)
        mock_client.delete_backup_selection.assert_called_once_with(BackupPlanId="plan-123", SelectionId="sel-123")
        captured = capsys.readouterr()
        assert "Successfully removed backup selection" in captured.out

    def test_delete_selection_error(self, capsys):
        """Test handling errors when deleting backup selection."""
        mock_client = MagicMock()
        mock_client.delete_backup_selection.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "delete_backup_selection")
        selection = {
            "SelectionId": "sel-123",
            "SelectionName": "test-selection",
        }
        _delete_backup_selection(mock_client, "plan-123", selection)
        captured = capsys.readouterr()
        assert "Error removing backup selection" in captured.out


class TestDeletePlanSelections:
    """Test deletion of plan selections."""

    def test_delete_multiple_selections(self, capsys):
        """Test deleting multiple backup selections from a plan."""
        mock_client = MagicMock()
        mock_client.list_backup_selections.return_value = {
            "BackupSelectionsList": [
                {"SelectionId": "sel-1", "SelectionName": "selection-1"},
                {"SelectionId": "sel-2", "SelectionName": "selection-2"},
            ]
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_backup_selection"):
            _delete_plan_selections(mock_client, "plan-123")
        captured = capsys.readouterr()
        assert "Found 2 backup selection(s)" in captured.out

    def test_delete_no_selections(self):
        """Test handling plans with no backup selections."""
        mock_client = MagicMock()
        mock_client.list_backup_selections.return_value = {"BackupSelectionsList": []}
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_backup_selection") as mock_delete:
            _delete_plan_selections(mock_client, "plan-123")
        mock_delete.assert_not_called()


class TestDeleteSingleBackupPlan:
    """Test deletion of individual backup plans."""

    def test_delete_plan_success(self, capsys):
        """Test successful deletion of a backup plan."""
        mock_client = MagicMock()
        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": "2024-01-01",
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_plan_selections"):
            _delete_single_backup_plan(mock_client, plan)
        mock_client.delete_backup_plan.assert_called_once_with(BackupPlanId="plan-123")
        captured = capsys.readouterr()
        assert "Successfully deleted backup plan" in captured.out

    def test_delete_plan_error(self, capsys):
        """Test handling errors when deleting backup plan."""
        mock_client = MagicMock()
        mock_client.delete_backup_plan.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "delete_backup_plan")
        plan = {
            "BackupPlanId": "plan-123",
            "BackupPlanName": "test-plan",
            "CreationDate": "2024-01-01",
        }
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_plan_selections"):
            _delete_single_backup_plan(mock_client, plan)
        captured = capsys.readouterr()
        assert "Error deleting backup plan" in captured.out


def test_disable_aws_backup_plans_combined(capsys):
    """Test various scenarios for disabling AWS Backup plans."""

    plans = [
        {
            "BackupPlanId": "plan-1",
            "BackupPlanName": "plan-1",
            "CreationDate": "2024-01-01",
        }
    ]
    with patch("boto3.client"):
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans",
            return_value=plans,
        ):
            with patch("cost_toolkit.scripts.cleanup.aws_backup_disable._delete_single_backup_plan"):
                disable_aws_backup_plans("us-east-1")
    captured = capsys.readouterr()
    assert "Found 1 AWS Backup plan(s)" in captured.out

    with patch("boto3.client"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans", return_value=[]):
            disable_aws_backup_plans("us-east-1")
    captured = capsys.readouterr()
    assert "No AWS Backup plans found" in captured.out

    with patch("boto3.client"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans") as mock_get:
            mock_get.side_effect = ClientError({"Error": {"Code": "UnrecognizedClientException"}}, "list_backup_plans")
            disable_aws_backup_plans("us-east-1")
    captured = capsys.readouterr()
    assert "service not available" in captured.out

    with patch("boto3.client"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.get_backup_plans") as mock_get:
            mock_get.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "list_backup_plans")
            disable_aws_backup_plans("us-east-1")
    captured = capsys.readouterr()
    assert "Error checking AWS Backup" in captured.out


def test_disable_dlm_policies_combined(capsys):
    """Test various scenarios for disabling DLM policies."""

    policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "ENABLED"}]
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_client.return_value = mock_dlm
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
            return_value=policies,
        ):
            disable_dlm_policies("us-east-1")
    mock_dlm.update_lifecycle_policy.assert_called_once_with(PolicyId="policy-1", State="DISABLED")
    captured = capsys.readouterr()
    assert "Successfully disabled DLM policy" in captured.out

    policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "DISABLED"}]
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_client.return_value = mock_dlm
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
            return_value=policies,
        ):
            disable_dlm_policies("us-east-1")
    mock_dlm.update_lifecycle_policy.assert_not_called()
    captured = capsys.readouterr()
    assert "already disabled" in captured.out

    with patch("boto3.client"):
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
            return_value=[],
        ):
            disable_dlm_policies("us-east-1")
    captured = capsys.readouterr()
    assert "No Data Lifecycle Manager policies found" in captured.out

    policies = [{"PolicyId": "policy-1", "Description": "Test policy", "State": "ENABLED"}]
    with patch("boto3.client") as mock_client:
        mock_dlm = MagicMock()
        mock_dlm.update_lifecycle_policy.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "update_lifecycle_policy")
        mock_client.return_value = mock_dlm
        with patch(
            "cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies",
            return_value=policies,
        ):
            disable_dlm_policies("us-east-1")
    captured = capsys.readouterr()
    assert "Error disabling DLM policy" in captured.out

    with patch("boto3.client"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies") as mock_check:
            mock_check.side_effect = ClientError({"Error": {"Code": "UnrecognizedClientException"}}, "get_lifecycle_policies")
            disable_dlm_policies("us-east-1")
    captured = capsys.readouterr()
    assert "service not available" in captured.out

    with patch("boto3.client"):
        with patch("cost_toolkit.scripts.cleanup.aws_backup_disable.check_dlm_lifecycle_policies") as mock_check:
            mock_check.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "get_lifecycle_policies")
            disable_dlm_policies("us-east-1")
    captured = capsys.readouterr()
    assert "Error checking DLM" in captured.out
